"""end_session tool -- end an active enforcement session."""
# NOTE: Do NOT use 'from __future__ import annotations' here.
# FastMCP 3.x needs runtime-evaluated type annotations to detect Context params.

from datetime import datetime, timezone
from pathlib import Path

from calx.serve.db.engine import HandoffRow
from calx.serve.engine.health import score_all_rules
from calx.serve.engine.state_writer import remove_session_state
from calx.serve.engine.telemetry_sender import send_telemetry


def is_telemetry_enabled(state_dir: Path | None = None) -> bool:
    """Check if telemetry is enabled in calx.json."""
    import json
    if state_dir is None:
        return True
    calx_dir = state_dir.parent if state_dir else None
    if calx_dir is None:
        return True
    calx_json = calx_dir / "calx.json"
    if not calx_json.exists():
        return True
    try:
        config = json.loads(calx_json.read_text())
        return config.get("telemetry", {}).get("enabled", True)
    except Exception:
        return True


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


async def handle_end_session(
    db: object,
    session_id: str,
    state_dir: Path | None = None,
    what_changed: str | None = None,
    what_others_need: str | None = None,
    decisions_deferred: str | None = None,
    next_priorities: str | None = None,
) -> dict:
    """Core handler for end_session tool."""
    session = await db.get_session(session_id)
    if not session:
        return {"status": "not_found"}

    if session.ended_at:
        return {"status": "error", "message": "session already ended"}

    now = _now()
    await db.update_session(session_id, ended_at=now)

    # Write handoff if content provided
    if what_changed:
        handoff = HandoffRow(
            session_id=session_id,
            what_changed=what_changed,
            what_others_need=what_others_need,
            decisions_deferred=decisions_deferred,
            next_priorities=next_priorities,
            created_at=now,
        )
        await db.insert_handoff(handoff)

    # Count corrections logged during this session
    corrections = await db.find_corrections(limit=1000)
    corrections_logged = sum(
        1 for c in corrections if c.created_at >= session.started_at
    )

    # Compute duration
    try:
        started = datetime.fromisoformat(session.started_at.replace("Z", "+00:00"))
        ended = datetime.fromisoformat(now.replace("Z", "+00:00"))
        duration_minutes = int((ended - started).total_seconds() / 60)
    except (ValueError, AttributeError):
        duration_minutes = 0

    # Run health scoring
    health_results = await score_all_rules(db)

    # Include plan progress if active plan exists
    plan = await db.get_active_plan()
    plan_progress = None
    if plan:
        import json
        chunks = json.loads(plan.chunks)
        done_count = sum(1 for c in chunks if c.get("status") == "done")
        total_count = len(chunks)
        blocked = [c["id"] for c in chunks if c.get("status") == "blocked"]
        plan_progress = {
            "plan_id": plan.id,
            "task": plan.task_description,
            "phase": plan.phase,
            "wave": plan.current_wave,
            "chunks_done": done_count,
            "chunks_total": total_count,
            "blocked_chunks": blocked,
        }

    # Send telemetry (after handoff, before state cleanup)
    if is_telemetry_enabled(state_dir):
        try:
            from calx.serve.engine.telemetry_payload import build_telemetry_payload
            calx_dir = state_dir.parent if state_dir else None
            payload = await build_telemetry_payload(
                db,
                calx_dir=calx_dir,
                session_duration_minutes=duration_minutes,
                tool_call_count=session.tool_call_count,
            )
            send_telemetry(payload)
        except Exception:
            pass

    # Remove state files
    if state_dir:
        remove_session_state(state_dir, session_id)
        # Write clean-exit marker
        marker = state_dir / f"clean-exit-{session_id}"
        marker.write_text(now)

    return {
        "status": "ok",
        "session_id": session_id,
        "corrections_logged": corrections_logged,
        "session_duration_minutes": duration_minutes,
        "health_summary": {
            "rules_scored": len(health_results),
            "transitions": [
                {"rule_id": h.rule_id, "from": h.old_status, "to": h.new_status}
                for h in health_results if h.old_status != h.new_status
            ],
        },
        "plan_progress": plan_progress,
    }


def register_end_session_tool(mcp: object) -> None:
    """Register end_session MCP tool."""
    from fastmcp import Context

    @mcp.tool()
    async def end_session(
        session_id: str,
        what_changed: str | None = None,
        what_others_need: str | None = None,
        decisions_deferred: str | None = None,
        next_priorities: str | None = None,
        ctx: Context = None,
    ) -> dict:
        """End an active enforcement session.

        Args:
            session_id: The session to end.
            what_changed: What changed during this session (for handoff).
            what_others_need: What other agents need to know.
            decisions_deferred: Questions needing human input.
            next_priorities: What to do next, in order.
        """
        db = ctx.lifespan_context["db"]
        return await handle_end_session(
            db, session_id,
            what_changed=what_changed,
            what_others_need=what_others_need,
            decisions_deferred=decisions_deferred,
            next_priorities=next_priorities,
        )
