"""Tests for calx.cli.status."""
from __future__ import annotations

import json
from pathlib import Path

import click
from click.testing import CliRunner

from calx.cli.status import status
from calx.core.config import default_config, save_config
from calx.core.corrections import create_correction
from calx.core.rules import Rule, write_rule
from calx.core.state import write_clean_exit


@click.group()
def test_cli() -> None:
    pass


test_cli.add_command(status)


def _setup_calx_project(tmp_path: Path, domains: list[str] | None = None) -> Path:
    """Create a .calx dir with config and return the project root."""
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()
    config = default_config(domains or ["api", "services"])
    save_config(calx_dir, config)
    return tmp_path


def test_status_shows_domains(tmp_path: Path, monkeypatch: object) -> None:
    project = _setup_calx_project(tmp_path, ["api", "services"])
    monkeypatch.chdir(project)  # type: ignore[attr-defined]

    runner = CliRunner()
    result = runner.invoke(test_cli, ["status"])

    assert result.exit_code == 0
    assert "Calx Status" in result.output
    assert "api" in result.output
    assert "services" in result.output


def test_status_shows_corrections_and_rules(tmp_path: Path, monkeypatch: object) -> None:
    project = _setup_calx_project(tmp_path, ["api"])
    calx_dir = project / ".calx"
    monkeypatch.chdir(project)  # type: ignore[attr-defined]

    # Create a correction
    create_correction(calx_dir, domain="api", description="test correction")

    # Create a rule
    rule = Rule(
        id="api-R001",
        domain="api",
        type="process",
        source_corrections=["C001"],
        added="2026-03-21",
        status="active",
        title="Test Rule",
        body="Do the thing.",
    )
    write_rule(calx_dir, rule)

    runner = CliRunner()
    result = runner.invoke(test_cli, ["status"])

    assert result.exit_code == 0
    assert "1 total" in result.output
    assert "1 pending distillation" in result.output
    assert "1 active" in result.output


def test_status_json_output(tmp_path: Path, monkeypatch: object) -> None:
    project = _setup_calx_project(tmp_path, ["api", "services"])
    calx_dir = project / ".calx"
    monkeypatch.chdir(project)  # type: ignore[attr-defined]

    # Write a clean exit marker
    write_clean_exit(calx_dir)

    runner = CliRunner()
    result = runner.invoke(test_cli, ["status", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "domains" in data
    assert data["domains"] == ["api", "services"]
    assert "corrections" in data
    assert data["corrections"]["total"] == 0
    assert data["corrections"]["pending_distillation"] == 0
    assert "rules" in data
    assert data["rules"]["active"] == 0
    assert data["rules"]["domains"] == 0
    assert "last_clean_exit" in data
    assert data["last_clean_exit"] is not None


def test_status_not_calx_project(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.chdir(tmp_path)  # type: ignore[attr-defined]

    runner = CliRunner()
    result = runner.invoke(test_cli, ["status"])

    assert result.exit_code != 0
    assert "Not a Calx project" in result.output
