"""Tests for calx://board resource."""
from __future__ import annotations

import pytest

from calx.serve.db.engine import BoardStateRow


@pytest.mark.asyncio
async def test_board_resource_empty(db):
    from calx.serve.resources.board import build_board

    result = await build_board(db)
    assert "No board items" in result


@pytest.mark.asyncio
async def test_board_resource_with_items(db):
    from calx.serve.resources.board import build_board

    await db.insert_board_item(BoardStateRow(
        domain="general", description="Build Session 2",
        status="in_progress",
    ))
    await db.insert_board_item(BoardStateRow(
        domain="strategy", description="Prep pitch deck",
        status="blocked", blocked_reason="Waiting on metrics",
    ))
    result = await build_board(db)
    assert "Build Session 2" in result
    assert "in_progress" in result
    assert "Prep pitch deck" in result
    assert "blocked" in result


@pytest.mark.asyncio
async def test_board_resource_filters_by_domain(db):
    from calx.serve.resources.board import build_board

    await db.insert_board_item(BoardStateRow(
        domain="general", description="General task", status="done",
    ))
    await db.insert_board_item(BoardStateRow(
        domain="strategy", description="Strategy task", status="done",
    ))
    result = await build_board(db, domain="general")
    assert "General task" in result
    assert "Strategy task" not in result
