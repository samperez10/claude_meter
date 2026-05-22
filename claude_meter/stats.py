import json
import time
from datetime import datetime

import claude_meter.config as config
from claude_meter.api import fetch_usage_api, fmt_reset


def parse_stats():
    now          = time.time()
    window_start = now - config.WINDOW_HOURS * 3600
    week_start   = now - config.WEEKLY_HOURS * 3600

    entries    = []
    seen_uuids = set()
    total_out = msg_count = 0
    cost      = 0.0
    first_ts  = last_ts = None
    last_model    = "Sonnet 4.6"
    last_model_ts = None
    last_role     = None
    last_role_ts  = None

    PRICES = {
        "sonnet": (3.0,  15.0),
        "opus":   (15.0, 75.0),
        "haiku":  (0.80,  4.0),
    }

    if config.CLAUDE_DIR.exists():
        for fpath in config.CLAUDE_DIR.rglob("*.jsonl"):
            try:
                with open(fpath, encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            e = json.loads(line)
                        except Exception:
                            continue

                        ts = None
                        ts_raw = e.get("timestamp")
                        if ts_raw:
                            try:
                                ts = datetime.fromisoformat(
                                    ts_raw.replace("Z", "+00:00")).timestamp()
                            except Exception:
                                pass

                        role = e.get("message", {}).get("role") if "message" in e else None
                        if role and ts and (last_role_ts is None or ts > last_role_ts):
                            last_role    = role
                            last_role_ts = ts

                        if ts:
                            if first_ts is None or ts < first_ts:
                                first_ts = ts
                            if last_ts is None or ts > last_ts:
                                last_ts = ts

                        m = e.get("model") or e.get("message", {}).get("model", "")
                        if m and ts and (last_model_ts is None or ts > last_model_ts):
                            last_model    = m
                            last_model_ts = ts

                        uid = e.get("uuid", "")
                        if uid and uid in seen_uuids:
                            continue
                        if uid:
                            seen_uuids.add(uid)

                        u   = e.get("message", {}).get("usage", {})
                        out = u.get("output_tokens", 0) or 0
                        inp = u.get("input_tokens",  0) or 0
                        cc  = u.get("cache_creation_input_tokens", 0) or 0

                        if out > 0 and ts:
                            msg_count += 1
                            total_out += out
                            tier = next(
                                (t for t in PRICES if t in last_model.lower()), "sonnet")
                            p_in, p_out = PRICES[tier]
                            cost += (inp + cc) * p_in / 1e6 + out * p_out / 1e6
                            entries.append((ts, out))
            except Exception:
                continue

    window_tok   = sum(out for ts, out in entries if ts >= window_start)
    weekly_tok   = sum(out for ts, out in entries if ts >= week_start)
    burn_tok     = sum(out for ts, out in entries if ts >= now - 300)
    burn_rate    = burn_tok / 5.0  # tokens per minute over last 5 min

    api = fetch_usage_api()
    if api:
        window_pct   = float(api.get("five_hour", {}).get("utilization", 0) or 0)
        weekly_pct   = float(api.get("seven_day", {}).get("utilization", 0) or 0)
        window_reset = fmt_reset(api.get("five_hour", {}).get("resets_at"))
        weekly_reset = fmt_reset(api.get("seven_day", {}).get("resets_at"))
        api_ok       = True
    else:
        window_pct   = min(window_tok / config.WINDOW_TOKEN_LIMIT * 100, 100)
        weekly_pct   = min(weekly_tok / config.WEEKLY_TOKEN_LIMIT * 100, 100)
        win_entries  = [(ts, out) for ts, out in entries if ts >= window_start]
        week_entries = [(ts, out) for ts, out in entries if ts >= week_start]

        def _rst(subset, secs):
            if not subset:
                return "No data"
            rem = (min(ts for ts, _ in subset) + secs) - now
            if rem <= 0:
                return "Now"
            d2 = int(rem // 86400)
            h  = int((rem % 86400) // 3600)
            m  = int((rem % 3600)  // 60)
            return f"{d2}d {h}h" if d2 else (f"{h}h {m}m" if h else f"{m}m")

        window_reset = _rst(win_entries,  config.WINDOW_HOURS * 3600)
        weekly_reset = _rst(week_entries, config.WEEKLY_HOURS * 3600)
        api_ok       = False

    # Active while the last logged entry is a user message (Claude hasn't replied yet)
    is_active = (
        last_role == "user"
        and last_role_ts is not None
        and (now - last_role_ts) < 300
    )

    short = last_model
    for pat, rep in [
        ("claude-sonnet-4-6", "Sonnet 4.6"),
        ("claude-sonnet-4-5", "Sonnet 4.5"),
        ("claude-opus-4-7",   "Opus 4.7"),
        ("claude-opus-4-6",   "Opus 4.6"),
        ("claude-haiku-4-5",  "Haiku 4.5"),
    ]:
        if pat in short:
            short = rep
            break
    if len(short) > 20:
        short = "Sonnet 4.6"

    dur = "—"
    if first_ts and last_ts:
        s = int(last_ts - first_ts)
        h, m2 = divmod(s // 60, 60)
        dur = f"{h}h {m2:02d}m" if h else f"{m2}m"

    return {
        "model":        short,
        "messages":     msg_count,
        "total_output": total_out,
        "window_pct":   window_pct,
        "window_tok":   window_tok,
        "window_reset": window_reset,
        "weekly_pct":   weekly_pct,
        "weekly_tok":   weekly_tok,
        "weekly_reset": weekly_reset,
        "cost":         cost,
        "duration":     dur,
        "is_active":    is_active,
        "last_ts_raw":  last_ts,
        "last_active":  (datetime.fromtimestamp(last_ts).strftime("%H:%M:%S")
                         if last_ts else "—"),
        "api_ok":       api_ok,
        "burn_rate":    burn_rate,
    }
