"""Shared utilities for all hooks.
find_calx_dir, get_session_id, log_hook_error.
"""
from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path


def find_calx_dir() -> Path | None:
    """Walk up from cwd looking for .calx/ directory."""
    current = Path.cwd()
    for parent in [current, *current.parents]:
        candidate = parent / ".calx"
        if candidate.is_dir():
            return candidate
    return None


def get_session_id() -> str:
    """Determine the current session ID.

    Priority:
    1. $CLAUDE_SESSION_ID env var
    2. Hash of .calx/.session_start marker content
    3. Fallback: parent PID as string
    """
    session_id = os.environ.get("CLAUDE_SESSION_ID")
    if session_id:
        return session_id

    calx_dir = find_calx_dir()
    if calx_dir:
        marker = calx_dir / ".session_start"
        if marker.exists():
            content = marker.read_text().strip()
            return hashlib.sha256(content.encode()).hexdigest()[:16]

    return str(os.getppid())


def log_hook_error(message: str) -> None:
    """Append timestamped error to .calx/hook-errors.log."""
    calx_dir = find_calx_dir()
    if not calx_dir:
        return
    log_file = calx_dir / "hook-errors.log"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(log_file, "a") as f:
        f.write(f"[{timestamp}] {message}\n")


def get_server_url(calx_dir: Path) -> str | None:
    """Read server URL from .calx/server.json if it exists."""
    import json

    server_json = calx_dir / "server.json"
    if not server_json.exists():
        return None
    try:
        with open(server_json) as f:
            data = json.load(f)
        host = data.get("host", "127.0.0.1")
        port = data.get("port", 4195)
        return f"http://{host}:{port}"
    except (json.JSONDecodeError, OSError):
        return None


def server_is_running(url: str) -> bool:
    """Check if the calx serve is reachable."""
    try:
        import urllib.request
        req = urllib.request.Request(f"{url}/health", method="GET")
        urllib.request.urlopen(req, timeout=1)
        return True
    except Exception:
        return False
