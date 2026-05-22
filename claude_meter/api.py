import json
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

_CREDS_FILE       = Path.home() / ".claude" / ".credentials.json"
_USAGE_URL        = "https://api.anthropic.com/api/oauth/usage"
_USAGE_CACHE_FILE = Path.home() / ".claude" / "meter_usage_cache.json"
_API_TTL          = 120   # seconds between real API calls
_API_BACKOFF      = 3600  # seconds to wait after a 429


def _load_disk_cache():
    try:
        d = json.loads(_USAGE_CACHE_FILE.read_text())
        return {"data": d["data"], "ts": d.get("ts", 0.0), "backoff_until": 0.0}
    except Exception:
        return {"data": None, "ts": 0.0, "backoff_until": 0.0}


_api_cache = _load_disk_cache()


def _get_token():
    try:
        creds = json.loads(_CREDS_FILE.read_text())
        return creds["claudeAiOauth"]["accessToken"]
    except Exception:
        return None


def fetch_usage_api(force=False):
    """Return dict with five_hour/seven_day utilization %, None on failure."""
    now = time.time()
    if now < _api_cache["backoff_until"]:
        remaining = int(_api_cache["backoff_until"] - now)
        return _api_cache["data"]
    if not force and _api_cache["data"] and (now - _api_cache["ts"]) < _API_TTL:
        return _api_cache["data"]

    token = _get_token()
    if not token:
        return None
    try:
        req = urllib.request.Request(
            _USAGE_URL,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        _api_cache["data"] = data
        _api_cache["ts"]   = now
        try:
            _USAGE_CACHE_FILE.write_text(json.dumps({"data": data, "ts": now}))
        except Exception:
            pass
        return data
    except urllib.error.HTTPError as e:
        if e.code == 429:
            _api_cache["backoff_until"] = now + _API_BACKOFF
        return _api_cache["data"]
    except Exception:
        return _api_cache["data"]


def clear_cache():
    """Delete the disk cache and reset in-memory state."""
    try:
        _USAGE_CACHE_FILE.unlink(missing_ok=True)
    except Exception as e:
        print(f"[api] Warning: could not clear cache file: {e}")
    _api_cache["data"]          = None
    _api_cache["ts"]            = 0.0
    _api_cache["backoff_until"] = 0.0
    print("[usage] Cache cleared.")


def fmt_reset(iso_str):
    """ISO timestamp -> human 'Xh Ym' remaining string."""
    if not iso_str:
        return "No data"
    try:
        dt  = datetime.fromisoformat(iso_str)
        rem = (dt - datetime.now(timezone.utc)).total_seconds()
        if rem <= 0:
            return "Now"
        d2 = int(rem // 86400)
        h  = int((rem % 86400) // 3600)
        m  = int((rem % 3600)  // 60)
        if d2:
            return f"{d2}d {h}h"
        if h:
            return f"{h}h {m}m"
        return f"{m}m"
    except Exception:
        return "?"
