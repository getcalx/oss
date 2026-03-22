"""Session-end capture prompt. Called by the session-end hook."""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

from calx.core.corrections import get_undistilled
from calx.core.events import Event, log_event
from calx.core.state import write_clean_exit


def session_end_prompt(calx_dir: Path) -> str:
    """Generate a session-end summary and write clean-exit marker.

    Steps:
    1. Count undistilled corrections
    2. Check for uncommitted git changes
    3. Write clean-exit marker
    4. Log session_end event
    5. Return formatted message
    """
    undistilled = get_undistilled(calx_dir)
    uncommitted = _has_uncommitted_changes(calx_dir)

    write_clean_exit(calx_dir)

    log_event(calx_dir, Event(
        timestamp=datetime.now(timezone.utc).isoformat(),
        event="session_end",
        data={
            "undistilled_count": len(undistilled),
            "uncommitted_changes": uncommitted,
        },
    ))

    parts: list[str] = []

    if undistilled:
        ids = ", ".join(c.id for c in undistilled)
        parts.append(
            f"{len(undistilled)} undistilled correction(s): {ids}. "
            "Consider running `calx distill`."
        )

    if uncommitted:
        parts.append("Uncommitted changes detected. Consider committing before exit.")

    if not parts:
        return "Session ended cleanly. No pending items."

    return "Session end summary:\n" + "\n".join(f"- {p}" for p in parts)


def _has_uncommitted_changes(calx_dir: Path) -> bool:
    """Check for uncommitted git changes in the project root."""
    project_root = calx_dir.parent
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            cwd=str(project_root),
            timeout=5,
        )
        return bool(result.stdout.strip())
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return False
