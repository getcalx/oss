"""Tests for calx.cli.hook_cmd — session-start and session-end."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import click
from click.testing import CliRunner

from calx.cli.hook_cmd import hook_group
from calx.core.config import CalxConfig, default_config, save_config
from calx.core.corrections import CorrectionEvent, append_event, create_correction
from calx.core.rules import Rule, write_rule
from calx.core.state import write_clean_exit


@click.group()
def test_cli() -> None:
    pass


test_cli.add_command(hook_group)


def _setup_calx_project(tmp_path: Path, domains: list[str] | None = None) -> Path:
    """Create a .calx dir with config and return the project root."""
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()
    config = default_config(domains or ["api", "services"])
    save_config(calx_dir, config)
    return tmp_path


# --- session-start tests ---


def test_session_start_no_calx_dir(tmp_path: Path, monkeypatch: object) -> None:
    """Exit silently when not in a Calx project."""
    monkeypatch.chdir(tmp_path)  # type: ignore[attr-defined]
    runner = CliRunner()
    result = runner.invoke(test_cli, ["_hook", "session-start"])
    assert result.exit_code == 0
    assert result.output.strip() == "" or "TOKEN DISCIPLINE" not in result.output


def test_session_start_clean_exit(tmp_path: Path, monkeypatch: object) -> None:
    """No dirty exit warning when previous session exited cleanly."""
    project = _setup_calx_project(tmp_path)
    calx_dir = project / ".calx"
    write_clean_exit(calx_dir)
    monkeypatch.chdir(project)  # type: ignore[attr-defined]

    runner = CliRunner()
    result = runner.invoke(test_cli, ["_hook", "session-start"])
    assert result.exit_code == 0
    assert "WARNING" not in result.output


def test_session_start_dirty_exit(tmp_path: Path, monkeypatch: object) -> None:
    """Warn when previous session did not exit cleanly."""
    project = _setup_calx_project(tmp_path)
    # No clean exit marker = dirty exit
    monkeypatch.chdir(project)  # type: ignore[attr-defined]

    runner = CliRunner()
    result = runner.invoke(test_cli, ["_hook", "session-start"])
    assert result.exit_code == 0
    assert "WARNING" in result.output
    assert "did not exit cleanly" in result.output


def test_session_start_token_discipline(tmp_path: Path, monkeypatch: object) -> None:
    """Token discipline instructions always appear."""
    project = _setup_calx_project(tmp_path)
    calx_dir = project / ".calx"
    write_clean_exit(calx_dir)
    monkeypatch.chdir(project)  # type: ignore[attr-defined]

    runner = CliRunner()
    result = runner.invoke(test_cli, ["_hook", "session-start"])
    assert result.exit_code == 0
    assert "TOKEN DISCIPLINE" in result.output
    assert "200,000" in result.output
    assert "250,000" in result.output


def test_session_start_rule_injection(tmp_path: Path, monkeypatch: object) -> None:
    """Rules are injected at session start."""
    project = _setup_calx_project(tmp_path, ["api"])
    calx_dir = project / ".calx"
    write_clean_exit(calx_dir)

    rule = Rule(
        id="api-R001",
        domain="api",
        type="process",
        source_corrections=["C001"],
        added="2026-03-21",
        status="active",
        title="Always validate input",
        body="Check all inputs before processing.",
    )
    write_rule(calx_dir, rule)
    monkeypatch.chdir(project)  # type: ignore[attr-defined]

    runner = CliRunner()
    result = runner.invoke(test_cli, ["_hook", "session-start"])
    assert result.exit_code == 0
    assert "CALX RULES" in result.output
    assert "api (1 rule)" in result.output
    assert "api-R001" in result.output
    assert "Always validate input" in result.output


def test_session_start_multiple_domains(tmp_path: Path, monkeypatch: object) -> None:
    """Rules from multiple domains appear sorted."""
    project = _setup_calx_project(tmp_path, ["api", "frontend"])
    calx_dir = project / ".calx"
    write_clean_exit(calx_dir)

    write_rule(calx_dir, Rule(
        id="api-R001", domain="api", type="process",
        source_corrections=["C001"], added="2026-03-21",
        status="active", title="API rule", body="API body.",
    ))
    write_rule(calx_dir, Rule(
        id="frontend-R001", domain="frontend", type="process",
        source_corrections=["C002"], added="2026-03-21",
        status="active", title="Frontend rule", body="Frontend body.",
    ))
    monkeypatch.chdir(project)  # type: ignore[attr-defined]

    runner = CliRunner()
    result = runner.invoke(test_cli, ["_hook", "session-start"])
    assert result.exit_code == 0
    assert "api (1 rule)" in result.output
    assert "frontend (1 rule)" in result.output
    # api should appear before frontend (sorted)
    assert result.output.index("api") < result.output.index("frontend")


def test_session_start_integrity_repair(tmp_path: Path, monkeypatch: object) -> None:
    """Malformed JSONL lines get repaired."""
    project = _setup_calx_project(tmp_path)
    calx_dir = project / ".calx"
    write_clean_exit(calx_dir)

    # Write a valid event then a corrupt line
    corr_path = calx_dir / "corrections.jsonl"
    corr_path.write_text(
        '{"timestamp":"t","event_type":"created","correction_id":"C001","data":{}}\n'
        'not valid json\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(project)  # type: ignore[attr-defined]

    runner = CliRunner()
    result = runner.invoke(test_cli, ["_hook", "session-start"])
    assert result.exit_code == 0
    assert "Repaired 1 malformed" in result.output


def test_session_start_undistilled_count(tmp_path: Path, monkeypatch: object) -> None:
    """Shows undistilled correction count."""
    project = _setup_calx_project(tmp_path, ["api"])
    calx_dir = project / ".calx"
    write_clean_exit(calx_dir)

    create_correction(calx_dir, domain="api", description="test correction 1")
    create_correction(calx_dir, domain="api", description="test correction 2")
    monkeypatch.chdir(project)  # type: ignore[attr-defined]

    runner = CliRunner()
    result = runner.invoke(test_cli, ["_hook", "session-start"])
    assert result.exit_code == 0
    assert "2 corrections pending distillation" in result.output


def test_session_start_effectiveness_signal(tmp_path: Path, monkeypatch: object) -> None:
    """Shows correction delta between sessions."""
    project = _setup_calx_project(tmp_path, ["api"])
    calx_dir = project / ".calx"
    write_clean_exit(calx_dir)

    # Create corrections with different session IDs
    create_correction(
        calx_dir, domain="api", description="old issue",
        session_id="session-1",
    )
    create_correction(
        calx_dir, domain="api", description="old issue 2",
        session_id="session-1",
    )
    create_correction(
        calx_dir, domain="api", description="new issue",
        session_id="session-2",
    )
    monkeypatch.chdir(project)  # type: ignore[attr-defined]

    runner = CliRunner()
    result = runner.invoke(test_cli, ["_hook", "session-start"])
    assert result.exit_code == 0
    assert "api: 1 corrections last session (down from 2)" in result.output


def test_session_start_effectiveness_single_session(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Shows correction count without delta when only one session."""
    project = _setup_calx_project(tmp_path, ["api"])
    calx_dir = project / ".calx"
    write_clean_exit(calx_dir)

    create_correction(
        calx_dir, domain="api", description="issue",
        session_id="session-1",
    )
    monkeypatch.chdir(project)  # type: ignore[attr-defined]

    runner = CliRunner()
    result = runner.invoke(test_cli, ["_hook", "session-start"])
    assert result.exit_code == 0
    assert "api: 1 corrections last session." in result.output


def test_session_start_removes_clean_exit(tmp_path: Path, monkeypatch: object) -> None:
    """Clean exit marker is removed after session start."""
    project = _setup_calx_project(tmp_path)
    calx_dir = project / ".calx"
    write_clean_exit(calx_dir)

    marker = calx_dir / "health" / ".last_clean_exit"
    assert marker.exists()

    monkeypatch.chdir(project)  # type: ignore[attr-defined]
    runner = CliRunner()
    result = runner.invoke(test_cli, ["_hook", "session-start"])
    assert result.exit_code == 0
    assert not marker.exists()


# --- session-end tests ---


def test_session_end_no_calx_dir(tmp_path: Path, monkeypatch: object) -> None:
    """Exit silently when not in a Calx project."""
    monkeypatch.chdir(tmp_path)  # type: ignore[attr-defined]
    runner = CliRunner()
    result = runner.invoke(test_cli, ["_hook", "session-end"])
    assert result.exit_code == 0
    assert result.output.strip() == ""


def test_session_end_writes_clean_exit(tmp_path: Path, monkeypatch: object) -> None:
    """Clean exit marker is written at session end."""
    project = _setup_calx_project(tmp_path)
    calx_dir = project / ".calx"
    monkeypatch.chdir(project)  # type: ignore[attr-defined]

    runner = CliRunner()
    result = runner.invoke(test_cli, ["_hook", "session-end"])
    assert result.exit_code == 0

    marker = calx_dir / "health" / ".last_clean_exit"
    assert marker.exists()


def test_session_end_undistilled_message(tmp_path: Path, monkeypatch: object) -> None:
    """Reports undistilled corrections."""
    project = _setup_calx_project(tmp_path, ["api"])
    calx_dir = project / ".calx"
    create_correction(calx_dir, domain="api", description="fix X")
    monkeypatch.chdir(project)  # type: ignore[attr-defined]

    runner = CliRunner()
    result = runner.invoke(test_cli, ["_hook", "session-end"])
    assert result.exit_code == 0
    assert "1 corrections pending distillation" in result.output


def test_session_end_no_output_when_clean(tmp_path: Path, monkeypatch: object) -> None:
    """No output when nothing to report (no undistilled, no uncommitted)."""
    project = _setup_calx_project(tmp_path)
    # Initialize as a git repo with clean state
    monkeypatch.chdir(project)  # type: ignore[attr-defined]

    import subprocess
    subprocess.run(["git", "init"], capture_output=True, cwd=str(project))
    subprocess.run(["git", "add", "."], capture_output=True, cwd=str(project))
    subprocess.run(
        ["git", "commit", "-m", "init", "--allow-empty"],
        capture_output=True, cwd=str(project),
    )

    runner = CliRunner()
    result = runner.invoke(test_cli, ["_hook", "session-end"])
    assert result.exit_code == 0
    # No JSON output when nothing to report
    assert result.output.strip() == ""


def test_session_end_uncommitted_changes(tmp_path: Path, monkeypatch: object) -> None:
    """Warns about uncommitted changes."""
    project = _setup_calx_project(tmp_path)
    monkeypatch.chdir(project)  # type: ignore[attr-defined]

    import subprocess
    subprocess.run(["git", "init"], capture_output=True, cwd=str(project))
    subprocess.run(["git", "add", "."], capture_output=True, cwd=str(project))
    subprocess.run(
        ["git", "commit", "-m", "init"],
        capture_output=True, cwd=str(project),
    )
    # Create an uncommitted file
    (project / "dirty.txt").write_text("uncommitted", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(test_cli, ["_hook", "session-end"])
    assert result.exit_code == 0
    assert "Uncommitted changes" in result.output


def test_session_end_stats_not_posted_when_not_opted_in(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Stats are not posted when stats_opt_in is False."""
    project = _setup_calx_project(tmp_path)
    monkeypatch.chdir(project)  # type: ignore[attr-defined]

    # Track if post_stats was called
    calls: list[object] = []
    monkeypatch.setattr(  # type: ignore[attr-defined]
        "calx.cli.hook_cmd.post_stats",
        lambda payload: calls.append(payload) or True,
    )

    runner = CliRunner()
    runner.invoke(test_cli, ["_hook", "session-end"])
    assert len(calls) == 0


def test_session_end_stats_posted_when_opted_in(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Stats are posted when stats_opt_in is True."""
    project = _setup_calx_project(tmp_path)
    calx_dir = project / ".calx"

    from calx.core.config import load_config, save_config
    config = load_config(calx_dir)
    config.stats_opt_in = True
    save_config(calx_dir, config)

    monkeypatch.chdir(project)  # type: ignore[attr-defined]

    calls: list[object] = []
    monkeypatch.setattr(  # type: ignore[attr-defined]
        "calx.cli.hook_cmd.post_stats",
        lambda payload: calls.append(payload) or True,
    )

    runner = CliRunner()
    runner.invoke(test_cli, ["_hook", "session-end"])
    assert len(calls) == 1
