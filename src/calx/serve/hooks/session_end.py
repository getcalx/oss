"""Session end hook -- fires once when a Claude Code session stops.
Cleans up session markers (.session_start, .oriented).
"""
from __future__ import annotations

from calx.serve.hooks._common import find_calx_dir, log_hook_error


def main() -> None:
    """Session end hook entry point."""
    try:
        calx_dir = find_calx_dir()
        if not calx_dir:
            return

        # Clean up session marker
        marker = calx_dir / ".session_start"
        if marker.exists():
            marker.unlink()

        # Clean up orientation sentinel
        oriented = calx_dir / ".oriented"
        if oriented.exists():
            oriented.unlink()

    except Exception as e:
        log_hook_error(f"session_end: {e}")


if __name__ == "__main__":
    main()
