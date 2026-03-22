"""Tests for calx.dispatch.review."""

from pathlib import Path

from calx.core.config import CalxConfig, save_config
from calx.core.rules import Rule, write_rule
from calx.dispatch.review import (
    ReviewSuggestion,
    generate_review_dispatch,
    suggest_reviewer,
)


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


def test_suggest_reviewer_returns_different_domain(tmp_path: Path):
    calx_dir = _setup_calx(tmp_path, domains=["api", "frontend"])
    suggestion = suggest_reviewer(calx_dir, "api")
    assert suggestion is not None
    assert suggestion.spec_domain == "api"
    assert suggestion.suggested_reviewer_domain == "frontend"


def test_suggest_reviewer_returns_none_single_domain(tmp_path: Path):
    calx_dir = _setup_calx(tmp_path, domains=["api"])
    suggestion = suggest_reviewer(calx_dir, "api")
    assert suggestion is None


def test_suggest_reviewer_picks_domain_with_most_rules(tmp_path: Path):
    calx_dir = _setup_calx(tmp_path, domains=["api", "frontend", "infra"])
    # Give infra the most rules
    write_rule(calx_dir, _make_rule(domain="frontend", num=1))
    write_rule(calx_dir, _make_rule(domain="infra", num=1))
    write_rule(calx_dir, _make_rule(domain="infra", num=2))
    write_rule(calx_dir, _make_rule(domain="infra", num=3))

    suggestion = suggest_reviewer(calx_dir, "api")
    assert suggestion is not None
    assert suggestion.suggested_reviewer_domain == "infra"


def test_generate_review_dispatch_includes_domains_and_spec(tmp_path: Path):
    calx_dir = _setup_calx(tmp_path, domains=["api", "frontend"])
    write_rule(calx_dir, _make_rule(domain="frontend", title="Use design tokens"))

    spec_content = "POST /api/users returns 201 with user object."
    result = generate_review_dispatch(calx_dir, "api", "frontend", spec_content)

    assert "# Review Dispatch: frontend reviewing api" in result
    assert "Use design tokens" in result
    assert spec_content in result


def test_review_instructions_mention_boundary_failures(tmp_path: Path):
    calx_dir = _setup_calx(tmp_path, domains=["api", "frontend"])
    result = generate_review_dispatch(calx_dir, "api", "frontend", "Some spec")
    assert "boundary failures" in result
    assert "PASS or FAIL" in result


def test_review_dispatch_no_reviewer_rules(tmp_path: Path):
    calx_dir = _setup_calx(tmp_path, domains=["api", "frontend"])
    result = generate_review_dispatch(calx_dir, "api", "frontend", "Some spec")
    assert "No rules defined for your domain." in result


def test_review_dispatch_only_active_rules(tmp_path: Path):
    calx_dir = _setup_calx(tmp_path, domains=["api", "frontend"])
    write_rule(calx_dir, _make_rule(domain="frontend", num=1, title="Active", status="active"))
    write_rule(calx_dir, _make_rule(domain="frontend", num=2, title="Retired", status="retired"))

    result = generate_review_dispatch(calx_dir, "api", "frontend", "Some spec")
    assert "Active" in result
    assert "Retired" not in result


def test_suggest_reviewer_reason_content(tmp_path: Path):
    calx_dir = _setup_calx(tmp_path, domains=["api", "frontend"])
    suggestion = suggest_reviewer(calx_dir, "api")
    assert suggestion is not None
    assert "boundary failures" in suggestion.reason
