"""dispatch_chunk tool -- generate dispatch prompt for a plan chunk."""
# NOTE: Do NOT use 'from __future__ import annotations' here.

import json

from calx.serve.engine.dispatch import build_dispatch_prompt
from calx.serve.engine.orchestration import PHASE_ORDER


async def handle_dispatch_chunk(
    db: object,
    plan_id: int,
    chunk_id: str,
) -> dict:
    """Generate a dispatch prompt for a chunk.

    Refuses if plan phase has not reached 'build'.
    Marks chunk as in_progress.
    Returns assembled prompt + estimated_tokens.
    """
    plan = await db.get_plan(plan_id)
    if not plan:
        return {"status": "not_found", "message": "plan not found"}

    # Check phase >= build
    phase_idx = PHASE_ORDER.index(plan.phase)
    build_idx = PHASE_ORDER.index("build")
    if phase_idx < build_idx:
        return {
            "status": "phase_error",
            "message": f"Plan is in {plan.phase} phase. Complete {plan.phase} before dispatching.",
        }

    chunks = json.loads(plan.chunks)

    # Check chunk belongs to current or earlier wave
    from calx.serve.engine.orchestration import compute_waves
    edges = json.loads(plan.dependency_edges)
    waves = compute_waves(chunks, edges)
    chunk_wave = None
    for i, wave in enumerate(waves):
        if chunk_id in wave:
            chunk_wave = i + 1  # 1-indexed
            break

    if chunk_wave is not None and chunk_wave > plan.current_wave:
        return {
            "status": "wave_blocked",
            "message": f"BLOCKED: Wave {plan.current_wave} verification incomplete. Cannot dispatch wave {chunk_wave} chunk.",
        }

    chunk = None
    for c in chunks:
        if c["id"] == chunk_id:
            chunk = c
            break

    if not chunk:
        return {"status": "not_found", "message": f"chunk {chunk_id} not found in plan"}

    # Mark chunk as in_progress
    chunk["status"] = "in_progress"
    await db.update_plan(plan_id, chunks=json.dumps(chunks))

    # Build prompt
    plan_data = {
        "task_description": plan.task_description,
        "chunks": chunks,
        "dependency_edges": json.loads(plan.dependency_edges),
    }
    prompt = await build_dispatch_prompt(db, plan_data, chunk)

    return {
        "status": "ok",
        "prompt": prompt,
        "estimated_tokens": chunk.get("estimated_tokens", 0),
        "chunk_id": chunk_id,
    }


def register_dispatch_chunk_tool(mcp: object) -> None:
    """Register dispatch_chunk MCP tool."""
    from fastmcp import Context

    @mcp.tool()
    async def dispatch_chunk(
        plan_id: int,
        chunk_id: str,
        ctx: Context = None,
    ) -> dict:
        """Generate a complete dispatch prompt for a plan chunk.

        Args:
            plan_id: Which plan the chunk belongs to.
            chunk_id: Which chunk to dispatch.
        """
        db = ctx.lifespan_context["db"]
        return await handle_dispatch_chunk(db, plan_id, chunk_id)
