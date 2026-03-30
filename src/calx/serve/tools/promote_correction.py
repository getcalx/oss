"""promote_correction tool -- promote a correction to an active rule."""
# NOTE: Do NOT use 'from __future__ import annotations' here.
# FastMCP 3.x needs runtime-evaluated type annotations to detect Context params.

from calx.serve.db.engine import RuleRow


async def handle_promote_correction(
    db: object,
    correction_id: str,
    rule_text: str,
) -> dict:
    """Core handler for promote_correction tool."""
    correction = await db.get_correction(correction_id)  # type: ignore[attr-defined]
    if not correction:
        return {"status": "not_found"}

    if correction.quarantined:
        return {"status": "error", "message": "Cannot promote quarantined correction."}

    if correction.promoted:
        return {"status": "already_promoted", "message": "Correction already promoted."}

    rule_id = await db.next_rule_id(correction.domain)  # type: ignore[attr-defined]
    await db.insert_rule(RuleRow(  # type: ignore[attr-defined]
        id=rule_id,
        rule_text=rule_text,
        domain=correction.domain,
        surface=correction.surface,
        source_correction_id=correction_id,
        active=1,
    ))
    await db.update_correction(correction_id, promoted=1)  # type: ignore[attr-defined]

    return {"status": "ok", "rule_id": rule_id}


def register_promote_correction_tool(mcp: object) -> None:
    """Register promote_correction MCP tool."""
    from fastmcp import Context

    @mcp.tool()  # type: ignore[attr-defined]
    async def promote_correction(
        correction_id: str,
        rule_text: str,
        ctx: Context = None,
    ) -> dict:
        """Promote a correction to an active rule.

        Args:
            correction_id: The correction to promote (e.g., "C003").
            rule_text: The rule text to create.
        """
        db = ctx.lifespan_context["db"]
        return await handle_promote_correction(db, correction_id, rule_text)
