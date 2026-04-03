"""Check PyPI for newer Calx versions and auto-upgrade. Cached for 24 hours."""

from __future__ import annotations

import json
import subprocess
import sys
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

        _write_cache(cache_path, latest, current, message)
        return message if message else None

    except (urllib.error.URLError, OSError, ValueError, KeyError):
        return None  # network failure — silent


def auto_upgrade(calx_dir: Path) -> str | None:
    """Check for a newer version and install it in the background.

    Returns a status message, or None if already up to date / on failure.
    """
    cache_path = calx_dir / "health" / _CACHE_FILE

    # Respect the 24h cache: don't re-check (or re-upgrade) within window
    if cache_path.exists():
        try:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            cached_at = datetime.fromisoformat(data.get("checked_at", ""))
            hours_since = (datetime.now(timezone.utc) - cached_at).total_seconds() / 3600
            if hours_since < _CACHE_HOURS:
                msg = data.get("message")
                return msg if msg else None
        except (json.JSONDecodeError, ValueError, OSError):
            pass

    try:
        from calx import __version__ as current

        req = urllib.request.Request(_PYPI_URL, headers={"Accept": "application/json"})
        resp = urllib.request.urlopen(req, timeout=3)
        info = json.loads(resp.read().decode("utf-8"))
        latest = info.get("info", {}).get("version", "")

        if not latest or not _is_newer(latest, current):
            # Up to date: cache and return
            _write_cache(cache_path, latest, current, "")
            return None

        # Perform the upgrade
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "getcalx"],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode == 0:
            message = f"Calx auto-upgraded: {current} -> {latest}"
        else:
            message = (
                f"Calx {latest} available (you have {current}). "
                f"Auto-upgrade failed. Run: pip install --upgrade getcalx"
            )

        _write_cache(cache_path, latest, current, message)
        return message

    except (urllib.error.URLError, OSError, ValueError, KeyError,
            subprocess.TimeoutExpired):
        return None


def _write_cache(
    cache_path: Path, latest: str, current: str, message: str
) -> None:
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


def _is_newer(latest: str, current: str) -> bool:
    """Simple version comparison. Handles x.y.z format."""
    try:
        lat = tuple(int(x) for x in latest.split("."))
        cur = tuple(int(x) for x in current.split("."))
        return lat > cur
    except (ValueError, AttributeError):
        return False
