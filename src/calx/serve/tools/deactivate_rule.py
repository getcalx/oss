"""deactivate_rule tool -- deactivate an active rule."""
# NOTE: Do NOT use 'from __future__ import annotations' here.
# FastMCP 3.x needs runtime-evaluated type annotations to detect Context params.


async def handle_deactivate_rule(
    db: object,
    rule_id: str,
    reason: str | None = None,
) -> dict:
    """Core handler for deactivate_rule tool."""
    rule = await db.get_rule(rule_id)
    if not rule:
        return {"status": "not_found"}

    update_fields = {"active": 0, "health_status": "archived"}
    if reason:
        update_fields["deactivation_reason"] = reason
    await db.update_rule(rule_id, **update_fields)

    return {
        "status": "ok",
        "rule_id": rule_id,
        "active": 0,
    }


def register_deactivate_rule_tool(mcp: object) -> None:
    """Register deactivate_rule MCP tool."""
    from fastmcp import Context

    @mcp.tool()
    async def deactivate_rule(
        rule_id: str,
        reason: str | None = None,
        ctx: Context = None,
    ) -> dict:
        """Deactivate an active rule.

        Args:
            rule_id: ID of the rule to deactivate.
            reason: Optional reason for deactivation.
        """
        db = ctx.lifespan_context["db"]
        return await handle_deactivate_rule(db, rule_id, reason)
