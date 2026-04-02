"""State file writer for enforcement hooks.

Writes session state to .calx/state/ for fast hot-path reads.
All writes are atomic: write to temp file, then os.rename.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


def write_session_state(
    state_dir: Path,
    session_id: str,
    surface: str,
    oriented: bool,
    token_estimate: int,
    tool_call_count: int,
    soft_cap: int,
    ceiling: int,
    server_fail_mode: str,
    collapse_fail_mode: str,
    started_at: str,
    rules: list[dict],
) -> None:
    """Write session state file atomically."""
    state_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "session_id": session_id,
        "surface": surface,
        "oriented": oriented,
        "token_estimate": token_estimate,
        "tool_call_count": tool_call_count,
        "soft_cap": soft_cap,
        "ceiling": ceiling,
        "server_fail_mode": server_fail_mode,
        "collapse_fail_mode": collapse_fail_mode,
        "started_at": started_at,
        "rules": rules,
    }
    target = state_dir / f"session-{session_id}.json"
    _atomic_write(target, json.dumps(data, indent=2))


def write_active_session(state_dir: Path, session_id: str) -> None:
    """Write the active-session pointer file."""
    state_dir.mkdir(parents=True, exist_ok=True)
    target = state_dir / "active-session"
    _atomic_write(target, session_id)


def remove_session_state(state_dir: Path, session_id: str) -> None:
    """Remove session state file and active-session pointer."""
    state_file = state_dir / f"session-{session_id}.json"
    if state_file.exists():
        state_file.unlink()
    active_file = state_dir / "active-session"
    if active_file.exists():
        active_file.unlink()


def read_session_state(state_dir: Path, session_id: str) -> dict | None:
    """Read session state from file. Returns None if not found."""
    state_file = state_dir / f"session-{session_id}.json"
    if not state_file.exists():
        return None
    try:
        return json.loads(state_file.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _atomic_write(target: Path, content: str) -> None:
    """Write content to target atomically via temp file + rename."""
    fd, tmp_path = tempfile.mkstemp(
        dir=str(target.parent),
        prefix=".tmp_",
        suffix=".json",
    )
    closed = False
    try:
        os.write(fd, content.encode())
        os.close(fd)
        closed = True
        os.rename(tmp_path, str(target))
    except Exception:
        if not closed:
            os.close(fd)
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
