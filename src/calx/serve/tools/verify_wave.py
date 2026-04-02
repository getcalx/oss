"""verify_wave tool -- run verification checks on a completed wave."""
# NOTE: Do NOT use 'from __future__ import annotations' here.

import json
from datetime import datetime, timezone

from calx.serve.engine.verification import run_wave_verification


async def handle_verify_wave(
    db: object,
    plan_id: int,
    wave_id: int,
    manual_notes: str | None = None,
) -> dict:
    """Run verification checks for a wave and record results.

    Runs import, test, and duplicate checks. Records results in plan's
    wave_verification JSON. Blocks next wave on failure, unblocks on pass.
    """
    plan = await db.get_plan(plan_id)
    if not plan:
        return {"status": "not_found", "message": "plan not found"}

    plan_data = {
        "chunks": plan.chunks,
        "dependency_edges": plan.dependency_edges,
        "current_wave": plan.current_wave,
    }

    result = await run_wave_verification(plan_data, wave_id, manual_notes)

    # Record results in wave_verification JSON
    wv = json.loads(plan.wave_verification) if plan.wave_verification else {}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    wv[str(wave_id)] = {
        "overall": result["overall"],
        "notes": manual_notes or "",
        "verified_at": now,
        "import_check": result["import_check"],
        "test_check": result["test_check"],
        "duplicate_check": result["duplicate_check"],
    }

    # On pass, advance current_wave to unlock next wave
    if result["overall"] == "pass":
        edges = json.loads(plan.dependency_edges)
        chunks_list = json.loads(plan.chunks)
        from calx.serve.engine.orchestration import compute_waves
        waves = compute_waves(chunks_list, edges)
        if wave_id < len(waves):
            await db.update_plan(plan_id, wave_verification=json.dumps(wv), current_wave=wave_id + 1)
        else:
            await db.update_plan(plan_id, wave_verification=json.dumps(wv))
    else:
        await db.update_plan(plan_id, wave_verification=json.dumps(wv))

    result["status"] = "ok"
    result["wave_id"] = wave_id
    return result


def register_verify_wave_tool(mcp: object) -> None:
    """Register verify_wave MCP tool."""
    from fastmcp import Context

    @mcp.tool()
    async def verify_wave(
        plan_id: int,
        wave_id: int,
        manual_notes: str | None = None,
        ctx: Context = None,
    ) -> dict:
        """Run verification checks on a completed wave.

        Args:
            plan_id: Which plan the wave belongs to.
            wave_id: Which wave to verify (1-indexed).
            manual_notes: Optional manual verification notes (pass/fail with findings).
        """
        db = ctx.lifespan_context["db"]
        return await handle_verify_wave(db, plan_id, wave_id, manual_notes)
