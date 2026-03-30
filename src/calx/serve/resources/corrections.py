"""calx://corrections{?domain} -- recent corrections."""
# NOTE: Do NOT use 'from __future__ import annotations' here.
# FastMCP 3.x needs runtime-evaluated type annotations to detect Context params.

from calx.serve.db.engine import CorrectionRow


def format_corrections_markdown(corrections: list[CorrectionRow]) -> str:
    """Format corrections as markdown."""
    if not corrections:
        return "No recent corrections."
    lines = []
    for c in corrections:
        recurrence = f" (x{c.recurrence_count})" if c.recurrence_count > 1 else ""
        lines.append(
            f"### {c.id} [{c.domain}/{c.category}]{recurrence}\n\n"
            f"{c.correction}\n\n"
            f"Surface: {c.surface} | Severity: {c.severity} | "
            f"Confidence: {c.confidence}"
        )
    return "\n\n".join(lines)


async def _get_corrections(db: object, domain: str | None = None) -> str:
    corrections = await db.find_corrections(domain=domain, limit=50)  # type: ignore[attr-defined]
    return format_corrections_markdown(corrections)


def register_corrections_resource(mcp: object) -> None:
    """Register calx://corrections{?domain} resource."""
    from fastmcp import Context

    @mcp.resource("calx://corrections{?domain}")  # type: ignore[attr-defined]
    async def get_corrections(ctx: Context, domain: str | None = None) -> str:
        """Recent corrections, optionally filtered by domain."""
        db = ctx.lifespan_context["db"]
        return await _get_corrections(db, domain=domain)
