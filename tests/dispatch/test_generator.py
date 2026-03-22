"""Tests for calx.dispatch.generator."""

from pathlib import Path

from calx.core.config import CalxConfig, save_config
from calx.core.rules import Rule, write_rule
from calx.dispatch.generator import generate_dispatch


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


def test_dispatch_includes_domain_in_header(tmp_path: Path):
    calx_dir = _setup_calx(tmp_path)
    result = generate_dispatch(calx_dir, "api", "Build the endpoint")
    assert "# Dispatch: api" in result


def test_rules_section_populated(tmp_path: Path):
    calx_dir = _setup_calx(tmp_path)
    write_rule(calx_dir, _make_rule(title="Always validate input"))
    result = generate_dispatch(calx_dir, "api", "Build the endpoint")
    assert "## Rules" in result
    assert "Always validate input" in result


def test_empty_rules_shows_message(tmp_path: Path):
    calx_dir = _setup_calx(tmp_path)
    result = generate_dispatch(calx_dir, "api", "Build the endpoint")
    assert "No rules defined for this domain yet." in result


def test_task_text_included(tmp_path: Path):
    calx_dir = _setup_calx(tmp_path)
    result = generate_dispatch(calx_dir, "api", "Build the /users endpoint")
    assert "## Task" in result
    assert "Build the /users endpoint" in result


def test_files_listed(tmp_path: Path):
    calx_dir = _setup_calx(tmp_path)
    result = generate_dispatch(
        calx_dir, "api", "Build endpoint", files=["src/api/users.py", "src/api/models.py"]
    )
    assert "## Files" in result
    assert "- src/api/users.py" in result
    assert "- src/api/models.py" in result


def test_default_prohibitions(tmp_path: Path):
    calx_dir = _setup_calx(tmp_path)
    result = generate_dispatch(calx_dir, "api", "Build endpoint")
    assert "## Prohibitions" in result
    assert "- Do NOT commit" in result
    assert "- Do NOT modify files outside the specified list" in result


def test_custom_prohibitions_override_defaults(tmp_path: Path):
    calx_dir = _setup_calx(tmp_path)
    custom = ["Do NOT deploy", "Do NOT run migrations"]
    result = generate_dispatch(calx_dir, "api", "Build endpoint", prohibitions=custom)
    assert "- Do NOT deploy" in result
    assert "- Do NOT run migrations" in result
    assert "Do NOT commit" not in result


def test_agent_naming_self(tmp_path: Path):
    calx_dir = _setup_calx(tmp_path, agent_naming="self")
    result = generate_dispatch(calx_dir, "api", "Build endpoint")
    assert "## Agent Naming" in result
    assert "Name yourself" in result


def test_agent_naming_none_omits_section(tmp_path: Path):
    calx_dir = _setup_calx(tmp_path, agent_naming="none")
    result = generate_dispatch(calx_dir, "api", "Build endpoint")
    assert "## Agent Naming" not in result


def test_agent_naming_developer(tmp_path: Path):
    calx_dir = _setup_calx(tmp_path, agent_naming="developer")
    result = generate_dispatch(calx_dir, "api", "Build endpoint")
    assert "## Agent Naming" in result
    assert "developer will name you" in result


def test_only_active_rules_injected(tmp_path: Path):
    calx_dir = _setup_calx(tmp_path)
    write_rule(calx_dir, _make_rule(num=1, title="Active rule", status="active"))
    write_rule(calx_dir, _make_rule(num=2, title="Retired rule", status="retired"))
    result = generate_dispatch(calx_dir, "api", "Build endpoint")
    assert "Active rule" in result
    assert "Retired rule" not in result
