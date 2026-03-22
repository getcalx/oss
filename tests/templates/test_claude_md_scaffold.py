"""Tests for calx.templates.claude_md_scaffold."""

from calx.templates.claude_md_scaffold import generate_claude_md_scaffold


def test_scaffold_has_project_name_heading():
    result = generate_claude_md_scaffold("my-project", [])
    assert "# my-project" in result


def test_scaffold_lists_domains():
    result = generate_claude_md_scaffold("my-project", ["api", "frontend"])
    assert "- **api**" in result
    assert "- **frontend**" in result


def test_scaffold_no_domain_section_when_empty():
    result = generate_claude_md_scaffold("my-project", [])
    assert "## Domains" not in result


def test_scaffold_contains_calx_reference():
    result = generate_claude_md_scaffold("my-project", [])
    assert "Calx" in result
    assert "calx.sh" in result


def test_scaffold_contains_calx_correct_usage():
    result = generate_claude_md_scaffold("my-project", [])
    assert 'calx correct' in result
