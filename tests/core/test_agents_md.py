"""Tests for calx.core.agents_md."""

from pathlib import Path

from calx.core.agents_md import generate_agents_md, get_agents_md_path, sync_agents_md
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


def _setup_calx(tmp_path: Path, domain_paths: dict[str, str] | None = None) -> Path:
    """Create a minimal .calx/ directory with config."""
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()
    (calx_dir / "rules").mkdir()
    config = CalxConfig(
        domains=list((domain_paths or {}).keys()),
        domain_paths=domain_paths or {},
    )
    save_config(calx_dir, config)
    return calx_dir


def test_generate_agents_md_with_rules(tmp_path: Path):
    """Generate AGENTS.md content from existing rules."""
    calx_dir = _setup_calx(tmp_path, {"api": "src/api"})
    write_rule(calx_dir, _make_rule(domain="api", num=1, title="First rule"))
    write_rule(calx_dir, _make_rule(domain="api", num=2, title="Second rule"))

    content = generate_agents_md(calx_dir, "api")

    assert "# AGENTS.md — Api Conventions" in content
    assert "Managed by Calx" in content
    assert "do not edit directly" in content.lower()
    assert "`.calx/rules/api.md`" in content
    assert "`calx sync`" in content
    assert "api-R001" in content
    assert "api-R002" in content
    assert "First rule" in content
    assert "Second rule" in content
    assert "Rule IDs: api-R001 through api-R002" in content
    assert "Last synced:" in content


def test_generate_agents_md_no_rules(tmp_path: Path):
    """Empty domain returns minimal header with no-rules message."""
    calx_dir = _setup_calx(tmp_path, {"api": "src/api"})

    content = generate_agents_md(calx_dir, "api")

    assert "# AGENTS.md — Api Conventions" in content
    assert "Managed by Calx" in content
    assert "No rules defined yet" in content
    assert "Rule IDs:" not in content


def test_sync_agents_md_writes_files(tmp_path: Path):
    """Sync writes AGENTS.md files to configured domain paths."""
    calx_dir = _setup_calx(tmp_path, {"api": "src/api", "tests": "tests"})
    write_rule(calx_dir, _make_rule(domain="api"))
    write_rule(calx_dir, _make_rule(domain="tests"))

    written = sync_agents_md(calx_dir)

    assert len(written) == 2
    assert (tmp_path / "src" / "api" / "AGENTS.md").exists()
    assert (tmp_path / "tests" / "AGENTS.md").exists()

    api_content = (tmp_path / "src" / "api" / "AGENTS.md").read_text()
    assert "Api Conventions" in api_content
    assert "api-R001" in api_content


def test_sync_agents_md_single_domain(tmp_path: Path):
    """Sync with a specific domain only writes that domain's file."""
    calx_dir = _setup_calx(tmp_path, {"api": "src/api", "tests": "tests"})
    write_rule(calx_dir, _make_rule(domain="api"))
    write_rule(calx_dir, _make_rule(domain="tests"))

    written = sync_agents_md(calx_dir, domain="api")

    assert len(written) == 1
    assert (tmp_path / "src" / "api" / "AGENTS.md").exists()
    assert not (tmp_path / "tests" / "AGENTS.md").exists()


def test_sync_agents_md_unconfigured_domain(tmp_path: Path):
    """Sync with a domain not in domain_paths returns empty list."""
    calx_dir = _setup_calx(tmp_path, {"api": "src/api"})

    written = sync_agents_md(calx_dir, domain="missing")

    assert written == []


def test_get_agents_md_path(tmp_path: Path):
    """Returns correct path when configured, None when not."""
    calx_dir = _setup_calx(tmp_path, {"api": "src/api"})

    path = get_agents_md_path(calx_dir, "api")
    assert path == tmp_path / "src" / "api" / "AGENTS.md"

    path = get_agents_md_path(calx_dir, "missing")
    assert path is None
