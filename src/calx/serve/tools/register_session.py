"""register_session tool -- create a new enforcement session."""
# NOTE: Do NOT use 'from __future__ import annotations' here.
# FastMCP 3.x needs runtime-evaluated type annotations to detect Context params.

import uuid as uuid_mod
from datetime import datetime, timezone
from pathlib import Path

from calx.serve.db.engine import SessionRow
from calx.serve.engine.state_writer import (
    remove_session_state,
    write_active_session,
    write_session_state,
)
from calx.serve.engine.bootstrap import bootstrap_session
from calx.serve.engine.compilation import check_verification_status
from calx.serve.resources.briefing import build_briefing


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


async def handle_register_session(
    db: object,
    surface: str,
    session_id: str | None = None,
    soft_cap: int = 200000,
    ceiling: int = 250000,
    server_fail_mode: str = "open",
    collapse_fail_mode: str = "closed",
    state_dir: Path | None = None,
) -> dict:
    """Core handler for register_session tool."""
    session_id = session_id or f"sess_{uuid_mod.uuid4().hex[:12]}"

    # End any active session first
    active = await db.get_active_session()
    if active and active.id != session_id:
        await db.update_session(active.id, ended_at=_now())
        if state_dir:
            remove_session_state(state_dir, active.id)

    # Run bootstrap before creating session
    bootstrap = await bootstrap_session(db, state_dir=state_dir)
    verification = await check_verification_status(db)
    bootstrap_data = {
        "dirty_exit": bootstrap.dirty_exit,
        "dirty_session_id": bootstrap.dirty_session_id,
        "staleness_warning": bootstrap.staleness_warning,
        "handoff": {
            "what_changed": bootstrap.last_handoff.what_changed,
            "what_others_need": bootstrap.last_handoff.what_others_need,
            "decisions_deferred": bootstrap.last_handoff.decisions_deferred,
            "next_priorities": bootstrap.last_handoff.next_priorities,
        } if bootstrap.last_handoff else None,
        "rules_needing_attention": [
            {"id": r.id, "health_status": r.health_status, "health_score": r.health_score}
            for r in bootstrap.rules_needing_attention
        ],
        "verification_results": [
            {"rule_id": v.rule_id, "status": v.status, "days_remaining": v.days_remaining}
            for v in verification
        ],
    }

    # Idempotent: return existing if already registered
    existing = await db.get_session(session_id)
    if existing:
        briefing = await build_briefing(db, surface)
        return {
            "status": "ok",
            "session_id": session_id,
            "briefing": briefing,
            "state_file": f".calx/state/session-{session_id}.json",
            "bootstrap": bootstrap_data,
        }

    session = SessionRow(
        id=session_id,
        surface=surface,
        surface_type=surface,
        soft_cap=soft_cap,
        ceiling=ceiling,
        server_fail_mode=server_fail_mode,
        collapse_fail_mode=collapse_fail_mode,
        started_at=_now(),
    )
    await db.insert_session(session)

    briefing = await build_briefing(db, surface)

    # Write state files
    if state_dir:
        rules = await db.find_rules(active_only=True)
        rules_data = [{"id": r.id, "text": r.rule_text} for r in rules]
        write_session_state(
            state_dir=state_dir,
            session_id=session_id,
            surface=surface,
            oriented=False,
            token_estimate=0,
            tool_call_count=0,
            soft_cap=soft_cap,
            ceiling=ceiling,
            server_fail_mode=server_fail_mode,
            collapse_fail_mode=collapse_fail_mode,
            started_at=session.started_at,
            rules=rules_data,
        )
        write_active_session(state_dir, session_id)

    return {
        "status": "ok",
        "session_id": session_id,
        "briefing": briefing,
        "state_file": f".calx/state/session-{session_id}.json",
        "bootstrap": bootstrap_data,
    }


def register_register_session_tool(mcp: object) -> None:
    """Register register_session MCP tool."""
    from fastmcp import Context

    @mcp.tool()
    async def register_session(
        surface: str,
        session_id: str | None = None,
        ctx: Context = None,
    ) -> dict:
        """Register a new enforcement session.

        Args:
            surface: The surface type (claude-code, cursor, codex, gemini).
            session_id: Optional surface-provided session ID.
        """
        db = ctx.lifespan_context["db"]
        return await handle_register_session(db, surface, session_id)
