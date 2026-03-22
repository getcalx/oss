"""Tests for calx.cli.health."""
from __future__ import annotations

import json
from pathlib import Path

import click
from click.testing import CliRunner

from calx.cli.health import health
from calx.core.config import CalxConfig, save_config
from calx.core.corrections import create_correction


def _setup_calx(tmp_path: Path, **config_kwargs) -> Path:
    """Create a .calx dir with config and return the calx_dir path."""
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()
    defaults = {
        "install_id": "test-id",
        "domains": ["api", "frontend"],
    }
    defaults.update(config_kwargs)
    save_config(calx_dir, CalxConfig(**defaults))
    return calx_dir


def _make_cli():
    """Create a standalone Click group with the health command group."""
    group = click.Group()
    group.add_command(health)
    return group


def test_coverage_shows_info(tmp_path: Path, monkeypatch):
    """health coverage shows coverage info."""
    calx_dir = _setup_calx(tmp_path)
    monkeypatch.chdir(tmp_path)

    # Create a correction so we have data
    create_correction(calx_dir, domain="api", description="test correction")

    runner = CliRunner()
    result = runner.invoke(_make_cli(), ["health", "coverage"])
    assert result.exit_code == 0
    assert "Coverage:" in result.output
    assert "distilled" in result.output
    assert "pending" in result.output


def test_coverage_json_output(tmp_path: Path, monkeypatch):
    """health coverage --json outputs valid JSON."""
    calx_dir = _setup_calx(tmp_path)
    monkeypatch.chdir(tmp_path)

    create_correction(calx_dir, domain="api", description="test correction")

    runner = CliRunner()
    result = runner.invoke(_make_cli(), ["health", "coverage", "--json"])
    assert result.exit_code == 0

    data = json.loads(result.output)
    assert "total" in data
    assert "distilled" in data
    assert "pending" in data
    assert "gaps" in data
    assert data["total"] == 1
    assert data["pending"] == 1


def test_coverage_empty_project(tmp_path: Path, monkeypatch):
    """health coverage on empty project shows zeros."""
    _setup_calx(tmp_path)
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(_make_cli(), ["health", "coverage"])
    assert result.exit_code == 0
    assert "0/0" in result.output


def test_coverage_not_a_calx_project(tmp_path: Path, monkeypatch):
    """health coverage exits with error when not a Calx project."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(_make_cli(), ["health", "coverage"])
    assert result.exit_code != 0
    assert "Not a Calx project" in result.output


def test_conflicts_not_a_calx_project(tmp_path: Path, monkeypatch):
    """health conflicts exits with error when not a Calx project."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(_make_cli(), ["health", "conflicts"])
    assert result.exit_code != 0
    assert "Not a Calx project" in result.output


def test_conflicts_no_conflicts(tmp_path: Path, monkeypatch):
    """health conflicts shows no conflicts when rules don't conflict."""
    _setup_calx(tmp_path)
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(_make_cli(), ["health", "conflicts"])
    assert result.exit_code == 0
    assert "No conflicts detected" in result.output
