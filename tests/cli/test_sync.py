"""Tests for calx sync command."""


from click.testing import CliRunner

from calx.cli.main import cli
from calx.core.config import CalxConfig, save_config
from calx.core.rules import Rule, write_rule


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


def _init_calx(tmp_path, domain_paths):
    """Set up a .calx/ directory with config and rules."""
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()
    (calx_dir / "rules").mkdir()
    config = CalxConfig(
        domains=list(domain_paths.keys()),
        domain_paths=domain_paths,
    )
    save_config(calx_dir, config)
    return calx_dir


def test_sync_all_domains(tmp_path, monkeypatch):
    """calx sync writes AGENTS.md for all configured domains."""
    monkeypatch.chdir(tmp_path)
    calx_dir = _init_calx(tmp_path, {"api": "src/api", "tests": "tests"})
    (tmp_path / "src" / "api").mkdir(parents=True)
    (tmp_path / "tests").mkdir()

    write_rule(calx_dir, _make_rule(domain="api"))
    write_rule(calx_dir, _make_rule(domain="tests"))

    runner = CliRunner()
    result = runner.invoke(cli, ["sync"])
    assert result.exit_code == 0, result.output

    assert (tmp_path / "src" / "api" / "AGENTS.md").exists()
    assert (tmp_path / "tests" / "AGENTS.md").exists()
    assert "Synced 2 AGENTS.md" in result.output


def test_sync_single_domain(tmp_path, monkeypatch):
    """calx sync api writes only the api AGENTS.md."""
    monkeypatch.chdir(tmp_path)
    calx_dir = _init_calx(tmp_path, {"api": "src/api", "tests": "tests"})
    (tmp_path / "src" / "api").mkdir(parents=True)
    (tmp_path / "tests").mkdir()

    write_rule(calx_dir, _make_rule(domain="api"))
    write_rule(calx_dir, _make_rule(domain="tests"))

    runner = CliRunner()
    result = runner.invoke(cli, ["sync", "api"])
    assert result.exit_code == 0, result.output

    assert (tmp_path / "src" / "api" / "AGENTS.md").exists()
    assert not (tmp_path / "tests" / "AGENTS.md").exists()
    assert "Synced 1 AGENTS.md" in result.output


def test_sync_no_calx_dir(tmp_path, monkeypatch):
    """calx sync without .calx/ gives a graceful error."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["sync"])
    assert result.exit_code != 0
    assert "No .calx/ directory found" in result.output


def test_sync_no_domain_paths(tmp_path, monkeypatch):
    """calx sync with empty domain_paths reports nothing to sync."""
    monkeypatch.chdir(tmp_path)
    _init_calx(tmp_path, {})

    runner = CliRunner()
    result = runner.invoke(cli, ["sync"])
    assert result.exit_code == 0, result.output
    assert "Nothing to sync" in result.output
