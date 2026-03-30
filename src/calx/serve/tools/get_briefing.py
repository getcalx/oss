"""get_briefing tool -- fallback for MCP clients that don't support Resources."""
# NOTE: Do NOT use 'from __future__ import annotations' here.
# FastMCP 3.x needs runtime-evaluated type annotations to detect Context params.

from calx.serve.resources.briefing import build_briefing


def register_get_briefing_tool(mcp: object) -> None:
    """Register get_briefing MCP tool (resource fallback)."""
    from fastmcp import Context

    @mcp.tool()  # type: ignore[attr-defined]
    async def get_briefing(
        surface: str = "default",
        ctx: Context = None,
    ) -> str:
        """Fetch the full briefing for a surface.

        Tool-based fallback for MCP clients that don't support Resources.
        Same logic as calx://briefing/{surface} Resource.

        Args:
            surface: Which surface to brief (maps to domain set via SURFACE_DOMAIN_MAP).
        """
        db = ctx.lifespan_context["db"]
        return await build_briefing(db, surface)
