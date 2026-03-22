"""Tests for calx.cli.distill."""
from __future__ import annotations

from pathlib import Path

import click
from click.testing import CliRunner

from calx.cli.distill import distill
from calx.core.config import CalxConfig, save_config


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
    """Create a standalone Click group with the distill command."""
    group = click.Group()
    group.add_command(distill)
    return group


def test_not_a_calx_project(tmp_path: Path, monkeypatch):
    """Exits with error when not a Calx project."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(_make_cli(), ["distill"])
    assert result.exit_code != 0
    assert "Not a Calx project" in result.output


def test_no_corrections_ready(tmp_path: Path, monkeypatch):
    """Shows 'No corrections ready' when promotion module has no candidates."""
    _setup_calx(tmp_path)
    monkeypatch.chdir(tmp_path)

    # Monkeypatch the import to simulate the promotion module being available
    # but returning no candidates
    import calx.cli.distill as distill_mod

    def _fake_run_promotion(calx_dir, config):
        click.echo("No corrections ready for promotion.")

    monkeypatch.setattr(distill_mod, "_run_promotion", _fake_run_promotion)

    runner = CliRunner()
    result = runner.invoke(_make_cli(), ["distill"])
    assert result.exit_code == 0
    assert "No corrections ready for promotion" in result.output


def test_review_flag_calls_review(tmp_path: Path, monkeypatch):
    """--review triggers the review flow."""
    _setup_calx(tmp_path)
    monkeypatch.chdir(tmp_path)

    import calx.cli.distill as distill_mod

    def _fake_run_review(calx_dir):
        click.echo("Review module not available.")

    monkeypatch.setattr(distill_mod, "_run_review", _fake_run_review)

    runner = CliRunner()
    result = runner.invoke(_make_cli(), ["distill", "--review"])
    assert result.exit_code == 0
    assert "Review module not available" in result.output
