"""redispatch_chunk tool -- generate updated prompt for a blocked chunk."""
# NOTE: Do NOT use 'from __future__ import annotations' here.

import json

from calx.serve.engine.dispatch import build_redispatch_prompt


async def handle_redispatch_chunk(
    db: object,
    plan_id: int,
    chunk_id: str,
) -> dict:
    """Generate an updated prompt for a blocked chunk.

    Refuses if chunk is not blocked.
    Marks chunk back to in_progress.
    """
    plan = await db.get_plan(plan_id)
    if not plan:
        return {"status": "not_found", "message": "plan not found"}

    chunks = json.loads(plan.chunks)
    chunk = None
    for c in chunks:
        if c["id"] == chunk_id:
            chunk = c
            break

    if not chunk:
        return {"status": "not_found", "message": f"chunk {chunk_id} not found in plan"}

    if chunk.get("status") != "blocked":
        return {"status": "error", "message": f"chunk {chunk_id} is not blocked (status: {chunk.get('status')})"}

    # Mark chunk back to in_progress
    chunk["status"] = "in_progress"
    await db.update_plan(plan_id, chunks=json.dumps(chunks))

    # Build redispatch prompt
    plan_data = {
        "task_description": plan.task_description,
        "chunks": chunks,
        "dependency_edges": json.loads(plan.dependency_edges),
    }
    prompt = await build_redispatch_prompt(db, plan_data, chunk)

    return {
        "status": "ok",
        "prompt": prompt,
        "estimated_tokens": chunk.get("estimated_tokens", 0),
        "chunk_id": chunk_id,
    }


def register_redispatch_chunk_tool(mcp: object) -> None:
    """Register redispatch_chunk MCP tool."""
    from fastmcp import Context

    @mcp.tool()
    async def redispatch_chunk(
        plan_id: int,
        chunk_id: str,
        ctx: Context = None,
    ) -> dict:
        """Generate an updated dispatch prompt for a blocked chunk.

        Args:
            plan_id: Which plan the chunk belongs to.
            chunk_id: Which blocked chunk to re-dispatch.
        """
        db = ctx.lifespan_context["db"]
        return await handle_redispatch_chunk(db, plan_id, chunk_id)
