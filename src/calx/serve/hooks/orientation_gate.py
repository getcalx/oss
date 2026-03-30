"""Orientation gate: cold path only (first edit of session).
The shell wrapper handles the hot path (sentinel check) in <10ms.
This module runs only when the sentinel is missing or stale.
"""
from __future__ import annotations

import sys
from pathlib import Path

from calx.serve.hooks._common import find_calx_dir, get_session_id, log_hook_error


def _print_rules(calx_dir: Path) -> None:
    """Print rules for orientation."""
    rules_dir = calx_dir / "rules"
    if not rules_dir.exists():
        return
    for rule_file in sorted(rules_dir.glob("*.md")):
        content = rule_file.read_text().strip()
        if content:
            print(content, file=sys.stderr)


def main() -> None:
    """Orientation gate cold path entry point."""
    try:
        calx_dir = find_calx_dir()
        if not calx_dir:
            sys.exit(0)

        session_id = get_session_id()

        # Print rules for orientation
        _print_rules(calx_dir)

        # Write sentinel for future hot-path checks
        sentinel = calx_dir / ".oriented"
        sentinel.write_text(session_id)

    except Exception as e:
        log_hook_error(f"orientation_gate: {e}")

    sys.exit(0)


if __name__ == "__main__":
    main()
