"""Tests for verify_wave tool."""
from __future__ import annotations

import json
from unittest.mock import patch, AsyncMock

import pytest

from calx.serve.tools.create_plan import handle_create_plan
from calx.serve.tools.verify_wave import handle_verify_wave


def _make_chunks():
    return [
        {"id": "a", "description": "Build models", "files": ["src/models.py"],
         "acceptance_criteria": ["Models exist"], "prohibitions": [],
         "domain": "general", "role": "builder", "estimated_tokens": 30000,
         "depends_on": [], "status": "done"},
    ]


def _mock_pass_result(manual_notes=None):
    return {
        "import_check": {"passed": True, "failures": []},
        "test_check": {"passed": True, "failures": []},
        "duplicate_check": {"passed": True, "duplicates": []},
        "manual": {"passed": manual_notes is not None, "notes": manual_notes or ""},
        "overall": "pass",
        "failing_chunks": [],
        "redispatch_recommended": False,
    }


def _mock_fail_result():
    return {
        "import_check": {"passed": False, "failures": [{"file": "src/models.py", "error": "SyntaxError"}]},
        "test_check": {"passed": True, "failures": []},
        "duplicate_check": {"passed": True, "duplicates": []},
        "manual": {"passed": False, "notes": ""},
        "overall": "fail",
        "failing_chunks": ["a"],
        "redispatch_recommended": True,
    }


class TestVerifyWave:

    @pytest.mark.asyncio
    @patch("calx.serve.tools.verify_wave.run_wave_verification", new_callable=AsyncMock)
    async def test_verify_wave_records_result(self, mock_verify, db):
        """Verification results are recorded in wave_verification JSON."""
        mock_verify.return_value = _mock_pass_result("all good")

        chunks = _make_chunks()
        result = await handle_create_plan(db, "Test", json.dumps(chunks), "[]")
        plan_id = result["plan_id"]

        result = await handle_verify_wave(db, plan_id, 1, manual_notes="all good")
        assert result["status"] == "ok"
        assert result["overall"] == "pass"
        assert result["wave_id"] == 1

        # Verify stored in DB
        plan = await db.get_plan(plan_id)
        wv = json.loads(plan.wave_verification)
        assert "1" in wv
        assert wv["1"]["overall"] == "pass"
        assert wv["1"]["notes"] == "all good"
        assert "verified_at" in wv["1"]

    @pytest.mark.asyncio
    async def test_verify_wave_plan_not_found(self, db):
        """Nonexistent plan returns not_found."""
        result = await handle_verify_wave(db, 999, 1)
        assert result["status"] == "not_found"

    @pytest.mark.asyncio
    @patch("calx.serve.tools.verify_wave.run_wave_verification", new_callable=AsyncMock)
    async def test_verify_wave_with_manual_notes(self, mock_verify, db):
        """Manual notes are recorded in verification result."""
        mock_verify.return_value = _mock_pass_result("Checked manually, looks good")

        chunks = _make_chunks()
        result = await handle_create_plan(db, "Test", json.dumps(chunks), "[]")
        plan_id = result["plan_id"]

        result = await handle_verify_wave(db, plan_id, 1, manual_notes="Checked manually, looks good")
        assert result["status"] == "ok"

        plan = await db.get_plan(plan_id)
        wv = json.loads(plan.wave_verification)
        assert wv["1"]["notes"] == "Checked manually, looks good"

    @pytest.mark.asyncio
    @patch("calx.serve.tools.verify_wave.run_wave_verification", new_callable=AsyncMock)
    async def test_verify_wave_fail_records_failure(self, mock_verify, db):
        """Failed verification is recorded with overall=fail."""
        mock_verify.return_value = _mock_fail_result()

        chunks = _make_chunks()
        result = await handle_create_plan(db, "Test", json.dumps(chunks), "[]")
        plan_id = result["plan_id"]

        result = await handle_verify_wave(db, plan_id, 1)
        assert result["status"] == "ok"
        assert result["overall"] == "fail"
        assert result["redispatch_recommended"] is True

        plan = await db.get_plan(plan_id)
        wv = json.loads(plan.wave_verification)
        assert wv["1"]["overall"] == "fail"

    @pytest.mark.asyncio
    @patch("calx.serve.tools.verify_wave.run_wave_verification", new_callable=AsyncMock)
    async def test_verify_wave_without_manual_notes(self, mock_verify, db):
        """Verification without manual notes stores empty string."""
        mock_verify.return_value = _mock_pass_result()

        chunks = _make_chunks()
        result = await handle_create_plan(db, "Test", json.dumps(chunks), "[]")
        plan_id = result["plan_id"]

        result = await handle_verify_wave(db, plan_id, 1)
        assert result["status"] == "ok"

        plan = await db.get_plan(plan_id)
        wv = json.loads(plan.wave_verification)
        assert wv["1"]["notes"] == ""

    @pytest.mark.asyncio
    @patch("calx.serve.tools.verify_wave.run_wave_verification", new_callable=AsyncMock)
    async def test_verify_wave_preserves_previous_waves(self, mock_verify, db):
        """Verifying wave 2 does not erase wave 1 results."""
        mock_verify.return_value = _mock_pass_result("wave pass")

        chunks = _make_chunks()
        result = await handle_create_plan(db, "Test", json.dumps(chunks), "[]")
        plan_id = result["plan_id"]

        # Verify wave 1
        await handle_verify_wave(db, plan_id, 1, manual_notes="wave 1 ok")

        # Verify wave 2
        await handle_verify_wave(db, plan_id, 2, manual_notes="wave 2 ok")

        plan = await db.get_plan(plan_id)
        wv = json.loads(plan.wave_verification)
        assert "1" in wv
        assert "2" in wv
        assert wv["1"]["notes"] == "wave 1 ok"
        assert wv["2"]["notes"] == "wave 2 ok"

    @pytest.mark.asyncio
    @patch("calx.serve.tools.verify_wave.run_wave_verification", new_callable=AsyncMock)
    async def test_verify_wave_pass_advances_current_wave(self, mock_verify, db):
        """Passing verification advances current_wave."""
        mock_verify.return_value = _mock_pass_result("ok")

        chunks = [
            {"id": "a", "description": "W1", "files": ["src/a.py"],
             "acceptance_criteria": [], "prohibitions": [],
             "domain": "general", "role": "builder", "estimated_tokens": 10000,
             "depends_on": [], "status": "done"},
            {"id": "b", "description": "W2", "files": ["src/b.py"],
             "acceptance_criteria": [], "prohibitions": [],
             "domain": "general", "role": "builder", "estimated_tokens": 10000,
             "depends_on": ["a"], "status": "pending"},
        ]
        result = await handle_create_plan(db, "Test", json.dumps(chunks), json.dumps([["a", "b"]]))
        plan_id = result["plan_id"]

        plan_before = await db.get_plan(plan_id)
        assert plan_before.current_wave == 1

        await handle_verify_wave(db, plan_id, 1, manual_notes="ok")

        plan_after = await db.get_plan(plan_id)
        assert plan_after.current_wave == 2

    @pytest.mark.asyncio
    @patch("calx.serve.tools.verify_wave.run_wave_verification", new_callable=AsyncMock)
    async def test_verify_wave_fail_does_not_advance(self, mock_verify, db):
        """Failed verification does NOT advance current_wave."""
        mock_verify.return_value = _mock_fail_result()

        chunks = _make_chunks()
        result = await handle_create_plan(db, "Test", json.dumps(chunks), "[]")
        plan_id = result["plan_id"]

        await handle_verify_wave(db, plan_id, 1)

        plan = await db.get_plan(plan_id)
        assert plan.current_wave == 1
