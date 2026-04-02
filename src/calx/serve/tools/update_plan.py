"""update_plan tool -- update plan state."""
# NOTE: Do NOT use 'from __future__ import annotations' here.
# FastMCP 3.x needs runtime-evaluated type annotations to detect Context params.


import json

from calx.serve.engine.orchestration import (
    PHASE_ORDER,
    advance_phase,
    compute_waves,
    get_next_dispatchable,
)


async def handle_update_plan(
    db: object,
    plan_id: int,
    chunk_id: str | None = None,
    chunk_status: str | None = None,
    block_reason: str | None = None,
    spec_file: str | None = None,
    test_files: str | None = None,
    review_id: int | None = None,
) -> dict:
    """Update plan state: chunk status, metadata, auto-advance phase.

    Auto-advance rules:
    - When spec_file is set and phase=spec, advance to test
    - When test_files is set and phase=test, advance to chunk
    - When review_id is set and phase=plan, advance to build

    Returns: {status, phase, next_dispatchable, wave}
    """
    plan = await db.get_plan(plan_id)
    if not plan:
        return {"status": "not_found"}

    chunks = json.loads(plan.chunks)
    edges = json.loads(plan.dependency_edges)
    update_fields = {}

    # Update chunk status
    if chunk_id and chunk_status:
        for chunk in chunks:
            if chunk["id"] == chunk_id:
                chunk["status"] = chunk_status
                if block_reason and chunk_status == "blocked":
                    chunk["block_reason"] = block_reason
                break
        update_fields["chunks"] = json.dumps(chunks)

    # Update metadata fields
    if spec_file is not None:
        update_fields["spec_file"] = spec_file
    if test_files is not None:
        update_fields["test_files"] = test_files
    if review_id is not None:
        update_fields["review_id"] = review_id

    if update_fields:
        await db.update_plan(plan_id, **update_fields)

    # Auto-advance phase based on metadata changes
    plan_after = await db.get_plan(plan_id)
    phase = plan_after.phase

    auto_advance_map = {
        "spec": lambda p: p.spec_file is not None,
        "test": lambda p: p.test_files is not None,
        "plan": lambda p: p.review_id is not None,
    }

    if phase in auto_advance_map and auto_advance_map[phase](plan_after):
        new_phase, msg = await advance_phase(db, plan_id)
        phase = new_phase

    # Get next dispatchable
    chunks_after = json.loads(plan_after.chunks) if plan_after else chunks
    edges_after = json.loads(plan_after.dependency_edges) if plan_after else edges
    wave_after = plan_after.current_wave if plan_after else plan.current_wave

    # Use 0-indexed for get_next_dispatchable
    next_dispatchable = get_next_dispatchable(chunks_after, edges_after, wave_after - 1)

    return {
        "status": "ok",
        "phase": phase,
        "wave": wave_after,
        "next_dispatchable": next_dispatchable,
    }


def register_update_plan_tool(mcp: object) -> None:
    """Register update_plan MCP tool."""
    from fastmcp import Context

    @mcp.tool()
    async def update_plan(
        plan_id: int,
        chunk_id: str | None = None,
        chunk_status: str | None = None,
        block_reason: str | None = None,
        spec_file: str | None = None,
        test_files: str | None = None,
        review_id: int | None = None,
        ctx: Context = None,
    ) -> dict:
        """Update plan state: mark chunks complete/blocked, set metadata, auto-advance phase.

        Args:
            plan_id: Which plan to update.
            chunk_id: Optional chunk to update status for.
            chunk_status: New status: pending, in_progress, done, blocked.
            block_reason: Why the chunk is blocked (required if blocked).
            spec_file: Path to spec file (auto-advances spec->test phase).
            test_files: JSON array of test file paths (auto-advances test->chunk phase).
            review_id: Foil review ID (auto-advances plan->build phase).
        """
        db = ctx.lifespan_context["db"]
        return await handle_update_plan(
            db, plan_id, chunk_id, chunk_status, block_reason,
            spec_file, test_files, review_id,
        )
