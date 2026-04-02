"""Session end hook -- fires once when a Claude Code session stops.

1. Read active session ID from state file
2. Call POST /enforce/end-session on the server
3. Clean up local state files and legacy markers
"""
from __future__ import annotations

import json
from pathlib import Path

from calx.serve.hooks._common import (
    find_calx_dir,
    get_server_url,
    log_hook_error,
    server_is_running,
)


def _end_session_on_server(server_url: str, session_id: str) -> None:
    """Tell the server to end the session."""
    try:
        import urllib.request
        body = json.dumps({"session_id": session_id}).encode()
        req = urllib.request.Request(
            f"{server_url}/enforce/end-session",
            data=body,
            method="POST",
        )
        req.add_header("Content-Type", "application/json")
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass


def _cleanup_state(calx_dir: Path) -> None:
    """Remove local state files and legacy markers."""
    state_dir = calx_dir / "state"
    if state_dir.exists():
        active_file = state_dir / "active-session"
        if active_file.exists():
            session_id = active_file.read_text().strip()
            state_file = state_dir / f"session-{session_id}.json"
            if state_file.exists():
                state_file.unlink()
            active_file.unlink()

    # Legacy markers
    for legacy in [".session_start", ".oriented"]:
        marker = calx_dir / legacy
        if marker.exists():
            marker.unlink()


def main() -> None:
    """Session end hook entry point."""
    try:
        calx_dir = find_calx_dir()
        if not calx_dir:
            return

        # Get session ID before cleanup
        state_dir = calx_dir / "state"
        session_id = None
        active_file = state_dir / "active-session" if state_dir.exists() else None
        if active_file and active_file.exists():
            session_id = active_file.read_text().strip()

        # Tell server to end session
        if session_id:
            server_url = get_server_url(calx_dir)
            if server_url and server_is_running(server_url):
                _end_session_on_server(server_url, session_id)

        # Clean up local state
        _cleanup_state(calx_dir)

    except Exception as e:
        log_hook_error(f"session_end: {e}")


if __name__ == "__main__":
    main()
