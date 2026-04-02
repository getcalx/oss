"""Tests for dispatch_chunk tool."""
from __future__ import annotations

import json

import pytest

from calx.serve.tools.create_plan import handle_create_plan
from calx.serve.tools.dispatch_chunk import handle_dispatch_chunk
from tests.serve.conftest import make_rule


def _make_chunks():
    return [
        {"id": "a", "description": "Build models", "files": ["src/models.py"],
         "acceptance_criteria": ["Models exist"], "prohibitions": [],
         "domain": "general", "role": "builder", "estimated_tokens": 30000, "depends_on": []}
    ]


class TestDispatchChunk:

    @pytest.mark.asyncio
    async def test_dispatch_refuses_before_build_phase(self, db):
        """dispatch_chunk refuses if plan phase < build."""
        result = await handle_create_plan(db, "Test", json.dumps(_make_chunks()), "[]")
        plan_id = result["plan_id"]

        result = await handle_dispatch_chunk(db, plan_id, "a")
        assert result["status"] == "phase_error"
        assert "spec" in result["message"]

    @pytest.mark.asyncio
    async def test_dispatch_marks_in_progress(self, db, tmp_path):
        """dispatch_chunk marks chunk as in_progress."""
        result = await handle_create_plan(db, "Test", json.dumps(_make_chunks()), "[]")
        plan_id = result["plan_id"]

        # Advance plan to build phase
        spec = tmp_path / "spec.md"
        spec.write_text("spec")
        test_file = tmp_path / "test.py"
        test_file.write_text("test")

        await db.update_plan(plan_id,
            spec_file=str(spec),
            test_files=json.dumps([str(test_file)]),
            phase="build")

        result = await handle_dispatch_chunk(db, plan_id, "a")
        assert result["status"] == "ok"
        assert "prompt" in result

        # Verify chunk is in_progress in DB
        plan = await db.get_plan(plan_id)
        chunks = json.loads(plan.chunks)
        assert chunks[0]["status"] == "in_progress"

    @pytest.mark.asyncio
    async def test_dispatch_prompt_contains_rules(self, db):
        """Dispatch prompt includes domain rules."""
        await db.insert_rule(make_rule(id="general-R001", rule_text="Always test first", domain="general", role="builder"))
        result = await handle_create_plan(db, "Test", json.dumps(_make_chunks()), "[]")
        plan_id = result["plan_id"]
        await db.update_plan(plan_id, phase="build")

        result = await handle_dispatch_chunk(db, plan_id, "a")
        assert result["status"] == "ok"
        assert "Always test first" in result["prompt"]

    @pytest.mark.asyncio
    async def test_dispatch_prompt_filters_by_role(self, db):
        """Builder chunk only gets builder + null-role rules."""
        await db.insert_rule(make_rule(id="general-R001", rule_text="Builder rule", domain="general", role="builder"))
        await db.insert_rule(make_rule(id="general-R002", rule_text="Reviewer rule", domain="general", role="reviewer"))
        await db.insert_rule(make_rule(id="general-R003", rule_text="All role rule", domain="general"))

        result = await handle_create_plan(db, "Test", json.dumps(_make_chunks()), "[]")
        plan_id = result["plan_id"]
        await db.update_plan(plan_id, phase="build")

        result = await handle_dispatch_chunk(db, plan_id, "a")
        assert "Builder rule" in result["prompt"]
        assert "All role rule" in result["prompt"]
        assert "Reviewer rule" not in result["prompt"]

    @pytest.mark.asyncio
    async def test_dispatch_prompt_contains_prohibitions(self, db):
        """Prompt contains standard and chunk-specific prohibitions."""
        result = await handle_create_plan(db, "Test", json.dumps(_make_chunks()), "[]")
        plan_id = result["plan_id"]
        await db.update_plan(plan_id, phase="build")

        result = await handle_dispatch_chunk(db, plan_id, "a")
        assert "Do NOT modify files outside" in result["prompt"]
        assert "Delta edits only" in result["prompt"]

    @pytest.mark.asyncio
    async def test_dispatch_prompt_contains_role(self, db):
        """Prompt contains role assignment."""
        result = await handle_create_plan(db, "Test", json.dumps(_make_chunks()), "[]")
        plan_id = result["plan_id"]
        await db.update_plan(plan_id, phase="build")

        result = await handle_dispatch_chunk(db, plan_id, "a")
        assert "builder" in result["prompt"].lower()

    @pytest.mark.asyncio
    async def test_dispatch_chunk_not_found(self, db):
        """Nonexistent chunk returns not_found."""
        result = await handle_create_plan(db, "Test", json.dumps(_make_chunks()), "[]")
        plan_id = result["plan_id"]
        await db.update_plan(plan_id, phase="build")

        result = await handle_dispatch_chunk(db, plan_id, "nonexistent")
        assert result["status"] == "not_found"

    @pytest.mark.asyncio
    async def test_dispatch_plan_not_found(self, db):
        """Nonexistent plan returns not_found."""
        result = await handle_dispatch_chunk(db, 999, "a")
        assert result["status"] == "not_found"

    @pytest.mark.asyncio
    async def test_dispatch_blocked_before_wave_verified(self, db):
        """Dispatch wave-2 chunk before wave-1 verified -> refused."""
        from calx.serve.tools.create_plan import handle_create_plan

        chunks = [
            {"id": "a", "description": "Wave 1", "files": ["src/a.py"],
             "acceptance_criteria": [], "prohibitions": [],
             "domain": "general", "role": "builder", "estimated_tokens": 10000, "depends_on": []},
            {"id": "b", "description": "Wave 2", "files": ["src/b.py"],
             "acceptance_criteria": [], "prohibitions": [],
             "domain": "general", "role": "builder", "estimated_tokens": 10000, "depends_on": ["a"]},
        ]
        result = await handle_create_plan(db, "Test", json.dumps(chunks), json.dumps([["a", "b"]]))
        plan_id = result["plan_id"]
        await db.update_plan(plan_id, phase="build")

        # Try to dispatch wave-2 chunk before wave-1 verified
        result = await handle_dispatch_chunk(db, plan_id, "b")
        assert result["status"] == "wave_blocked"
        assert "Wave" in result["message"]

    @pytest.mark.asyncio
    async def test_dispatch_wave2_after_wave1_verified(self, db):
        """After wave-1 verified, wave-2 dispatch succeeds."""
        from calx.serve.tools.create_plan import handle_create_plan
        from calx.serve.tools.update_plan import handle_update_plan
        from calx.serve.tools.verify_wave import handle_verify_wave
        from unittest.mock import patch, AsyncMock

        chunks = [
            {"id": "a", "description": "Wave 1", "files": ["src/a.py"],
             "acceptance_criteria": [], "prohibitions": [],
             "domain": "general", "role": "builder", "estimated_tokens": 10000, "depends_on": []},
            {"id": "b", "description": "Wave 2", "files": ["src/b.py"],
             "acceptance_criteria": [], "prohibitions": [],
             "domain": "general", "role": "builder", "estimated_tokens": 10000, "depends_on": ["a"]},
        ]
        result = await handle_create_plan(db, "Test", json.dumps(chunks), json.dumps([["a", "b"]]))
        plan_id = result["plan_id"]
        await db.update_plan(plan_id, phase="build")

        # Complete wave 1 chunk
        await handle_update_plan(db, plan_id, chunk_id="a", chunk_status="done")

        # Verify wave 1
        mock_result = {
            "import_check": {"passed": True, "failures": []},
            "test_check": {"passed": True, "failures": []},
            "duplicate_check": {"passed": True, "duplicates": []},
            "manual": {"passed": True, "notes": "ok"},
            "overall": "pass",
            "failing_chunks": [],
            "redispatch_recommended": False,
        }
        with patch("calx.serve.tools.verify_wave.run_wave_verification", new_callable=AsyncMock, return_value=mock_result):
            await handle_verify_wave(db, plan_id, 1, manual_notes="ok")

        # Now wave-2 dispatch should work
        result = await handle_dispatch_chunk(db, plan_id, "b")
        assert result["status"] == "ok"
