"""Tests for redispatch_chunk tool."""
from __future__ import annotations

import json

import pytest

from calx.serve.tools.create_plan import handle_create_plan
from calx.serve.tools.redispatch_chunk import handle_redispatch_chunk
from tests.serve.conftest import make_rule


def _make_chunks(status="pending", block_reason=None):
    chunk = {
        "id": "a", "description": "Build models", "files": ["src/models.py"],
        "acceptance_criteria": ["Models exist", "Tests pass"], "prohibitions": [],
        "domain": "general", "role": "builder", "estimated_tokens": 30000,
        "depends_on": [], "status": status,
    }
    if block_reason:
        chunk["block_reason"] = block_reason
    return [chunk]


class TestRedispatchChunk:

    @pytest.mark.asyncio
    async def test_redispatch_refuses_if_not_blocked(self, db):
        """Chunk with status=done returns error, not redispatch."""
        chunks = _make_chunks(status="done")
        result = await handle_create_plan(db, "Test", json.dumps(chunks), "[]")
        plan_id = result["plan_id"]

        result = await handle_redispatch_chunk(db, plan_id, "a")
        assert result["status"] == "error"
        assert "not blocked" in result["message"]

    @pytest.mark.asyncio
    async def test_redispatch_prompt_includes_block_reason(self, db):
        """Blocked chunk with reason produces prompt containing the reason."""
        chunks = _make_chunks(status="blocked", block_reason="Import error in models.py")
        result = await handle_create_plan(db, "Test", json.dumps(chunks), "[]")
        plan_id = result["plan_id"]

        result = await handle_redispatch_chunk(db, plan_id, "a")
        assert result["status"] == "ok"
        assert "Import error in models.py" in result["prompt"]

    @pytest.mark.asyncio
    async def test_redispatch_marks_in_progress(self, db):
        """Blocked chunk status changes to in_progress after redispatch."""
        chunks = _make_chunks(status="blocked", block_reason="Failed tests")
        result = await handle_create_plan(db, "Test", json.dumps(chunks), "[]")
        plan_id = result["plan_id"]

        result = await handle_redispatch_chunk(db, plan_id, "a")
        assert result["status"] == "ok"

        # Verify chunk is in_progress in DB
        plan = await db.get_plan(plan_id)
        stored_chunks = json.loads(plan.chunks)
        assert stored_chunks[0]["status"] == "in_progress"

    @pytest.mark.asyncio
    async def test_redispatch_chunk_not_found(self, db):
        """Nonexistent chunk returns not_found."""
        chunks = _make_chunks(status="blocked", block_reason="reason")
        result = await handle_create_plan(db, "Test", json.dumps(chunks), "[]")
        plan_id = result["plan_id"]

        result = await handle_redispatch_chunk(db, plan_id, "nonexistent")
        assert result["status"] == "not_found"

    @pytest.mark.asyncio
    async def test_redispatch_plan_not_found(self, db):
        """Nonexistent plan returns not_found."""
        result = await handle_redispatch_chunk(db, 999, "a")
        assert result["status"] == "not_found"

    @pytest.mark.asyncio
    async def test_redispatch_prompt_contains_rules(self, db):
        """Redispatch prompt includes domain rules."""
        await db.insert_rule(make_rule(id="general-R001", rule_text="Always test first", domain="general", role="builder"))
        chunks = _make_chunks(status="blocked", block_reason="Tests failing")
        result = await handle_create_plan(db, "Test", json.dumps(chunks), "[]")
        plan_id = result["plan_id"]

        result = await handle_redispatch_chunk(db, plan_id, "a")
        assert result["status"] == "ok"
        assert "Always test first" in result["prompt"]

    @pytest.mark.asyncio
    async def test_redispatch_pending_chunk_refuses(self, db):
        """Chunk with status=pending is not blocked, returns error."""
        chunks = _make_chunks(status="pending")
        result = await handle_create_plan(db, "Test", json.dumps(chunks), "[]")
        plan_id = result["plan_id"]

        result = await handle_redispatch_chunk(db, plan_id, "a")
        assert result["status"] == "error"
        assert "not blocked" in result["message"]
