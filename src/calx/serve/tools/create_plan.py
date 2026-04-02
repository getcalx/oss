"""create_plan tool -- create a new orchestration plan."""
# NOTE: Do NOT use 'from __future__ import annotations' here.
# FastMCP 3.x needs runtime-evaluated type annotations to detect Context params.


import json

from calx.serve.db.engine import PlanRow
from calx.serve.engine.orchestration import compute_waves, validate_file_disjoint


async def handle_create_plan(
    db: object,
    task_description: str,
    chunks_json: str,
    dependency_edges_json: str,
    soft_cap: int | None = None,
) -> dict:
    """Create a new plan with chunks and dependency graph.

    Validates file-disjoint constraint, flags oversized chunks,
    computes waves, stores plan.

    Returns: {status, plan_id, waves, chunks, warnings}
    """
    chunks = json.loads(chunks_json)
    edges = json.loads(dependency_edges_json)

    # Set default status on all chunks
    for chunk in chunks:
        chunk.setdefault("status", "pending")
        chunk.setdefault("block_reason", None)

    warnings = []

    # Validate file-disjoint
    disjoint_warnings = validate_file_disjoint(chunks)
    for w in disjoint_warnings:
        warnings.append(
            f"File conflict: {w['file']} shared by chunks {', '.join(w['chunks'])}"
        )

    # Determine soft_cap
    if soft_cap is None:
        session = await db.get_active_session()
        soft_cap = session.soft_cap if session else 200000

    # Flag oversized chunks
    for chunk in chunks:
        est = chunk.get("estimated_tokens", 0)
        if est > soft_cap:
            warnings.append(
                f"Chunk {chunk['id']} estimated at {est} tokens, "
                f"exceeds soft cap of {soft_cap}. Consider splitting."
            )

    # Compute waves
    waves = compute_waves(chunks, edges)

    plan = PlanRow(
        task_description=task_description,
        chunks=json.dumps(chunks),
        dependency_edges=json.dumps(edges),
    )
    plan_id = await db.insert_plan(plan)

    return {
        "status": "ok",
        "plan_id": plan_id,
        "waves": len(waves),
        "chunks": len(chunks),
        "warnings": warnings,
    }


def register_create_plan_tool(mcp: object) -> None:
    """Register create_plan MCP tool."""
    from fastmcp import Context

    @mcp.tool()
    async def create_plan(
        task_description: str,
        chunks: str,
        dependency_edges: str,
        ctx: Context = None,
    ) -> dict:
        """Create a new orchestration plan with chunks and dependency graph.

        Args:
            task_description: What the plan accomplishes.
            chunks: JSON array of chunk objects [{id, description, files, acceptance_criteria, prohibitions, domain, role, estimated_tokens, depends_on}].
            dependency_edges: JSON array of [from_chunk_id, to_chunk_id] pairs.
        """
        db = ctx.lifespan_context["db"]
        return await handle_create_plan(db, task_description, chunks, dependency_edges)
