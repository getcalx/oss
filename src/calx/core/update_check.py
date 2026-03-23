"""Check PyPI for newer Calx versions. Cached for 24 hours."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

_PYPI_URL = "https://pypi.org/pypi/getcalx/json"
_CACHE_FILE = ".last_update_check"
_CACHE_HOURS = 24


def check_for_update(calx_dir: Path) -> str | None:
    """Return an update message if a newer version is available, else None.

    Checks PyPI at most once per 24 hours. Never blocks on failure.
    """
    cache_path = calx_dir / "health" / _CACHE_FILE

    # Check cache
    if cache_path.exists():
        try:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            cached_at = datetime.fromisoformat(data.get("checked_at", ""))
            hours_since = (datetime.now(timezone.utc) - cached_at).total_seconds() / 3600
            if hours_since < _CACHE_HOURS:
                msg = data.get("message")
                return msg if msg else None
        except (json.JSONDecodeError, ValueError, OSError):
            pass  # stale or corrupt cache, re-check

    # Fetch latest version from PyPI
    try:
        from calx import __version__ as current

        req = urllib.request.Request(_PYPI_URL, headers={"Accept": "application/json"})
        resp = urllib.request.urlopen(req, timeout=3)
        info = json.loads(resp.read().decode("utf-8"))
        latest = info.get("info", {}).get("version", "")

        if latest and latest != current and _is_newer(latest, current):
            message = (
                f"Calx {latest} available (you have {current}). "
                f"Run: pip install --upgrade getcalx"
            )
        else:
            message = ""

        # Write cache
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps({
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "latest": latest,
                "current": current,
                "message": message,
            }) + "\n",
            encoding="utf-8",
        )

        return message if message else None

    except (urllib.error.URLError, OSError, ValueError, KeyError):
        return None  # network failure — silent


def _is_newer(latest: str, current: str) -> bool:
    """Simple version comparison. Handles x.y.z format."""
    try:
        lat = tuple(int(x) for x in latest.split("."))
        cur = tuple(int(x) for x in current.split("."))
        return lat > cur
    except (ValueError, AttributeError):
        return False
