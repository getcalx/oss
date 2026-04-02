"""Tests for orchestration engine modules: orchestration, dispatch, verification.

Wave 1B -- TDD: these tests are written before implementation.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from calx.serve.db.engine import FoilReviewRow, PlanRow, RuleRow


# =========================================================================
# Fixtures
# =========================================================================

def _make_chunk(chunk_id: str, files: list[str] | None = None,
                status: str = "pending", role: str = "builder",
                domain: str = "general",
                description: str = "do the thing",
                acceptance_criteria: list[str] | None = None,
                prohibitions: list[str] | None = None) -> dict:
    return {
        "id": chunk_id,
        "files": files or [],
        "status": status,
        "role": role,
        "domain": domain,
        "description": description,
        "acceptance_criteria": acceptance_criteria or ["tests pass"],
        "prohibitions": prohibitions or [],
    }


def _make_plan_data(
    plan_id: int = 1,
    task_description: str = "Build the widget",
    chunks: list[dict] | None = None,
    edges: list[list[str]] | None = None,
    phase: str = "spec",
    spec_file: str | None = None,
    test_files: str | None = None,
    review_id: int | None = None,
    current_wave: int = 1,
    wave_verification: str | None = None,
    status: str = "active",
) -> dict:
    return {
        "id": plan_id,
        "task_description": task_description,
        "chunks": json.dumps(chunks or []),
        "dependency_edges": json.dumps(edges or []),
        "phase": phase,
        "spec_file": spec_file,
        "test_files": test_files,
        "review_id": review_id,
        "current_wave": current_wave,
        "wave_verification": wave_verification,
        "status": status,
    }


def _mock_db(plan_row: PlanRow | None = None,
             rules: list[RuleRow] | None = None,
             foil_reviews: list[FoilReviewRow] | None = None) -> AsyncMock:
    db = AsyncMock()
    db.get_plan = AsyncMock(return_value=plan_row)
    db.update_plan = AsyncMock()
    db.find_rules = AsyncMock(return_value=rules or [])
    db.get_foil_reviews = AsyncMock(return_value=foil_reviews or [])
    return db


# =========================================================================
# orchestration.compute_waves
# =========================================================================

class TestComputeWaves:
    def test_linear_chain(self):
        from calx.serve.engine.orchestration import compute_waves

        chunks = [_make_chunk("A"), _make_chunk("B"), _make_chunk("C")]
        edges = [["A", "B"], ["B", "C"]]
        waves = compute_waves(chunks, edges)
        assert len(waves) == 3
        assert waves[0] == ["A"]
        assert waves[1] == ["B"]
        assert waves[2] == ["C"]

    def test_independent_chunks(self):
        from calx.serve.engine.orchestration import compute_waves

        chunks = [_make_chunk("A"), _make_chunk("B"), _make_chunk("C")]
        edges = []
        waves = compute_waves(chunks, edges)
        assert len(waves) == 1
        assert sorted(waves[0]) == ["A", "B", "C"]

    def test_diamond(self):
        from calx.serve.engine.orchestration import compute_waves

        chunks = [_make_chunk("A"), _make_chunk("B"), _make_chunk("C")]
        edges = [["A", "C"], ["B", "C"]]
        waves = compute_waves(chunks, edges)
        assert len(waves) == 2
        assert sorted(waves[0]) == ["A", "B"]
        assert waves[1] == ["C"]

    def test_empty_chunks(self):
        from calx.serve.engine.orchestration import compute_waves

        waves = compute_waves([], [])
        assert waves == []

    def test_compute_waves_raises_on_cycle(self):
        """Cyclic dependencies raise ValueError."""
        from calx.serve.engine.orchestration import compute_waves

        chunks = [
            {"id": "a", "files": []},
            {"id": "b", "files": []},
        ]
        edges = [["a", "b"], ["b", "a"]]
        with pytest.raises(ValueError, match="Cycle"):
            compute_waves(chunks, edges)


# =========================================================================
# orchestration.get_next_dispatchable
# =========================================================================

class TestGetNextDispatchable:
    def test_returns_pending_in_current_wave(self):
        from calx.serve.engine.orchestration import get_next_dispatchable

        chunks = [
            _make_chunk("A", files=["src/a.py"], status="pending"),
            _make_chunk("B", files=["src/b.py"], status="pending"),
            _make_chunk("C", files=["src/c.py"], status="pending"),
        ]
        # A, B independent; C depends on A
        edges = [["A", "C"]]
        # Wave 0 contains A, B
        result = get_next_dispatchable(chunks, edges, current_wave=0)
        assert sorted(result) == ["A", "B"]

    def test_excludes_file_overlap(self):
        from calx.serve.engine.orchestration import get_next_dispatchable

        chunks = [
            _make_chunk("A", files=["src/shared.py"], status="pending"),
            _make_chunk("B", files=["src/shared.py"], status="pending"),
        ]
        edges = []
        result = get_next_dispatchable(chunks, edges, current_wave=0)
        # Only one should be returned since they share a file
        assert len(result) == 1
        assert result[0] in ("A", "B")

    def test_empty_when_all_done_or_in_progress(self):
        from calx.serve.engine.orchestration import get_next_dispatchable

        chunks = [
            _make_chunk("A", files=["src/a.py"], status="done"),
            _make_chunk("B", files=["src/b.py"], status="in_progress"),
        ]
        edges = []
        result = get_next_dispatchable(chunks, edges, current_wave=0)
        assert result == []


# =========================================================================
# orchestration.validate_file_disjoint
# =========================================================================

class TestValidateFileDisjoint:
    def test_flags_shared_files(self):
        from calx.serve.engine.orchestration import validate_file_disjoint

        chunks = [
            _make_chunk("A", files=["src/foo.py"]),
            _make_chunk("B", files=["src/foo.py"]),
        ]
        warnings = validate_file_disjoint(chunks)
        assert len(warnings) == 1
        assert warnings[0]["file"] == "src/foo.py"
        assert sorted(warnings[0]["chunks"]) == ["A", "B"]

    def test_passes_disjoint(self):
        from calx.serve.engine.orchestration import validate_file_disjoint

        chunks = [
            _make_chunk("A", files=["src/a.py"]),
            _make_chunk("B", files=["src/b.py"]),
        ]
        warnings = validate_file_disjoint(chunks)
        assert warnings == []

    def test_empty_for_single_chunk(self):
        from calx.serve.engine.orchestration import validate_file_disjoint

        chunks = [_make_chunk("A", files=["src/a.py"])]
        warnings = validate_file_disjoint(chunks)
        assert warnings == []


# =========================================================================
# orchestration.check_phase_entry
# =========================================================================

class TestCheckPhaseEntry:
    def test_spec_always_allowed(self):
        from calx.serve.engine.orchestration import check_phase_entry

        plan = _make_plan_data()
        allowed, reason = check_phase_entry(plan, "spec")
        assert allowed is True

    @patch("calx.serve.engine.orchestration.Path")
    def test_test_phase_fails_without_spec_file(self, mock_path_cls):
        from calx.serve.engine.orchestration import check_phase_entry

        plan = _make_plan_data(spec_file=None)
        allowed, reason = check_phase_entry(plan, "test")
        assert allowed is False
        assert "spec_file" in reason.lower()

    @patch("calx.serve.engine.orchestration.Path")
    def test_test_phase_passes_with_spec_file(self, mock_path_cls):
        from calx.serve.engine.orchestration import check_phase_entry

        mock_path_cls.return_value.exists.return_value = True
        plan = _make_plan_data(spec_file="product/spec.md")
        allowed, reason = check_phase_entry(plan, "test")
        assert allowed is True

    @patch("calx.serve.engine.orchestration.Path")
    def test_chunk_phase_fails_without_test_files(self, mock_path_cls):
        from calx.serve.engine.orchestration import check_phase_entry

        plan = _make_plan_data(test_files=None)
        allowed, reason = check_phase_entry(plan, "chunk")
        assert allowed is False
        assert "test_files" in reason.lower()

    def test_plan_phase_fails_with_empty_chunks(self):
        from calx.serve.engine.orchestration import check_phase_entry

        plan = _make_plan_data(chunks=[])
        allowed, reason = check_phase_entry(plan, "plan")
        assert allowed is False
        assert "chunk" in reason.lower()

    def test_build_phase_fails_without_review_id(self):
        from calx.serve.engine.orchestration import check_phase_entry

        plan = _make_plan_data(review_id=None)
        allowed, reason = check_phase_entry(plan, "build")
        assert allowed is False
        assert "review" in reason.lower()

    def test_check_phase_entry_build_revise_verdict(self):
        """Build phase gate rejects revise verdict."""
        from calx.serve.engine.orchestration import check_phase_entry

        plan_data = _make_plan_data(review_id=1)
        plan_data["review_verdict"] = "revise"
        allowed, reason = check_phase_entry(plan_data, "build")
        assert not allowed
        assert "approve" in reason

    def test_check_phase_entry_build_approve_verdict(self):
        """Build phase gate accepts approve verdict."""
        from calx.serve.engine.orchestration import check_phase_entry

        plan_data = _make_plan_data(review_id=1)
        plan_data["review_verdict"] = "approve"
        allowed, reason = check_phase_entry(plan_data, "build")
        assert allowed

    def test_verify_phase_fails_when_chunks_not_done(self):
        from calx.serve.engine.orchestration import check_phase_entry

        chunks = [
            _make_chunk("A", status="done"),
            _make_chunk("B", status="in_progress"),
        ]
        plan = _make_plan_data(chunks=chunks, current_wave=1)
        allowed, reason = check_phase_entry(plan, "verify")
        assert allowed is False
        assert "chunk" in reason.lower() or "done" in reason.lower()

    def test_commit_phase_fails_without_wave_verification(self):
        from calx.serve.engine.orchestration import check_phase_entry

        plan = _make_plan_data(wave_verification=None)
        allowed, reason = check_phase_entry(plan, "commit")
        assert allowed is False
        assert "verification" in reason.lower() or "verif" in reason.lower()

    def test_commit_phase_fails_when_verification_failed(self):
        from calx.serve.engine.orchestration import check_phase_entry

        verification = json.dumps({"1": {"overall": "fail"}})
        plan = _make_plan_data(wave_verification=verification, current_wave=1)
        allowed, reason = check_phase_entry(plan, "commit")
        assert allowed is False

    def test_done_phase_fails_when_not_all_waves_verified(self):
        from calx.serve.engine.orchestration import check_phase_entry

        chunks = [
            _make_chunk("A", status="done"),
            _make_chunk("B", status="done"),
        ]
        # Two waves, only wave 1 verified
        edges = [["A", "B"]]
        verification = json.dumps({"1": {"overall": "pass"}})
        plan = _make_plan_data(
            chunks=chunks, edges=edges,
            wave_verification=verification, current_wave=2,
        )
        allowed, reason = check_phase_entry(plan, "done")
        assert allowed is False
        assert "wave" in reason.lower() or "verified" in reason.lower()

    def test_check_phase_entry_done_all_waves_verified(self):
        """Done phase gate passes when all waves verified."""
        from calx.serve.engine.orchestration import check_phase_entry

        plan_data = {
            "chunks": json.dumps([
                {"id": "a", "files": [], "status": "done"},
                {"id": "b", "files": [], "status": "done", "depends_on": ["a"]},
            ]),
            "dependency_edges": json.dumps([["a", "b"]]),
            "wave_verification": json.dumps({
                "1": {"overall": "pass"},
                "2": {"overall": "pass"},
            }),
        }
        allowed, reason = check_phase_entry(plan_data, "done")
        assert allowed
        assert "all waves" in reason.lower()


# =========================================================================
# orchestration.advance_phase
# =========================================================================

class TestAdvancePhase:
    async def test_advances_spec_to_test(self):
        from calx.serve.engine.orchestration import advance_phase

        plan_row = PlanRow(
            id=1, task_description="build it",
            phase="spec", spec_file="product/spec.md",
            status="active",
        )
        db = _mock_db(plan_row=plan_row)
        with patch("calx.serve.engine.orchestration.Path") as mock_path_cls:
            mock_path_cls.return_value.exists.return_value = True
            new_phase, msg = await advance_phase(db, plan_id=1)

        assert new_phase == "test"
        db.update_plan.assert_called_once()

    async def test_refuses_when_criteria_not_met(self):
        from calx.serve.engine.orchestration import advance_phase

        plan_row = PlanRow(
            id=1, task_description="build it",
            phase="spec", spec_file=None,
            status="active",
        )
        db = _mock_db(plan_row=plan_row)
        new_phase, msg = await advance_phase(db, plan_id=1)

        assert new_phase == "spec"
        assert "spec_file" in msg.lower()
        db.update_plan.assert_not_called()

    async def test_advance_to_done_sets_completed(self):
        from calx.serve.engine.orchestration import advance_phase

        chunks = [_make_chunk("A", status="done")]
        verification = json.dumps({"1": {"overall": "pass"}})
        plan_row = PlanRow(
            id=1, task_description="build it",
            chunks=json.dumps(chunks),
            dependency_edges="[]",
            phase="commit",
            current_wave=1,
            wave_verification=verification,
            status="active",
        )
        db = _mock_db(plan_row=plan_row)
        new_phase, msg = await advance_phase(db, plan_id=1)

        assert new_phase == "done"
        # Verify status was set to completed along with phase
        call_kwargs = db.update_plan.call_args
        assert call_kwargs[1].get("status") == "completed" or \
               (len(call_kwargs[0]) > 2 and "completed" in str(call_kwargs))

    async def test_advance_phase_with_revise_review_blocks(self):
        """advance_phase with revise review doesn't advance to build."""
        from calx.serve.engine.orchestration import advance_phase

        plan_row = PlanRow(
            id=1, task_description="build it",
            chunks=json.dumps([_make_chunk("A")]),
            dependency_edges="[]",
            phase="plan",
            review_id=42,
            status="active",
        )
        revise_review = FoilReviewRow(
            id=42,
            spec_reference="spec.md",
            reviewer_domain="backend",
            verdict="revise",
            findings="Issues found",
        )
        db = _mock_db(plan_row=plan_row, foil_reviews=[revise_review])
        phase, msg = await advance_phase(db, plan_id=1)
        assert phase == "plan"
        assert "approve" in msg

    async def test_advance_phase_with_approve_review_advances(self):
        """advance_phase with approve review advances to build."""
        from calx.serve.engine.orchestration import advance_phase

        plan_row = PlanRow(
            id=1, task_description="build it",
            chunks=json.dumps([_make_chunk("A")]),
            dependency_edges="[]",
            phase="plan",
            review_id=42,
            status="active",
        )
        approve_review = FoilReviewRow(
            id=42,
            spec_reference="spec.md",
            reviewer_domain="backend",
            verdict="approve",
            findings="Looks good",
        )
        db = _mock_db(plan_row=plan_row, foil_reviews=[approve_review])
        phase, msg = await advance_phase(db, plan_id=1)
        assert phase == "build"


# =========================================================================
# dispatch.build_dispatch_prompt
# =========================================================================

class TestBuildDispatchPrompt:
    async def test_contains_role_assignment(self):
        from calx.serve.engine.dispatch import build_dispatch_prompt

        chunk = _make_chunk("A", files=["src/a.py"], role="builder")
        plan = _make_plan_data()
        db = _mock_db()

        with patch("calx.serve.engine.dispatch.Path") as mock_path_cls:
            mock_path_cls.return_value.exists.return_value = False
            prompt = await build_dispatch_prompt(db, plan, chunk)

        assert "builder" in prompt.lower()

    async def test_contains_chunk_files(self):
        from calx.serve.engine.dispatch import build_dispatch_prompt

        chunk = _make_chunk("A", files=["src/a.py", "src/b.py"])
        plan = _make_plan_data()
        db = _mock_db()

        with patch("calx.serve.engine.dispatch.Path") as mock_path_cls:
            mock_path_cls.return_value.exists.return_value = False
            prompt = await build_dispatch_prompt(db, plan, chunk)

        assert "src/a.py" in prompt
        assert "src/b.py" in prompt

    async def test_contains_acceptance_criteria(self):
        from calx.serve.engine.dispatch import build_dispatch_prompt

        chunk = _make_chunk("A", acceptance_criteria=["all tests pass", "no lint errors"])
        plan = _make_plan_data()
        db = _mock_db()

        with patch("calx.serve.engine.dispatch.Path") as mock_path_cls:
            mock_path_cls.return_value.exists.return_value = False
            prompt = await build_dispatch_prompt(db, plan, chunk)

        assert "all tests pass" in prompt
        assert "no lint errors" in prompt

    async def test_contains_prohibitions(self):
        from calx.serve.engine.dispatch import build_dispatch_prompt

        chunk = _make_chunk("A", prohibitions=["do not touch the database"])
        plan = _make_plan_data()
        db = _mock_db()

        with patch("calx.serve.engine.dispatch.Path") as mock_path_cls:
            mock_path_cls.return_value.exists.return_value = False
            prompt = await build_dispatch_prompt(db, plan, chunk)

        assert "do not touch the database" in prompt
        assert "Do NOT modify files outside" in prompt

    async def test_filters_rules_by_role(self):
        from calx.serve.engine.dispatch import build_dispatch_prompt

        builder_rule = RuleRow(
            id="general-R001",
            rule_text="Builder must write tests",
            domain="general",
            role="builder",
            created_at="", updated_at="",
        )
        reviewer_rule = RuleRow(
            id="general-R002",
            rule_text="Reviewer must check coverage",
            domain="general",
            role="reviewer",
            created_at="", updated_at="",
        )
        universal_rule = RuleRow(
            id="general-R003",
            rule_text="No em dashes",
            domain="general",
            role=None,
            created_at="", updated_at="",
        )
        db = _mock_db(rules=[builder_rule, reviewer_rule, universal_rule])
        chunk = _make_chunk("A", role="builder", domain="general")
        plan = _make_plan_data()

        with patch("calx.serve.engine.dispatch.Path") as mock_path_cls:
            mock_path_cls.return_value.exists.return_value = False
            prompt = await build_dispatch_prompt(db, plan, chunk)

        assert "Builder must write tests" in prompt
        assert "No em dashes" in prompt
        assert "Reviewer must check coverage" not in prompt

    async def test_worktree_advisory_new_files(self):
        from calx.serve.engine.dispatch import build_dispatch_prompt

        chunk = _make_chunk("A", files=["src/new_file.py"])
        plan = _make_plan_data()
        db = _mock_db()

        with patch("calx.serve.engine.dispatch.Path") as mock_path_cls:
            mock_path_cls.return_value.exists.return_value = False
            prompt = await build_dispatch_prompt(db, plan, chunk)

        assert "worktree" in prompt.lower()
        assert "isolated" in prompt.lower() or "Recommended" in prompt

    async def test_worktree_advisory_existing_files(self):
        from calx.serve.engine.dispatch import build_dispatch_prompt

        chunk = _make_chunk("A", files=["src/existing.py"])
        plan = _make_plan_data()
        db = _mock_db()

        with patch("calx.serve.engine.dispatch.Path") as mock_path_cls:
            mock_path_cls.return_value.exists.return_value = True
            prompt = await build_dispatch_prompt(db, plan, chunk)

        assert "Warning" in prompt
        assert "existing" in prompt.lower() or "verified" in prompt.lower()


# =========================================================================
# dispatch.build_redispatch_prompt
# =========================================================================

class TestBuildRedispatchPrompt:
    async def test_includes_block_reason(self):
        from calx.serve.engine.dispatch import build_redispatch_prompt

        chunk = _make_chunk("A", status="blocked")
        chunk["block_reason"] = "Import check failed for calx.serve.engine.foo"
        plan = _make_plan_data()
        db = _mock_db()

        prompt = await build_redispatch_prompt(db, plan, chunk)
        assert "Import check failed" in prompt

    async def test_includes_remaining_acceptance_criteria(self):
        from calx.serve.engine.dispatch import build_redispatch_prompt

        chunk = _make_chunk(
            "A", status="blocked",
            acceptance_criteria=["tests pass", "no lint errors", "coverage > 80%"],
        )
        chunk["block_reason"] = "lint errors found"
        chunk["completed_criteria"] = ["tests pass"]
        plan = _make_plan_data()
        db = _mock_db()

        prompt = await build_redispatch_prompt(db, plan, chunk)
        # Should include the remaining criteria, not the completed one
        assert "no lint errors" in prompt
        assert "coverage > 80%" in prompt

    async def test_differs_from_dispatch_prompt(self):
        from calx.serve.engine.dispatch import build_dispatch_prompt, build_redispatch_prompt

        chunk = _make_chunk("A", files=["src/a.py"], status="blocked")
        chunk["block_reason"] = "test failure"
        chunk["completed_criteria"] = []
        plan = _make_plan_data()
        db = _mock_db()

        with patch("calx.serve.engine.dispatch.Path") as mock_path_cls:
            mock_path_cls.return_value.exists.return_value = False
            dispatch = await build_dispatch_prompt(db, plan, chunk)

        redispatch = await build_redispatch_prompt(db, plan, chunk)
        assert dispatch != redispatch


# =========================================================================
# verification.run_duplicate_check
# =========================================================================

class TestRunDuplicateCheck:
    def test_finds_duplicates(self, tmp_path):
        from calx.serve.engine.verification import run_duplicate_check

        file_a = tmp_path / "a.py"
        file_b = tmp_path / "b.py"
        file_a.write_text("class Widget:\n    pass\n")
        file_b.write_text("class Widget:\n    pass\n")

        result = run_duplicate_check([str(file_a), str(file_b)])
        assert result["passed"] is False
        assert len(result["duplicates"]) == 1
        assert result["duplicates"][0]["name"] == "Widget"
        assert len(result["duplicates"][0]["files"]) == 2

    def test_no_duplicates(self, tmp_path):
        from calx.serve.engine.verification import run_duplicate_check

        file_a = tmp_path / "a.py"
        file_b = tmp_path / "b.py"
        file_a.write_text("class Alpha:\n    pass\n")
        file_b.write_text("class Beta:\n    pass\n")

        result = run_duplicate_check([str(file_a), str(file_b)])
        assert result["passed"] is True
        assert result["duplicates"] == []

    def test_empty_file_list(self):
        from calx.serve.engine.verification import run_duplicate_check

        result = run_duplicate_check([])
        assert result["passed"] is True
        assert result["duplicates"] == []


# =========================================================================
# verification.run_import_check
# =========================================================================

class TestRunImportCheck:
    @patch("calx.serve.engine.verification.subprocess.run")
    def test_passes_clean_imports(self, mock_run):
        from calx.serve.engine.verification import run_import_check

        mock_run.return_value = MagicMock(returncode=0, stderr="")
        result = run_import_check(["src/calx/serve/engine/foo.py"])
        assert result["passed"] is True
        assert result["failures"] == []

    @patch("calx.serve.engine.verification.subprocess.run")
    def test_reports_import_failure(self, mock_run):
        from calx.serve.engine.verification import run_import_check

        mock_run.return_value = MagicMock(
            returncode=1,
            stderr="ModuleNotFoundError: No module named 'calx.serve.engine.foo'",
        )
        result = run_import_check(["src/calx/serve/engine/foo.py"])
        assert result["passed"] is False
        assert len(result["failures"]) == 1
        assert "foo" in result["failures"][0]["file"]


# =========================================================================
# verification.run_test_check
# =========================================================================

class TestRunTestCheck:
    @patch("calx.serve.engine.verification.subprocess.run")
    def test_passes_green_tests(self, mock_run):
        from calx.serve.engine.verification import run_test_check

        mock_run.return_value = MagicMock(returncode=0, stdout="3 passed", stderr="")
        result = run_test_check(["tests/test_foo.py"])
        assert result["passed"] is True
        assert result["failures"] == []

    @patch("calx.serve.engine.verification.subprocess.run")
    def test_reports_test_failure(self, mock_run):
        from calx.serve.engine.verification import run_test_check

        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="FAILED tests/test_foo.py::test_bar - AssertionError",
            stderr="",
        )
        result = run_test_check(["tests/test_foo.py"])
        assert result["passed"] is False
        assert len(result["failures"]) == 1


# =========================================================================
# verification.run_wave_verification
# =========================================================================

class TestRunWaveVerification:
    async def test_all_checks_pass(self, tmp_path):
        from calx.serve.engine.verification import run_wave_verification

        # Create real files for the checks
        src_file = tmp_path / "a.py"
        src_file.write_text("class Foo:\n    pass\n")
        test_file = tmp_path / "test_a.py"
        test_file.write_text("def test_foo():\n    assert True\n")

        chunks = [_make_chunk("A", files=[str(src_file)], status="done")]
        plan_data = _make_plan_data(chunks=chunks)

        with patch("calx.serve.engine.verification.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="1 passed", stderr="")
            result = await run_wave_verification(
                plan_data, wave_id=1, manual_notes="looks good",
            )

        assert result["overall"] == "pass"
        assert result["import_check"]["passed"] is True
        assert result["duplicate_check"]["passed"] is True

    async def test_fails_on_import_error(self, tmp_path):
        from calx.serve.engine.verification import run_wave_verification

        src_file = tmp_path / "bad.py"
        src_file.write_text("import nonexistent_module\n")

        chunks = [_make_chunk("A", files=[str(src_file)], status="done")]
        plan_data = _make_plan_data(chunks=chunks)

        with patch("calx.serve.engine.verification.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stderr="ModuleNotFoundError",
                stdout="",
            )
            result = await run_wave_verification(plan_data, wave_id=1)

        assert result["overall"] == "fail"
        assert result["redispatch_recommended"] is True

    async def test_wave_filtering_only_checks_requested_wave(self, tmp_path):
        """Wave 1 has clean files, wave 2 has duplicates. Verifying wave 1 should pass."""
        from calx.serve.engine.verification import run_wave_verification

        # Wave 1: clean file
        clean_file = tmp_path / "clean.py"
        clean_file.write_text("class Alpha:\n    pass\n")

        # Wave 2: file with duplicate def (would fail duplicate check if included)
        dup_file_a = tmp_path / "dup_a.py"
        dup_file_a.write_text("class Shared:\n    pass\n")
        dup_file_b = tmp_path / "dup_b.py"
        dup_file_b.write_text("class Shared:\n    pass\n")

        chunks = [
            _make_chunk("A", files=[str(clean_file)], status="done"),
            _make_chunk("B", files=[str(dup_file_a), str(dup_file_b)], status="done"),
        ]
        edges = [["A", "B"]]
        plan_data = _make_plan_data(chunks=chunks, edges=edges)

        with patch("calx.serve.engine.verification.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="1 passed", stderr="")
            result = await run_wave_verification(plan_data, wave_id=1)

        # Wave 1 only has chunk A with clean_file, so duplicate check should pass
        assert result["duplicate_check"]["passed"] is True
        assert result["overall"] == "pass"

    async def test_failing_chunks_includes_test_failures(self, tmp_path):
        """failing_chunks must map test failures back to chunks, not just imports."""
        from calx.serve.engine.verification import run_wave_verification

        src_file = tmp_path / "a.py"
        src_file.write_text("class Foo:\n    pass\n")
        test_file = tmp_path / "test_a.py"
        test_file.write_text("def test_foo():\n    assert False\n")

        chunks = [
            _make_chunk("A", files=[str(src_file), str(test_file)], status="done"),
        ]
        plan_data = _make_plan_data(chunks=chunks)

        with patch("calx.serve.engine.verification.subprocess.run") as mock_run:
            def side_effect(cmd, **kwargs):
                if "-c" in cmd:
                    # Import check passes
                    return MagicMock(returncode=0, stderr="", stdout="")
                else:
                    # Test check fails
                    return MagicMock(
                        returncode=1,
                        stdout=f"FAILED {test_file}::test_foo - AssertionError",
                        stderr="",
                    )
            mock_run.side_effect = side_effect
            result = await run_wave_verification(plan_data, wave_id=1)

        assert result["overall"] == "fail"
        assert "A" in result["failing_chunks"]

    async def test_failing_chunks_includes_duplicate_failures(self, tmp_path):
        """failing_chunks must map duplicate definition failures back to chunks."""
        from calx.serve.engine.verification import run_wave_verification

        file_a = tmp_path / "a.py"
        file_a.write_text("class Widget:\n    pass\n")
        file_b = tmp_path / "b.py"
        file_b.write_text("class Widget:\n    pass\n")

        chunks = [
            _make_chunk("A", files=[str(file_a)], status="done"),
            _make_chunk("B", files=[str(file_b)], status="done"),
        ]
        plan_data = _make_plan_data(chunks=chunks)

        with patch("calx.serve.engine.verification.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            result = await run_wave_verification(plan_data, wave_id=1)

        assert result["overall"] == "fail"
        assert result["duplicate_check"]["passed"] is False
        # Both chunks should be in failing_chunks since they each have a file with the duplicate
        assert "A" in result["failing_chunks"]
        assert "B" in result["failing_chunks"]
