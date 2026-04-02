"""Tests for update_board MCP tool."""
from __future__ import annotations

import pytest


class TestUpdateBoard:

    @pytest.mark.asyncio
    async def test_create_board_item(self, db):
        from calx.serve.tools.update_board import handle_update_board

        result = await handle_update_board(
            db,
            description="Build auth module",
            status="in_progress",
            domain="general",
        )
        assert result["status"] == "ok"
        assert "board_item_id" in result

    @pytest.mark.asyncio
    async def test_invalid_status(self, db):
        from calx.serve.tools.update_board import handle_update_board

        result = await handle_update_board(
            db,
            description="Task",
            status="invalid",
            domain="general",
        )
        assert result["status"] == "error"
