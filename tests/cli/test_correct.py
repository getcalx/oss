"""Tests for calx.cli.correct."""
from __future__ import annotations

import json
from pathlib import Path

import click
from click.testing import CliRunner

from calx.cli.correct import correct
from calx.core.config import default_config, save_config


@click.group()
def test_cli() -> None:
    pass


test_cli.add_command(correct)


def _setup_calx_project(tmp_path: Path, domains: list[str] | None = None) -> Path:
    """Create a .calx dir with config and return the project root."""
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()
    config = default_config(domains or ["api", "services"])
    save_config(calx_dir, config)
    return tmp_path


def test_correct_outputs_feedback(tmp_path: Path, monkeypatch: object) -> None:
    project = _setup_calx_project(tmp_path, ["api"])
    monkeypatch.chdir(project)  # type: ignore[attr-defined]

    runner = CliRunner()
    result = runner.invoke(test_cli, ["correct", "don't mock the database"])

    assert result.exit_code == 0
    assert "Logged as C001" in result.output
    assert "api" in result.output


def test_correct_json_output(tmp_path: Path, monkeypatch: object) -> None:
    project = _setup_calx_project(tmp_path, ["api"])
    monkeypatch.chdir(project)  # type: ignore[attr-defined]

    runner = CliRunner()
    result = runner.invoke(test_cli, ["correct", "--json", "test correction"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["id"] == "C001"
    assert data["domain"] == "api"
    assert data["type"] == "process"
    assert data["description"] == "test correction"
    assert data["status"] == "confirmed"
    assert "feedback" in data


def test_correct_domain_override(tmp_path: Path, monkeypatch: object) -> None:
    project = _setup_calx_project(tmp_path, ["api", "services"])
    monkeypatch.chdir(project)  # type: ignore[attr-defined]

    runner = CliRunner()
    result = runner.invoke(test_cli, ["correct", "-d", "services", "test override"])

    assert result.exit_code == 0
    assert "services" in result.output


def test_correct_type_architectural(tmp_path: Path, monkeypatch: object) -> None:
    project = _setup_calx_project(tmp_path, ["api"])
    monkeypatch.chdir(project)  # type: ignore[attr-defined]

    runner = CliRunner()
    result = runner.invoke(test_cli, ["correct", "--json", "-t", "architectural", "arch issue"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["type"] == "architectural"


def test_correct_not_calx_project(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.chdir(tmp_path)  # type: ignore[attr-defined]

    runner = CliRunner()
    result = runner.invoke(test_cli, ["correct", "should fail"])

    assert result.exit_code != 0
    assert "Not a Calx project" in result.output
