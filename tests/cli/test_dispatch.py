"""Tests for calx.cli.dispatch_cmd."""
from __future__ import annotations

from pathlib import Path

import click
from click.testing import CliRunner

from calx.cli.dispatch_cmd import dispatch
from calx.core.config import CalxConfig, save_config
from calx.core.rules import Rule, write_rule


def _setup_calx(tmp_path: Path, **config_kwargs) -> Path:
    """Create a .calx dir with config and return the calx_dir path."""
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()
    defaults = {
        "install_id": "test-id",
        "domains": ["api", "frontend"],
        "agent_naming": "self",
    }
    defaults.update(config_kwargs)
    save_config(calx_dir, CalxConfig(**defaults))
    return calx_dir


def _make_rule(domain: str = "api", num: int = 1, **kwargs) -> Rule:
    defaults = {
        "id": f"{domain}-R{num:03d}",
        "domain": domain,
        "type": "process",
        "source_corrections": ["C001"],
        "added": "2026-03-21",
        "status": "active",
        "title": "Test rule",
        "body": "This is a test rule.",
    }
    defaults.update(kwargs)
    return Rule(**defaults)


def _make_cli():
    """Create a standalone Click group with the dispatch command."""
    group = click.Group()
    group.add_command(dispatch)
    return group


def test_dispatch_generates_prompt(tmp_path: Path, monkeypatch):
    """Generates dispatch prompt with domain."""
    _setup_calx(tmp_path)
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(
        _make_cli(), ["dispatch", "api", "--task", "Build the users endpoint"]
    )
    assert result.exit_code == 0
    assert "# Dispatch: api" in result.output
    assert "Build the users endpoint" in result.output


def test_dispatch_includes_rules(tmp_path: Path, monkeypatch):
    """Dispatch prompt includes domain rules."""
    calx_dir = _setup_calx(tmp_path)
    write_rule(calx_dir, _make_rule(title="Always validate input"))
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(
        _make_cli(), ["dispatch", "api", "--task", "Build endpoint"]
    )
    assert result.exit_code == 0
    assert "Always validate input" in result.output


def test_dispatch_review_generates_review(tmp_path: Path, monkeypatch):
    """--review generates review dispatch."""
    calx_dir = _setup_calx(tmp_path, domains=["api", "frontend"])
    write_rule(calx_dir, _make_rule(domain="frontend", title="Use design tokens"))
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(
        _make_cli(),
        ["dispatch", "api", "--review", "--task", "POST /users returns 201"],
    )
    assert result.exit_code == 0
    assert "Review Dispatch" in result.output
    assert "POST /users returns 201" in result.output


def test_dispatch_review_no_other_domains(tmp_path: Path, monkeypatch):
    """--review with single domain shows message."""
    _setup_calx(tmp_path, domains=["api"])
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(
        _make_cli(),
        ["dispatch", "api", "--review", "--task", "Some spec"],
    )
    assert result.exit_code == 0
    assert "No other domains configured" in result.output


def test_dispatch_not_a_calx_project(tmp_path: Path, monkeypatch):
    """Exits with error when not a Calx project."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        _make_cli(), ["dispatch", "api", "--task", "Build endpoint"]
    )
    assert result.exit_code != 0
    assert "Not a Calx project" in result.output


def test_dispatch_with_files(tmp_path: Path, monkeypatch):
    """Dispatch with --files includes file list."""
    _setup_calx(tmp_path)
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(
        _make_cli(),
        ["dispatch", "api", "--task", "Build it", "-f", "src/main.py", "-f", "src/models.py"],
    )
    assert result.exit_code == 0
    assert "src/main.py" in result.output
    assert "src/models.py" in result.output
