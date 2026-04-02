"""compile_rule tool -- mark a rule as compiled (replaced by mechanism)."""
# NOTE: Do NOT use 'from __future__ import annotations' here.
# FastMCP 3.x needs runtime-evaluated type annotations to detect Context params.

from datetime import datetime, timezone

from calx.serve.db.engine import CompilationEventRow

VALID_MECHANISM_TYPES = {
    "code_change", "config_change", "hook_addition", "architecture_change",
}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


async def handle_compile_rule(
    db: object,
    rule_id: str,
    mechanism_type: str,
    mechanism_description: str,
    mechanism_reference: str | None = None,
) -> dict:
    """Core handler for compile_rule tool."""
    if mechanism_type not in VALID_MECHANISM_TYPES:
        return {
            "status": "error",
            "message": f"Invalid mechanism_type '{mechanism_type}'. Must be one of: {', '.join(sorted(VALID_MECHANISM_TYPES))}",
        }

    rule = await db.get_rule(rule_id)
    if not rule:
        return {"status": "not_found"}

    # Compute rule age
    now = datetime.now(timezone.utc)
    try:
        created = datetime.fromisoformat(rule.created_at.replace("Z", "+00:00"))
        rule_age_days = (now - created).days
    except (ValueError, AttributeError):
        rule_age_days = 0

    # Get the source correction chain length
    correction_chain_length = 0
    if rule.source_correction_id:
        correction = await db.get_correction(rule.source_correction_id)
        if correction:
            correction_chain_length = correction.recurrence_count

    # Get learning mode from rule (may need to check column existence)
    learning_mode_before = getattr(rule, "learning_mode", "unknown")
    if learning_mode_before is None:
        learning_mode_before = "unknown"

    # Create compilation event
    event = CompilationEventRow(
        rule_id=rule_id,
        source_correction_id=rule.source_correction_id,
        rule_text=rule.rule_text,
        learning_mode_before=learning_mode_before,
        mechanism_type=mechanism_type,
        mechanism_description=mechanism_description,
        mechanism_reference=mechanism_reference,
        recurrence_count_at_compilation=correction_chain_length,
        rule_age_days=rule_age_days,
        correction_chain_length=correction_chain_length,
        created_at=_now(),
    )
    event_id = await db.insert_compilation_event(event)

    # Archive the rule
    await db.update_rule(
        rule_id,
        active=0,
        health_status="compiled",
        compiled_at=_now(),
        compiled_via=mechanism_description,
        compiled_from_mode=learning_mode_before,
        recurrence_at_compilation=correction_chain_length,
    )

    return {
        "status": "ok",
        "compilation_id": event_id,
        "rule_id": rule_id,
        "rule_archived": True,
        "message": "Rule compiled. Monitoring for post-compilation recurrence.",
    }


def register_compile_rule_tool(mcp: object) -> None:
    """Register compile_rule MCP tool."""
    from fastmcp import Context

    @mcp.tool()
    async def compile_rule(
        rule_id: str,
        mechanism_type: str,
        mechanism_description: str,
        mechanism_reference: str | None = None,
        ctx: Context = None,
    ) -> dict:
        """Mark a rule as compiled: replaced by an architectural mechanism.

        Args:
            rule_id: The rule being compiled.
            mechanism_type: code_change, config_change, hook_addition, or architecture_change.
            mechanism_description: Human description of what replaced the rule.
            mechanism_reference: Optional commit hash, file path, or PR.
        """
        db = ctx.lifespan_context["db"]
        return await handle_compile_rule(
            db, rule_id, mechanism_type, mechanism_description, mechanism_reference,
        )
