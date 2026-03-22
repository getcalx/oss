"""Tests for calx.cli.stats."""
from __future__ import annotations

import json
from pathlib import Path

import click
from click.testing import CliRunner

from calx.cli.stats import stats
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
    """Create a standalone Click group with the stats command."""
    group = click.Group()
    group.add_command(stats)
    return group


def test_stats_summary(tmp_path: Path, monkeypatch):
    """Shows stats summary."""
    calx_dir = _setup_calx(tmp_path)
    monkeypatch.chdir(tmp_path)

    create_correction(calx_dir, domain="api", description="first correction")
    create_correction(
        calx_dir,
        domain="api",
        description="second correction",
        correction_type="architectural",
    )

    runner = CliRunner()
    result = runner.invoke(_make_cli(), ["stats"])
    assert result.exit_code == 0
    assert "Calx Stats" in result.output
    assert "Corrections: 2" in result.output
    assert "api: 2" in result.output
    assert "Recurrence rate: 0%" in result.output


def test_stats_json_output(tmp_path: Path, monkeypatch):
    """--json outputs valid JSON."""
    calx_dir = _setup_calx(tmp_path)
    monkeypatch.chdir(tmp_path)

    create_correction(calx_dir, domain="api", description="test")
    create_correction(
        calx_dir,
        domain="frontend",
        description="test2",
        correction_type="architectural",
    )

    runner = CliRunner()
    result = runner.invoke(_make_cli(), ["stats", "--json"])
    assert result.exit_code == 0

    data = json.loads(result.output)
    assert data["corrections"] == 2
    assert "type_split" in data
    assert "domain_counts" in data
    assert "recurrence_rate" in data
    assert data["rules"] == 0


def test_stats_empty_project(tmp_path: Path, monkeypatch):
    """Stats on empty project shows zeros."""
    _setup_calx(tmp_path)
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(_make_cli(), ["stats"])
    assert result.exit_code == 0
    assert "Corrections: 0" in result.output
    assert "Recurrence rate: 0%" in result.output


def test_stats_not_a_calx_project(tmp_path: Path, monkeypatch):
    """Exits with error when not a Calx project."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(_make_cli(), ["stats"])
    assert result.exit_code != 0
    assert "Not a Calx project" in result.output


def test_stats_json_empty_project(tmp_path: Path, monkeypatch):
    """--json on empty project outputs valid JSON with zeros."""
    _setup_calx(tmp_path)
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(_make_cli(), ["stats", "--json"])
    assert result.exit_code == 0

    data = json.loads(result.output)
    assert data["corrections"] == 0
    assert data["recurrence_rate"] == 0.0
    assert data["rules"] == 0
