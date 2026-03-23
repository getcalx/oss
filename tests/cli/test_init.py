"""Tests for calx init command."""

import json

from click.testing import CliRunner

from calx.cli.main import cli


def test_init_non_interactive(tmp_path, monkeypatch):
    """calx init --non-interactive creates .calx/ with defaults."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["init", "--non-interactive"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / ".calx" / "calx.json").exists()


def test_init_config_has_domains(tmp_path, monkeypatch):
    """Config file written with detected or default domains."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["init", "--non-interactive"])
    assert result.exit_code == 0, result.output

    config = json.loads((tmp_path / ".calx" / "calx.json").read_text())
    assert "domains" in config
    assert isinstance(config["domains"], list)
    assert len(config["domains"]) > 0  # at least "general"


def test_init_seed_rule_created(tmp_path, monkeypatch):
    """Seed rule file is created in .calx/rules/."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["init", "--non-interactive"])
    assert result.exit_code == 0, result.output

    rules_dir = tmp_path / ".calx" / "rules"
    assert rules_dir.exists()
    rule_files = list(rules_dir.glob("*.md"))
    assert len(rule_files) >= 1
    content = rule_files[0].read_text()
    assert "R001" in content
    assert "Never rewrite a file from scratch" in content


def test_init_readme_generated(tmp_path, monkeypatch):
    """README is generated inside .calx/."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["init", "--non-interactive"])
    assert result.exit_code == 0, result.output

    readme = tmp_path / ".calx" / "README"
    assert readme.exists()
    content = readme.read_text()
    assert "Calx" in content
    assert "calx.json" in content


def test_init_hooks_installed(tmp_path, monkeypatch):
    """Hooks are installed during init."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["init", "--non-interactive"])
    assert result.exit_code == 0, result.output

    assert "installed" in result.output
    # .claude/settings.json should be created
    settings_path = tmp_path / ".claude" / "settings.json"
    assert settings_path.exists()
    settings = json.loads(settings_path.read_text())
    assert "hooks" in settings


def test_init_claude_md_scaffold_created(tmp_path, monkeypatch):
    """CLAUDE.md scaffold is created when none exists."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["init", "--non-interactive"])
    assert result.exit_code == 0, result.output

    claude_md = tmp_path / "CLAUDE.md"
    assert claude_md.exists()
    content = claude_md.read_text()
    assert "Calx" in content
    assert "Created CLAUDE.md scaffold" in result.output


def test_init_claude_md_appends_calx_section(tmp_path, monkeypatch):
    """Existing CLAUDE.md gets Calx section appended, not overwritten."""
    monkeypatch.chdir(tmp_path)
    existing_content = "# My Project\n\nDo not touch this.\n"
    (tmp_path / "CLAUDE.md").write_text(existing_content)

    runner = CliRunner()
    result = runner.invoke(cli, ["init", "--non-interactive"])
    assert result.exit_code == 0, result.output

    claude_md = tmp_path / "CLAUDE.md"
    content = claude_md.read_text()
    assert content.startswith("# My Project")
    assert "Do not touch this." in content
    assert "## Calx" in content
    assert "calx correct" in content
    assert "Added Calx section" in result.output
    assert "Created CLAUDE.md scaffold" not in result.output


def test_init_already_initialized(tmp_path, monkeypatch):
    """Already initialized project shows message and exits."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".calx").mkdir()

    runner = CliRunner()
    result = runner.invoke(cli, ["init", "--non-interactive"])
    assert result.exit_code == 0
    assert "already initialized" in result.output


def test_init_with_explicit_domains(tmp_path, monkeypatch):
    """Domains passed via --domains flag are used."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["init", "--non-interactive", "-d", "api", "-d", "web"])
    assert result.exit_code == 0, result.output

    config = json.loads((tmp_path / ".calx" / "calx.json").read_text())
    assert config["domains"] == ["api", "web"]


def test_init_auto_detects_domains(tmp_path, monkeypatch):
    """Domains are auto-detected from directory structure."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "api").mkdir()
    (tmp_path / "tests").mkdir()

    runner = CliRunner()
    result = runner.invoke(cli, ["init", "--non-interactive"])
    assert result.exit_code == 0, result.output

    config = json.loads((tmp_path / ".calx" / "calx.json").read_text())
    assert "api" in config["domains"]
    assert "tests" in config["domains"]


def test_init_directory_structure(tmp_path, monkeypatch):
    """Init creates the expected directory structure."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["init", "--non-interactive"])
    assert result.exit_code == 0, result.output

    assert (tmp_path / ".calx").is_dir()
    assert (tmp_path / ".calx" / "rules").is_dir()
    assert (tmp_path / ".calx" / "health").is_dir()
    assert (tmp_path / ".calx" / "hooks").is_dir()


def test_init_version_option():
    """calx --version outputs the version."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    from calx import __version__
    assert __version__ in result.output
