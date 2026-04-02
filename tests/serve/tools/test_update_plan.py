"""Tests for update_plan MCP tool."""
from __future__ import annotations

import json

import pytest

from calx.serve.db.engine import FoilReviewRow


class TestUpdatePlan:

    async def _create_plan(self, db, chunks, edges=None):
        """Helper to create a plan and return plan_id."""
        from calx.serve.tools.create_plan import handle_create_plan

        edges = edges or []
        result = await handle_create_plan(
            db, "Test plan", json.dumps(chunks), json.dumps(edges),
        )
        return result["plan_id"]

    @pytest.mark.asyncio
    async def test_update_plan_marks_chunk_complete(self, db):
        from calx.serve.tools.update_plan import handle_update_plan

        chunks = [
            {"id": "a", "description": "A", "files": ["a.py"],
             "acceptance_criteria": [], "prohibitions": [], "domain": "general",
             "role": "builder", "estimated_tokens": 10000, "depends_on": []},
            {"id": "b", "description": "B", "files": ["b.py"],
             "acceptance_criteria": [], "prohibitions": [], "domain": "general",
             "role": "builder", "estimated_tokens": 10000, "depends_on": []},
        ]
        plan_id = await self._create_plan(db, chunks)

        result = await handle_update_plan(
            db, plan_id, chunk_id="a", chunk_status="done",
        )
        assert result["status"] == "ok"
        assert result["phase"] is not None

        # Verify the chunk was marked done in DB
        plan = await db.get_plan(plan_id)
        stored = json.loads(plan.chunks)
        chunk_a = next(c for c in stored if c["id"] == "a")
        assert chunk_a["status"] == "done"

        # next_dispatchable should still include "b"
        assert "b" in result["next_dispatchable"]

    @pytest.mark.asyncio
    async def test_update_plan_marks_chunk_blocked(self, db):
        from calx.serve.tools.update_plan import handle_update_plan

        chunks = [
            {"id": "a", "description": "A", "files": ["a.py"],
             "acceptance_criteria": [], "prohibitions": [], "domain": "general",
             "role": "builder", "estimated_tokens": 10000, "depends_on": []},
        ]
        plan_id = await self._create_plan(db, chunks)

        result = await handle_update_plan(
            db, plan_id, chunk_id="a", chunk_status="blocked",
            block_reason="API not ready",
        )
        assert result["status"] == "ok"

        plan = await db.get_plan(plan_id)
        stored = json.loads(plan.chunks)
        chunk_a = next(c for c in stored if c["id"] == "a")
        assert chunk_a["status"] == "blocked"
        assert chunk_a["block_reason"] == "API not ready"

    @pytest.mark.asyncio
    async def test_update_plan_does_not_auto_advance_wave(self, db):
        """BF-1: update_plan must NOT auto-advance wave. Only verify_wave advances."""
        from calx.serve.tools.update_plan import handle_update_plan

        # Two waves: a (wave 1) -> b (wave 2)
        chunks = [
            {"id": "a", "description": "A", "files": ["a.py"],
             "acceptance_criteria": [], "prohibitions": [], "domain": "general",
             "role": "builder", "estimated_tokens": 10000, "depends_on": []},
            {"id": "b", "description": "B", "files": ["b.py"],
             "acceptance_criteria": [], "prohibitions": [], "domain": "general",
             "role": "builder", "estimated_tokens": 10000, "depends_on": ["a"]},
        ]
        edges = [["a", "b"]]
        plan_id = await self._create_plan(db, chunks, edges)

        # Verify starting at wave 1
        plan_before = await db.get_plan(plan_id)
        assert plan_before.current_wave == 1

        # Complete chunk a (the only chunk in wave 1)
        result = await handle_update_plan(
            db, plan_id, chunk_id="a", chunk_status="done",
        )
        assert result["status"] == "ok"

        # Wave must NOT auto-advance (BF-1: only verify_wave advances)
        plan_after = await db.get_plan(plan_id)
        assert plan_after.current_wave == 1
        assert result["wave"] == 1

    @pytest.mark.asyncio
    async def test_update_plan_auto_advance_spec_to_test(self, db, tmp_path):
        from calx.serve.tools.update_plan import handle_update_plan

        chunks = [
            {"id": "a", "description": "A", "files": ["a.py"],
             "acceptance_criteria": [], "prohibitions": [], "domain": "general",
             "role": "builder", "estimated_tokens": 10000, "depends_on": []},
        ]
        plan_id = await self._create_plan(db, chunks)

        # Plan starts in spec phase
        plan = await db.get_plan(plan_id)
        assert plan.phase == "spec"

        # Create a real spec file so Path.exists() passes
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("# Spec")

        result = await handle_update_plan(
            db, plan_id, spec_file=str(spec_file),
        )
        assert result["status"] == "ok"
        assert result["phase"] == "test"

    @pytest.mark.asyncio
    async def test_update_plan_auto_advance_test_to_chunk(self, db, tmp_path):
        from calx.serve.tools.update_plan import handle_update_plan

        chunks = [
            {"id": "a", "description": "A", "files": ["a.py"],
             "acceptance_criteria": [], "prohibitions": [], "domain": "general",
             "role": "builder", "estimated_tokens": 10000, "depends_on": []},
        ]
        plan_id = await self._create_plan(db, chunks)

        # Advance to test phase first: set spec_file
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("# Spec")
        await handle_update_plan(db, plan_id, spec_file=str(spec_file))

        plan = await db.get_plan(plan_id)
        assert plan.phase == "test"

        # Create real test files
        test_file = tmp_path / "test_a.py"
        test_file.write_text("def test_a(): pass")

        result = await handle_update_plan(
            db, plan_id, test_files=json.dumps([str(test_file)]),
        )
        assert result["status"] == "ok"
        assert result["phase"] == "chunk"

    @pytest.mark.asyncio
    async def test_update_plan_auto_advance_plan_to_build(self, db, tmp_path):
        from calx.serve.tools.update_plan import handle_update_plan

        chunks = [
            {"id": "a", "description": "A", "files": ["a.py"],
             "acceptance_criteria": [], "prohibitions": [], "domain": "general",
             "role": "builder", "estimated_tokens": 10000, "depends_on": []},
        ]
        plan_id = await self._create_plan(db, chunks)

        # Advance through spec -> test -> chunk -> plan
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("# Spec")
        await handle_update_plan(db, plan_id, spec_file=str(spec_file))

        test_file = tmp_path / "test_a.py"
        test_file.write_text("def test_a(): pass")
        await handle_update_plan(db, plan_id, test_files=json.dumps([str(test_file)]))

        # Now at chunk phase. Advance to plan phase.
        # chunk -> plan requires chunks to be non-empty (already true)
        from calx.serve.engine.orchestration import advance_phase
        new_phase, msg = await advance_phase(db, plan_id)
        assert new_phase == "plan"

        plan = await db.get_plan(plan_id)
        assert plan.phase == "plan"

        # Insert a real foil review to satisfy FK constraint
        review_id = await db.insert_foil_review(FoilReviewRow(
            spec_reference="spec.md",
            reviewer_domain="backend",
            verdict="approve",
            findings="Looks good",
        ))

        # Set review_id to auto-advance plan -> build
        result = await handle_update_plan(db, plan_id, review_id=review_id)
        assert result["status"] == "ok"
        assert result["phase"] == "build"

    @pytest.mark.asyncio
    async def test_auto_advance_plan_to_build_rejects_revise_review(self, db, tmp_path):
        """Setting review_id with revise verdict does NOT auto-advance to build."""
        from calx.serve.tools.update_plan import handle_update_plan

        chunks = [
            {"id": "a", "description": "A", "files": ["a.py"],
             "acceptance_criteria": [], "prohibitions": [], "domain": "general",
             "role": "builder", "estimated_tokens": 10000, "depends_on": []},
        ]
        plan_id = await self._create_plan(db, chunks)

        # Advance through spec -> test -> chunk -> plan
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("# Spec")
        await handle_update_plan(db, plan_id, spec_file=str(spec_file))

        test_file = tmp_path / "test_a.py"
        test_file.write_text("def test_a(): pass")
        await handle_update_plan(db, plan_id, test_files=json.dumps([str(test_file)]))

        # chunk -> plan
        from calx.serve.engine.orchestration import advance_phase
        new_phase, msg = await advance_phase(db, plan_id)
        assert new_phase == "plan"

        # Record a REVISE review
        review_id = await db.insert_foil_review(FoilReviewRow(
            spec_reference="spec.md",
            reviewer_domain="backend",
            verdict="revise",
            findings="Issues found",
        ))

        # Set review_id: should NOT auto-advance to build
        result = await handle_update_plan(db, plan_id, review_id=review_id)
        assert result["phase"] == "plan"

    @pytest.mark.asyncio
    async def test_update_plan_not_found(self, db):
        from calx.serve.tools.update_plan import handle_update_plan

        result = await handle_update_plan(db, plan_id=99999)
        assert result["status"] == "not_found"
