"""Dirty-exit recovery check at session start."""

from __future__ import annotations

from pathlib import Path

from calx.core.state import check_clean_exit


def recovery_check(calx_dir: Path) -> str | None:
    """Check whether the previous session exited cleanly.

    Returns a recovery prompt message if the exit was dirty,
    or ``None`` if everything is fine.
    """
    status = check_clean_exit(calx_dir)

    if status.was_clean:
        return None

    return (
        "Previous session did not exit cleanly. "
        "There may be undistilled corrections or uncommitted changes. "
        "Run `calx status` to review."
    )
