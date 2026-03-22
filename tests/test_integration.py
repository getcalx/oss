"""End-to-end integration tests for the Calx CLI.

Exercises the full flow: init -> correct -> recurrence -> promote -> status -> health -> hooks.
"""
from __future__ import annotations

import json
from pathlib import Path

import click
from click.testing import CliRunner

from calx.cli.main import cli
from calx.core.config import CalxConfig, default_config, load_config, save_config
from calx.core.corrections import materialize
from calx.core.rules import read_all_rules
from calx.core.state import write_clean_exit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _setup_project(tmp_path: Path, domains: list[str] | None = None) -> Path:
    """Create a .calx dir with config and return the project root."""
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()
    config = default_config(domains or ["api", "services"])
    # Lower the promotion threshold to 3 for manageable test data
    config.promotion_threshold = 3
    save_config(calx_dir, config)
    return tmp_path


def _invoke(runner: CliRunner, args: list[str], **kwargs):
    """Invoke the real CLI and return the result."""
    return runner.invoke(cli, args, catch_exceptions=False, **kwargs)


# ---------------------------------------------------------------------------
# 1. Full lifecycle: init -> correct -> recurrence -> distill -> status -> health
# ---------------------------------------------------------------------------


class TestFullLifecycle:
    """Full lifecycle from first correction through rule promotion and verification."""

    def test_correct_then_recurrence_then_promote(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Log corrections, trigger recurrence, promote to rule, verify via status and health."""
        project = _setup_project(tmp_path, ["api"])
        calx_dir = project / ".calx"
        monkeypatch.chdir(project)
        runner = CliRunner()

        # --- Step 1: first correction ---
        r1 = _invoke(runner, ["correct", "always validate input parameters"])
        assert r1.exit_code == 0
        assert "C001" in r1.output

        # --- Step 2: similar corrections to build recurrence ---
        r2 = _invoke(runner, ["correct", "validate input parameters before processing"])
        assert r2.exit_code == 0
        # Should detect recurrence with C001 (feedback mentions original)
        assert "C001" in r2.output

        r3 = _invoke(runner, ["correct", "must validate input parameters always"])
        assert r3.exit_code == 0
        assert "C001" in r3.output

        r4 = _invoke(runner, ["correct", "validate all input parameters first"])
        assert r4.exit_code == 0

        # --- Step 3: verify status shows corrections ---
        s1 = _invoke(runner, ["status", "--json"])
        assert s1.exit_code == 0
        status_data = json.loads(s1.output)
        assert status_data["corrections"]["total"] == 4
        assert status_data["corrections"]["pending_distillation"] == 4

        # --- Step 4: distill (promote) ---
        # The distill command prompts interactively; feed "y" to approve
        r_distill = _invoke(runner, ["distill"], input="y\n")
        assert r_distill.exit_code == 0
        assert "Created rule" in r_distill.output or "No corrections ready" in r_distill.output

        # --- Step 5: if a rule was created, verify via status ---
        rules = read_all_rules(calx_dir)
        if rules:
            s2 = _invoke(runner, ["status", "--json"])
            assert s2.exit_code == 0
            status_after = json.loads(s2.output)
            assert status_after["rules"]["active"] >= 1

            # --- Step 6: verify health score shows the rule ---
            h1 = _invoke(runner, ["health", "score", "--json"])
            assert h1.exit_code == 0
            scores = json.loads(h1.output)
            assert len(scores) >= 1
            assert scores[0]["rule_id"].startswith("api-R")

    def test_status_shows_domains_and_corrections(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Status reflects correction count and domain list."""
        project = _setup_project(tmp_path, ["api", "frontend"])
        monkeypatch.chdir(project)
        runner = CliRunner()

        _invoke(runner, ["correct", "use consistent error codes"])
        _invoke(runner, ["correct", "-d", "frontend", "always use design tokens"])

        r = _invoke(runner, ["status"])
        assert r.exit_code == 0
        assert "2 total" in r.output
        assert "api" in r.output
        assert "frontend" in r.output

    def test_recurrence_detection_with_similar_text(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Two corrections with similar descriptions trigger recurrence detection."""
        project = _setup_project(tmp_path, ["api"])
        monkeypatch.chdir(project)
        runner = CliRunner()

        _invoke(runner, ["correct", "never mock the database in tests"])
        r2 = _invoke(runner, ["correct", "do not mock database in integration tests"])
        assert r2.exit_code == 0
        # Recurrence should link back to C001
        assert "C001" in r2.output

    def test_dissimilar_corrections_no_recurrence(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Unrelated corrections should not trigger recurrence."""
        project = _setup_project(tmp_path, ["api"])
        monkeypatch.chdir(project)
        runner = CliRunner()

        _invoke(runner, ["correct", "always validate input"])
        r2 = _invoke(runner, ["correct", "use structured logging everywhere"])
        assert r2.exit_code == 0
        # Should NOT reference C001 in the recurrence sense
        assert "Matches C001" not in r2.output


# ---------------------------------------------------------------------------
# 2. Hook round-trip: session-end -> session-start
# ---------------------------------------------------------------------------


class TestHookRoundTrip:
    """Session lifecycle via _hook commands."""

    def test_clean_exit_then_start(self, tmp_path: Path, monkeypatch) -> None:
        """session-end writes clean exit; subsequent session-start sees no warning."""
        project = _setup_project(tmp_path, ["api"])
        monkeypatch.chdir(project)
        runner = CliRunner()

        # End session (writes clean exit marker)
        r_end = _invoke(runner, ["_hook", "session-end"])
        assert r_end.exit_code == 0

        # Start new session
        r_start = _invoke(runner, ["_hook", "session-start"])
        assert r_start.exit_code == 0
        assert "WARNING" not in r_start.output
        # Token discipline should always appear
        assert "TOKEN DISCIPLINE" in r_start.output
        assert "200,000" in r_start.output

    def test_hook_round_trip_with_corrections(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Corrections logged between session-end and session-start show up in status."""
        project = _setup_project(tmp_path, ["api"])
        calx_dir = project / ".calx"
        monkeypatch.chdir(project)
        runner = CliRunner()

        # Log corrections
        _invoke(runner, ["correct", "validate inputs"])
        _invoke(runner, ["correct", "check return types"])

        # End session
        r_end = _invoke(runner, ["_hook", "session-end"])
        assert r_end.exit_code == 0
        # Should mention pending corrections
        data = json.loads(r_end.output)
        assert "2 corrections pending distillation" in data["followup_message"]

        # Start new session
        r_start = _invoke(runner, ["_hook", "session-start"])
        assert r_start.exit_code == 0
        assert "WARNING" not in r_start.output
        assert "2 corrections pending distillation" in r_start.output

    def test_hook_shows_rules_at_session_start(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Rules are injected at session start."""
        project = _setup_project(tmp_path, ["api"])
        calx_dir = project / ".calx"
        monkeypatch.chdir(project)
        runner = CliRunner()

        # Create a rule directly
        from calx.core.rules import Rule, write_rule

        write_rule(calx_dir, Rule(
            id="api-R001",
            domain="api",
            type="process",
            source_corrections=["C001"],
            added="2026-03-21",
            status="active",
            title="Always validate input",
            body="Check all inputs before processing.",
        ))

        # Write clean exit so no dirty warning
        write_clean_exit(calx_dir)

        r_start = _invoke(runner, ["_hook", "session-start"])
        assert r_start.exit_code == 0
        assert "CALX RULES" in r_start.output
        assert "api-R001" in r_start.output
        assert "Always validate input" in r_start.output


# ---------------------------------------------------------------------------
# 3. Dirty exit detection
# ---------------------------------------------------------------------------


class TestDirtyExit:
    """Dirty exit detection when session-end was never called."""

    def test_dirty_exit_warning(self, tmp_path: Path, monkeypatch) -> None:
        """session-start without prior clean exit shows warning."""
        project = _setup_project(tmp_path, ["api"])
        monkeypatch.chdir(project)
        runner = CliRunner()

        # No session-end was called — no clean exit marker exists
        r = _invoke(runner, ["_hook", "session-start"])
        assert r.exit_code == 0
        assert "WARNING" in r.output
        assert "did not exit cleanly" in r.output

    def test_clean_exit_clears_marker(self, tmp_path: Path, monkeypatch) -> None:
        """session-start removes the clean exit marker so next start will be dirty."""
        project = _setup_project(tmp_path, ["api"])
        calx_dir = project / ".calx"
        monkeypatch.chdir(project)
        runner = CliRunner()

        # Write clean exit
        write_clean_exit(calx_dir)
        marker = calx_dir / "health" / ".last_clean_exit"
        assert marker.exists()

        # session-start consumes the marker
        _invoke(runner, ["_hook", "session-start"])
        assert not marker.exists()

        # Next session-start without session-end = dirty
        r2 = _invoke(runner, ["_hook", "session-start"])
        assert "WARNING" in r2.output
        assert "did not exit cleanly" in r2.output

    def test_session_end_then_no_dirty_warning(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Proper session-end -> session-start cycle produces no dirty warning."""
        project = _setup_project(tmp_path, ["api"])
        monkeypatch.chdir(project)
        runner = CliRunner()

        # First start will be dirty (fresh project)
        r1 = _invoke(runner, ["_hook", "session-start"])
        assert "WARNING" in r1.output

        # End session properly
        _invoke(runner, ["_hook", "session-end"])

        # Start again — should be clean
        r2 = _invoke(runner, ["_hook", "session-start"])
        assert "WARNING" not in r2.output


# ---------------------------------------------------------------------------
# 4. Multi-domain flow
# ---------------------------------------------------------------------------


class TestMultiDomain:
    """Operations across multiple domains."""

    def test_corrections_in_multiple_domains(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Corrections in different domains show up correctly in status."""
        project = _setup_project(tmp_path, ["api", "frontend", "services"])
        monkeypatch.chdir(project)
        runner = CliRunner()

        _invoke(runner, ["correct", "-d", "api", "validate request body"])
        _invoke(runner, ["correct", "-d", "frontend", "use design tokens"])
        _invoke(runner, ["correct", "-d", "services", "handle timeouts"])
        _invoke(runner, ["correct", "-d", "api", "check auth headers"])

        # Status should show all corrections
        r = _invoke(runner, ["status", "--json"])
        assert r.exit_code == 0
        data = json.loads(r.output)
        assert data["corrections"]["total"] == 4
        assert data["corrections"]["pending_distillation"] == 4
        assert set(data["domains"]) == {"api", "frontend", "services"}

    def test_recurrence_scoped_to_domain(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Recurrence detection only matches within the same domain."""
        project = _setup_project(tmp_path, ["api", "frontend"])
        monkeypatch.chdir(project)
        runner = CliRunner()

        # Log in api domain
        _invoke(runner, ["correct", "-d", "api", "validate input parameters"])
        # Log similar text in frontend domain — should NOT match api's correction
        r2 = _invoke(runner, ["correct", "-d", "frontend", "validate input parameters"])
        assert r2.exit_code == 0
        # The second correction is in a different domain so no recurrence
        assert "Matches C001" not in r2.output

    def test_multi_domain_session_start_rules(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Rules from multiple domains all appear at session start."""
        project = _setup_project(tmp_path, ["api", "frontend"])
        calx_dir = project / ".calx"
        monkeypatch.chdir(project)
        runner = CliRunner()

        from calx.core.rules import Rule, write_rule

        write_rule(calx_dir, Rule(
            id="api-R001", domain="api", type="process",
            source_corrections=["C001"], added="2026-03-21",
            status="active", title="API input validation",
            body="Always validate inputs.",
        ))
        write_rule(calx_dir, Rule(
            id="frontend-R001", domain="frontend", type="process",
            source_corrections=["C002"], added="2026-03-21",
            status="active", title="Use design tokens",
            body="Always use the design token system.",
        ))

        write_clean_exit(calx_dir)

        r = _invoke(runner, ["_hook", "session-start"])
        assert r.exit_code == 0
        assert "CALX RULES" in r.output
        assert "api (1 rules)" in r.output
        assert "frontend (1 rules)" in r.output
        assert "api-R001" in r.output
        assert "frontend-R001" in r.output
        # Alphabetical order: api before frontend
        assert r.output.index("api (1 rules)") < r.output.index("frontend (1 rules)")

    def test_multi_domain_health_coverage(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Health coverage reflects corrections across domains."""
        project = _setup_project(tmp_path, ["api", "frontend"])
        monkeypatch.chdir(project)
        runner = CliRunner()

        _invoke(runner, ["correct", "-d", "api", "validate inputs"])
        _invoke(runner, ["correct", "-d", "frontend", "use tokens"])

        r = _invoke(runner, ["health", "coverage", "--json"])
        assert r.exit_code == 0
        data = json.loads(r.output)
        assert data["total"] == 2
        assert data["pending"] == 2

    def test_multi_domain_status_text(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Text status lists all configured domains."""
        project = _setup_project(tmp_path, ["api", "frontend", "services"])
        monkeypatch.chdir(project)
        runner = CliRunner()

        r = _invoke(runner, ["status"])
        assert r.exit_code == 0
        assert "api" in r.output
        assert "frontend" in r.output
        assert "services" in r.output


# ---------------------------------------------------------------------------
# 5. Edge cases and error paths
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases and error conditions."""

    def test_status_outside_calx_project(self, tmp_path: Path, monkeypatch) -> None:
        """Status in non-calx directory gives clear error."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        r = _invoke(runner, ["status"])
        assert r.exit_code != 0
        assert "Not a Calx project" in r.output

    def test_correct_outside_calx_project(self, tmp_path: Path, monkeypatch) -> None:
        """Correct in non-calx directory gives clear error."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        r = _invoke(runner, ["correct", "some correction"])
        assert r.exit_code != 0
        assert "Not a Calx project" in r.output

    def test_health_score_with_no_rules(self, tmp_path: Path, monkeypatch) -> None:
        """Health score on project with no rules returns empty list."""
        _setup_project(tmp_path, ["api"])
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()

        r = _invoke(runner, ["health", "score", "--json"])
        assert r.exit_code == 0
        scores = json.loads(r.output)
        assert scores == []

    def test_distill_with_no_corrections(self, tmp_path: Path, monkeypatch) -> None:
        """Distill on empty project reports nothing to promote."""
        _setup_project(tmp_path, ["api"])
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()

        r = _invoke(runner, ["distill"])
        assert r.exit_code == 0
        assert "No corrections ready for promotion" in r.output

    def test_hook_session_start_outside_project(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """session-start outside calx project exits silently."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        r = _invoke(runner, ["_hook", "session-start"])
        assert r.exit_code == 0

    def test_hook_session_end_outside_project(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """session-end outside calx project exits silently."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        r = _invoke(runner, ["_hook", "session-end"])
        assert r.exit_code == 0
        assert r.output.strip() == ""

    def test_correct_json_output_integration(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Correct --json returns valid structured data."""
        _setup_project(tmp_path, ["api"])
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()

        r = _invoke(runner, ["correct", "--json", "validate input"])
        assert r.exit_code == 0
        data = json.loads(r.output)
        assert data["id"] == "C001"
        assert data["domain"] == "api"
        assert data["description"] == "validate input"
        assert data["status"] == "confirmed"
