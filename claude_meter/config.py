import json
from pathlib import Path

DISPLAY_W, DISPLAY_H = 320, 240
WINDOW_HOURS = 5
WEEKLY_HOURS = 168
CLAUDE_DIR   = Path.home() / ".claude" / "projects"
AX206_VID    = 0x1908
AX206_PID    = 0x0102

BG            = (8, 12, 20)
PANEL         = (15, 22, 38)
ACCENT        = (99, 179, 237)
GREEN         = (72, 199, 142)
YELLOW        = (250, 199, 70)
RED           = (252, 90, 90)
ORANGE        = (255, 160, 50)
WHITE         = (220, 230, 245)
DIM           = (80, 100, 130)
BORDER        = (30, 50, 80)
BADGE_CURRENT = (28, 44, 80)
BADGE_WEEKLY  = (44, 26, 74)

_CONFIG_FILE          = Path.home() / ".claude" / "meter_config.json"
_DEFAULT_WINDOW_LIMIT = 500_000


def _load_limits():
    if _CONFIG_FILE.exists():
        try:
            data = json.loads(_CONFIG_FILE.read_text())
            w = int(data.get("window_token_limit", _DEFAULT_WINDOW_LIMIT))
            return w, int(w * 168 / 5)
        except Exception:
            pass
    return _DEFAULT_WINDOW_LIMIT, int(_DEFAULT_WINDOW_LIMIT * 168 / 5)


WINDOW_TOKEN_LIMIT, WEEKLY_TOKEN_LIMIT = _load_limits()


def reload_limits():
    global WINDOW_TOKEN_LIMIT, WEEKLY_TOKEN_LIMIT
    WINDOW_TOKEN_LIMIT, WEEKLY_TOKEN_LIMIT = _load_limits()


def save_limit(window_tokens: int):
    _CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG_FILE.write_text(json.dumps({"window_token_limit": window_tokens}, indent=2))
    print(f"[config] Saved limit: {window_tokens:,} tokens/5h -> {_CONFIG_FILE}")
