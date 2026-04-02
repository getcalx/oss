"""update_board tool -- create or update board state items."""
# NOTE: Do NOT use 'from __future__ import annotations' here.
# FastMCP 3.x needs runtime-evaluated type annotations to detect Context params.

from datetime import datetime, timezone

from calx.serve.db.engine import BoardStateRow

VALID_STATUSES = {"blocked", "in_progress", "needs_review", "done"}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


async def handle_update_board(
    db: object,
    description: str,
    status: str,
    domain: str,
    blocked_reason: str | None = None,
) -> dict:
    """Core handler for update_board tool."""
    if status not in VALID_STATUSES:
        return {
            "status": "error",
            "message": f"Invalid status '{status}'. Must be one of: {', '.join(sorted(VALID_STATUSES))}",
        }

    if status == "blocked" and not blocked_reason:
        return {
            "status": "error",
            "message": "blocked_reason is required when status is 'blocked'",
        }

    item = BoardStateRow(
        domain=domain,
        description=description,
        status=status,
        blocked_reason=blocked_reason,
        updated_at=_now(),
    )
    item_id = await db.insert_board_item(item)

    return {"status": "ok", "board_item_id": item_id}


def register_update_board_tool(mcp: object) -> None:
    """Register update_board MCP tool."""
    from fastmcp import Context

    @mcp.tool()
    async def update_board(
        description: str,
        status: str,
        domain: str,
        blocked_reason: str | None = None,
        ctx: Context = None,
    ) -> dict:
        """Create or update a board state item.

        Args:
            description: Work item description.
            status: blocked, in_progress, needs_review, or done.
            domain: Owning domain.
            blocked_reason: Why it's blocked (required if status=blocked).
        """
        db = ctx.lifespan_context["db"]
        return await handle_update_board(db, description, status, domain, blocked_reason)
