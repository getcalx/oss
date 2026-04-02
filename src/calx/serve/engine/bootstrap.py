"""Session bootstrap engine.

Gathers prior-session context at startup: last handoff, board state,
dirty-exit detection, staleness warnings, and rules needing attention.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from calx.serve.db.engine import (
    BoardStateRow,
    HandoffRow,
    RuleRow,
    SessionRow,
)

STALENESS_THRESHOLD_HOURS = 24


@dataclass
class BootstrapResult:
    last_handoff: HandoffRow | None
    board_state: list[BoardStateRow]
    dirty_exit: bool
    dirty_session_id: str | None
    staleness_warning: str | None
    rules_needing_attention: list[RuleRow]


async def bootstrap_session(
    db,
    state_dir: Path | None = None,
    staleness_hours: int = STALENESS_THRESHOLD_HOURS,
    now: datetime | None = None,
) -> BootstrapResult:
    """Build a BootstrapResult from the current DB state.

    Sequence:
    1. Determine current time.
    2. Read latest handoff (any session).
    3. Read board state.
    4. Check handoff staleness.
    5. Detect dirty exit.
    6. Find rules needing attention.
    7. Return BootstrapResult.
    """
    now = now or datetime.now(timezone.utc)

    # -- Latest handoff ---------------------------------------------------
    last_handoff: HandoffRow | None = await db.get_latest_handoff()

    # -- Board state ------------------------------------------------------
    board_state: list[BoardStateRow] = await db.get_board_state()

    # -- Staleness check --------------------------------------------------
    staleness_warning: str | None = None
    if last_handoff is not None and last_handoff.created_at:
        handoff_time = datetime.fromisoformat(last_handoff.created_at)
        if handoff_time.tzinfo is None:
            handoff_time = handoff_time.replace(tzinfo=timezone.utc)
        age = now - handoff_time
        if age > timedelta(hours=staleness_hours):
            hours_ago = int(age.total_seconds() // 3600)
            staleness_warning = (
                f"Last handoff is {hours_ago} hours old "
                f"(threshold: {staleness_hours}h). Context may be stale."
            )

    # -- Dirty exit detection ---------------------------------------------
    dirty_exit = False
    dirty_session_id: str | None = None
    active_session: SessionRow | None = await db.get_active_session()

    if active_session is not None and active_session.ended_at is None:
        if state_dir is not None:
            marker = state_dir / f"clean-exit-{active_session.id}"
            if not marker.exists():
                dirty_exit = True
                dirty_session_id = active_session.id
        else:
            # No state_dir: fall back to DB-only check (active + no ended_at)
            dirty_exit = True
            dirty_session_id = active_session.id

    # -- Rules needing attention ------------------------------------------
    all_active_rules: list[RuleRow] = await db.find_rules(active_only=True)
    rules_needing_attention = [
        r for r in all_active_rules
        if r.health_status in ("warning", "critical")
    ]

    return BootstrapResult(
        last_handoff=last_handoff,
        board_state=board_state,
        dirty_exit=dirty_exit,
        dirty_session_id=dirty_session_id,
        staleness_warning=staleness_warning,
        rules_needing_attention=rules_needing_attention,
    )
