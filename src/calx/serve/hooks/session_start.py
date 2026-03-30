"""Session start hook -- fires once at the beginning of each Claude Code session.
1. Write session marker for orientation gate
2. Inject rules from .calx/rules/ files
3. Run JSONL integrity check
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from calx.serve.hooks._common import find_calx_dir, log_hook_error


def _write_session_marker(calx_dir: Path) -> None:
    """Write ppid:timestamp marker for session ID resolution."""
    ppid = os.getppid()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (calx_dir / ".session_start").write_text(f"{ppid}:{now}")


def _inject_rules_from_files(calx_dir: Path) -> None:
    """Fallback: inject rules from .calx/rules/*.md to stderr."""
    rules_dir = calx_dir / "rules"
    if not rules_dir.exists():
        return
    for rule_file in sorted(rules_dir.glob("*.md")):
        content = rule_file.read_text().strip()
        if content:
            print(content, file=sys.stderr)


def _check_jsonl_integrity(calx_dir: Path) -> None:
    """Verify corrections.jsonl is valid JSONL."""
    jsonl = calx_dir / "corrections.jsonl"
    if not jsonl.exists():
        return
    try:
        with open(jsonl) as f:
            for i, line in enumerate(f, 1):
                line = line.strip()
                if line:
                    json.loads(line)
    except json.JSONDecodeError as e:
        log_hook_error(f"JSONL integrity error at line {i}: {e}")
    except OSError as e:
        log_hook_error(f"JSONL read error: {e}")


def main() -> None:
    """Session start hook entry point."""
    try:
        calx_dir = find_calx_dir()
        if not calx_dir:
            return
        _write_session_marker(calx_dir)
        # v0.4.0: file-based rule injection only.
        # Server-based briefing fetch coming in v0.5.0.
        _inject_rules_from_files(calx_dir)
        _check_jsonl_integrity(calx_dir)
    except Exception as e:
        log_hook_error(f"session_start: {e}")


if __name__ == "__main__":
    main()
