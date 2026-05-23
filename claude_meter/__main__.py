import argparse
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import claude_meter.config as config
from claude_meter.api import clear_cache
from claude_meter.stats import parse_stats
from claude_meter.renderer import render, fmt_tokens, get_activity_text
from claude_meter.lcd import AX206LCD


def push_frame(display, preview, preview_path, frame):
    if preview:
        frame.save(str(preview_path))
        return True
    try:
        display.display_image(frame)
        return True
    except Exception as e:
        display._connected = False
        if display.debug:
            print(f"[lcd] Display error: {e}")
        return False


def main():
    ap = argparse.ArgumentParser(description="Claude Code LCD Monitor")
    ap.add_argument("--preview",        action="store_true",
                    help="Save preview.png instead of sending to LCD")
    ap.add_argument("--brightness",     type=int, default=5, choices=range(0, 8),
                    help="LCD backlight brightness (0-7)")
    ap.add_argument("--stats-interval", type=int, default=5,
                    help="How often to re-parse JSONL files (seconds, default 5)")
    ap.add_argument("--no-flip-h", action="store_true",
                    help="Disable horizontal flip")
    ap.add_argument("--no-flip-v", action="store_true",
                    help="Disable vertical flip")
    theme_grp = ap.add_mutually_exclusive_group()
    theme_grp.add_argument("--dark",  action="store_true", default=False,
                           help="Dark theme (default)")
    theme_grp.add_argument("--white", action="store_true", default=False,
                           help="Light/white theme")
    ap.add_argument("--debug",          action="store_true",
                    help="Enable debug output")
    ap.add_argument("--calibrate",      action="store_true",
                    help="Set the 5h window limit to your current usage "
                         "(run when Claude tells you you've hit the limit)")
    args = ap.parse_args()

    config.set_theme("white" if args.white else "dark")

    if args.calibrate:
        stats = parse_stats()
        config.save_limit(stats["window_tok"])
        clear_cache()
        print(f"[calibrate] Current 5h output tokens: {stats['window_tok']:,}")
        print(f"[calibrate] Run the meter normally now.")
        sys.exit(0)

    flip_h = not args.no_flip_h
    flip_v = not args.no_flip_v
    preview_path   = Path("preview.png")

    display = None
    if not args.preview:
        try:
            display = AX206LCD(
                debug=args.debug,
                flip_horizontal=flip_h,
                flip_vertical=flip_v,
            )
            display.set_backlight(args.brightness)
            display.clear()
        except Exception as e:
            print(f"Failed to initialize LCD: {e}")
            print("Falling back to preview mode...")
            args.preview = True

    _reconnect_interval = 5.0  # seconds between reconnect attempts
    _reconnect_state = [0.0]   # [last_attempt_time] — mutable so the loop can update it

    print(f"[claude-lcd] Watching {config.CLAUDE_DIR}")
    print(f"[claude-lcd] Mode: {'preview' if args.preview else 'LCD'}  "
          f"render=1s  stats={args.stats_interval}s")
    print(f"[claude-lcd] Limits: 5h={fmt_tokens(config.WINDOW_TOKEN_LIMIT)} "
          f"7d={fmt_tokens(config.WEEKLY_TOKEN_LIMIT)} output tokens")
    if not args.preview:
        print(f"[claude-lcd] Backlight: {args.brightness}/7")
    print("Ctrl+C to stop.\n")

    stats      = parse_stats()
    stats_lock = threading.Lock()
    stop_event = threading.Event()

    def stats_worker():
        while not stop_event.is_set():
            stop_event.wait(args.stats_interval)
            if stop_event.is_set():
                break
            config.reload_limits()
            new_stats = parse_stats()
            with stats_lock:
                stats.clear()
                stats.update(new_stats)
            activity = get_activity_text(stats["is_active"], stats["last_ts_raw"])
            if stats["api_ok"]:
                tok_info = f"{stats['window_pct']:.0f}%"
            else:
                tok_info = (f"{stats['window_pct']:.0f}%"
                            f" ({fmt_tokens(stats['window_tok'])}/{fmt_tokens(config.WINDOW_TOKEN_LIMIT)})"
                            f" [no API]")
            print(
                f"[stats] {datetime.now().strftime('%H:%M:%S')}  "
                f"5h: {tok_info}  "
                f"7d: {stats['weekly_pct']:.0f}%  "
                f"{'[' + activity + ']' if activity else '[idle]'}"
            )

    worker = threading.Thread(target=stats_worker, daemon=True)
    worker.start()

    try:
        while True:
            loop_start = time.time()

            # Auto-reconnect if the USB display was unplugged and re-plugged
            if display is not None and not args.preview and not display._connected:
                now = time.time()
                if now - _reconnect_state[0] >= _reconnect_interval:
                    _reconnect_state[0] = now
                    print("[lcd] Display disconnected — reconnecting...")
                    display.reconnect(brightness=args.brightness)

            with stats_lock:
                current_stats = dict(stats)

            frame = render(current_stats)
            push_frame(display, args.preview, preview_path, frame)

            elapsed = time.time() - loop_start
            time.sleep(max(0.0, 1.0 - elapsed))

    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        worker.join(timeout=2)
        if display:
            display.close()
    print("Stopped.")


if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            import ctypes
            if not ctypes.windll.shell32.IsUserAnAdmin():
                print("WARNING: Not running as Administrator!\n")
        except Exception:
            pass
    main()
