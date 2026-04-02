"""Tests for create_plan MCP tool."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from calx.serve.db.engine import SessionRow


class TestCreatePlan:

    @pytest.mark.asyncio
    async def test_create_plan_stores_plan(self, db):
        from calx.serve.tools.create_plan import handle_create_plan

        chunks = [
            {
                "id": "a",
                "description": "task A",
                "files": ["src/a.py"],
                "acceptance_criteria": ["A works"],
                "prohibitions": [],
                "domain": "general",
                "role": "builder",
                "estimated_tokens": 30000,
                "depends_on": [],
            },
        ]
        result = await handle_create_plan(
            db, "Test plan", json.dumps(chunks), json.dumps([]),
        )
        assert result["status"] == "ok"
        assert result["plan_id"] is not None
        assert result["chunks"] == 1
        assert result["waves"] >= 1
        assert result["warnings"] == []

        # Verify persisted in DB
        plan = await db.get_plan(result["plan_id"])
        assert plan is not None
        assert plan.task_description == "Test plan"
        stored_chunks = json.loads(plan.chunks)
        assert len(stored_chunks) == 1
        assert stored_chunks[0]["status"] == "pending"

    @pytest.mark.asyncio
    async def test_create_plan_validates_file_disjoint(self, db):
        from calx.serve.tools.create_plan import handle_create_plan

        chunks = [
            {
                "id": "a",
                "description": "task A",
                "files": ["src/shared.py", "src/a.py"],
                "acceptance_criteria": ["A works"],
                "prohibitions": [],
                "domain": "general",
                "role": "builder",
                "estimated_tokens": 10000,
                "depends_on": [],
            },
            {
                "id": "b",
                "description": "task B",
                "files": ["src/shared.py", "src/b.py"],
                "acceptance_criteria": ["B works"],
                "prohibitions": [],
                "domain": "general",
                "role": "builder",
                "estimated_tokens": 10000,
                "depends_on": [],
            },
        ]
        result = await handle_create_plan(
            db, "Overlap plan", json.dumps(chunks), json.dumps([]),
        )
        assert result["status"] == "ok"
        assert len(result["warnings"]) >= 1
        assert any("src/shared.py" in w for w in result["warnings"])
        assert any("a" in w and "b" in w for w in result["warnings"])

    @pytest.mark.asyncio
    async def test_create_plan_flags_oversized_chunks(self, db):
        from calx.serve.tools.create_plan import handle_create_plan

        chunks = [
            {
                "id": "big",
                "description": "huge chunk",
                "files": ["src/big.py"],
                "acceptance_criteria": ["done"],
                "prohibitions": [],
                "domain": "general",
                "role": "builder",
                "estimated_tokens": 300000,
                "depends_on": [],
            },
            {
                "id": "small",
                "description": "small chunk",
                "files": ["src/small.py"],
                "acceptance_criteria": ["done"],
                "prohibitions": [],
                "domain": "general",
                "role": "builder",
                "estimated_tokens": 50000,
                "depends_on": [],
            },
        ]
        result = await handle_create_plan(
            db, "Big plan", json.dumps(chunks), json.dumps([]),
        )
        assert result["status"] == "ok"
        # Only the oversized chunk should trigger a warning
        assert len(result["warnings"]) == 1
        assert "big" in result["warnings"][0]
        assert "300000" in result["warnings"][0]
        assert "200000" in result["warnings"][0]

    @pytest.mark.asyncio
    async def test_create_plan_uses_session_soft_cap(self, db):
        """soft_cap from active session overrides hardcoded 200000."""
        from calx.serve.tools.create_plan import handle_create_plan

        # Register a session with soft_cap=50000
        session = SessionRow(
            id="s-softcap",
            surface="claude-code",
            surface_type="cli",
            soft_cap=50000,
        )
        await db.insert_session(session)

        chunks = [
            {
                "id": "big",
                "description": "oversized for 50k",
                "files": ["src/big.py"],
                "acceptance_criteria": ["done"],
                "prohibitions": [],
                "domain": "general",
                "role": "builder",
                "estimated_tokens": 60000,
                "depends_on": [],
            },
        ]
        result = await handle_create_plan(
            db, "Soft cap plan", json.dumps(chunks), json.dumps([]),
        )
        assert result["status"] == "ok"
        assert len(result["warnings"]) == 1
        assert "50000" in result["warnings"][0]
        assert "60000" in result["warnings"][0]

    @pytest.mark.asyncio
    async def test_create_plan_explicit_soft_cap_overrides_session(self, db):
        """Explicit soft_cap parameter takes precedence over session."""
        from calx.serve.tools.create_plan import handle_create_plan

        # Register a session with soft_cap=200000
        session = SessionRow(
            id="s-explicit",
            surface="claude-code",
            surface_type="cli",
            soft_cap=200000,
        )
        await db.insert_session(session)

        chunks = [
            {
                "id": "mid",
                "description": "fits 200k but not 40k",
                "files": ["src/mid.py"],
                "acceptance_criteria": ["done"],
                "prohibitions": [],
                "domain": "general",
                "role": "builder",
                "estimated_tokens": 60000,
                "depends_on": [],
            },
        ]
        result = await handle_create_plan(
            db, "Explicit cap plan", json.dumps(chunks), json.dumps([]),
            soft_cap=40000,
        )
        assert result["status"] == "ok"
        assert len(result["warnings"]) == 1
        assert "40000" in result["warnings"][0]
