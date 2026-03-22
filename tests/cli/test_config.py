"""Tests for calx.cli.config_cmd."""
from __future__ import annotations

import json
from pathlib import Path

import click
from click.testing import CliRunner

from calx.cli.config_cmd import config_cmd
from calx.core.config import CalxConfig, load_config, save_config


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
    """Create a standalone Click group with the config command."""
    group = click.Group()
    group.add_command(config_cmd)
    return group


def test_show_current_config(tmp_path: Path, monkeypatch):
    """Shows current config values."""
    _setup_calx(tmp_path, domains=["api", "frontend"])
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(_make_cli(), ["config"])
    assert result.exit_code == 0
    assert "Calx Config" in result.output
    assert "api, frontend" in result.output
    assert "Promotion threshold: 3" in result.output


def test_set_promotion_threshold(tmp_path: Path, monkeypatch):
    """--set promotion_threshold 5 updates config."""
    calx_dir = _setup_calx(tmp_path)
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(_make_cli(), ["config", "--set", "promotion_threshold", "5"])
    assert result.exit_code == 0
    assert "Set promotion_threshold = 5" in result.output

    # Verify the config was actually saved
    config = load_config(calx_dir)
    assert config.promotion_threshold == 5


def test_unknown_key_shows_error(tmp_path: Path, monkeypatch):
    """Unknown key shows error message."""
    _setup_calx(tmp_path)
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(_make_cli(), ["config", "--set", "nonexistent_key", "val"])
    assert "Unknown config key: nonexistent_key" in result.output


def test_not_a_calx_project(tmp_path: Path, monkeypatch):
    """Exits with error when not a Calx project."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(_make_cli(), ["config"])
    assert result.exit_code != 0
    assert "Not a Calx project" in result.output


def test_set_agent_naming(tmp_path: Path, monkeypatch):
    """--set agent_naming developer updates config."""
    calx_dir = _setup_calx(tmp_path)
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(_make_cli(), ["config", "--set", "agent_naming", "developer"])
    assert result.exit_code == 0
    assert "Set agent_naming = developer" in result.output

    config = load_config(calx_dir)
    assert config.agent_naming == "developer"


def test_set_agent_naming_invalid(tmp_path: Path, monkeypatch):
    """--set agent_naming with invalid value shows error."""
    _setup_calx(tmp_path)
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(_make_cli(), ["config", "--set", "agent_naming", "bad"])
    assert "Invalid value" in result.output


def test_set_stats_opt_in(tmp_path: Path, monkeypatch):
    """--set stats_opt_in true updates config."""
    calx_dir = _setup_calx(tmp_path)
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(_make_cli(), ["config", "--set", "stats_opt_in", "true"])
    assert result.exit_code == 0

    config = load_config(calx_dir)
    assert config.stats_opt_in is True
