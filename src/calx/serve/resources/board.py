"""calx://board/{?domain} -- board state resource."""
# NOTE: Do NOT use 'from __future__ import annotations' here.
# FastMCP 3.x needs runtime-evaluated type annotations to detect Context params.

from calx.serve.db.engine import BoardStateRow


async def build_board(db: object, domain: str | None = None) -> str:
    """Build the board state view."""
    items = await db.get_board_state()
    if domain:
        items = [i for i in items if i.domain == domain]

    if not items:
        return "## Board\n\nNo board items."

    lines = ["## Board\n"]
    for item in items:
        blocked = f" (blocked: {item.blocked_reason})" if item.blocked_reason else ""
        lines.append(f"- **{item.domain}** [{item.status}]: {item.description}{blocked}")
    return "\n".join(lines)


def register_board_resource(mcp: object) -> None:
    """Register calx://board resource."""
    from fastmcp import Context

    @mcp.resource("calx://board/{domain}")
    async def get_board(domain: str, ctx: Context) -> str:
        """Board state for a domain. Use 'all' for everything."""
        db = ctx.lifespan_context["db"]
        d = None if domain == "all" else domain
        return await build_board(db, domain=d)
