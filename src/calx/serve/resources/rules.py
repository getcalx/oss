"""calx://rules{?domain} -- active promoted rules."""
# NOTE: Do NOT use 'from __future__ import annotations' here.
# FastMCP 3.x needs runtime-evaluated type annotations to detect Context params.

from calx.serve.db.engine import RuleRow


def format_rules_markdown(rules: list[RuleRow]) -> str:
    """Format rules as markdown."""
    if not rules:
        return "No active rules."
    lines = []
    for r in rules:
        surface_tag = f" [{r.surface}]" if r.surface else ""
        lines.append(f"### {r.id}{surface_tag}\n\n{r.rule_text}")
    return "\n\n".join(lines)


async def _get_rules(db: object, domain: str | None = None) -> str:
    rules = await db.find_rules(domain=domain, active_only=True)  # type: ignore[attr-defined]
    if not rules:
        suffix = f" for domain {domain}" if domain else ""
        return f"No active rules{suffix}."
    return format_rules_markdown(rules)


def register_rules_resource(mcp: object) -> None:
    """Register calx://rules{?domain} resource."""
    from fastmcp import Context

    @mcp.resource("calx://rules{?domain}")  # type: ignore[attr-defined]
    async def get_rules(ctx: Context, domain: str | None = None) -> str:
        """Active promoted rules, optionally filtered by domain."""
        db = ctx.lifespan_context["db"]
        return await _get_rules(db, domain=domain)
