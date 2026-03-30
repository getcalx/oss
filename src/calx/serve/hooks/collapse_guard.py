"""Collapse guard: warns when approaching context window limits.
Fires on every Edit/Write. Checks estimated token usage against
soft cap and ceiling from calx.json.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from calx.serve.hooks._common import find_calx_dir, log_hook_error

# Rough heuristic: ~4000 tokens per conversation turn
TOKENS_PER_TURN = 4000


def _load_token_discipline(calx_dir: Path) -> dict:
    """Load token discipline config from calx.json."""
    config_file = calx_dir / "calx.json"
    if not config_file.exists():
        return {"soft_cap": 200000, "ceiling": 250000}
    try:
        with open(config_file) as f:
            data = json.load(f)
        return data.get("token_discipline", {"soft_cap": 200000, "ceiling": 250000})
    except (json.JSONDecodeError, OSError):
        return {"soft_cap": 200000, "ceiling": 250000}


def main() -> None:
    """Collapse guard entry point."""
    try:
        calx_dir = find_calx_dir()
        if not calx_dir:
            sys.exit(0)

        turn_count = int(os.environ.get("CLAUDE_TURN_COUNT", "0"))
        if turn_count == 0:
            sys.exit(0)

        discipline = _load_token_discipline(calx_dir)
        soft_cap = discipline.get("soft_cap", 200000)
        ceiling = discipline.get("ceiling", 250000)

        soft_cap_turns = soft_cap // TOKENS_PER_TURN
        ceiling_turns = ceiling // TOKENS_PER_TURN

        if turn_count >= ceiling_turns:
            print(
                "CEILING REACHED. Commit everything. Write handoff. End session.",
                file=sys.stderr,
            )
        elif turn_count >= soft_cap_turns:
            print(
                "Approaching token limit. Consider committing progress.",
                file=sys.stderr,
            )

    except Exception as e:
        log_hook_error(f"collapse_guard: {e}")

    sys.exit(0)


if __name__ == "__main__":
    main()
