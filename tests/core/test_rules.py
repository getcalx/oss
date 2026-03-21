"""Tests for calx.core.rules."""

from pathlib import Path

from calx.core.rules import (
    Rule,
    format_rule_block,
    next_rule_id,
    read_all_rules,
    read_rules,
    update_rule_status,
    write_rule,
)


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


def test_write_and_read(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()

    rule = _make_rule()
    write_rule(calx_dir, rule)

    rules = read_rules(calx_dir, "api")
    assert len(rules) == 1
    assert rules[0].id == "api-R001"
    assert rules[0].title == "Test rule"
    assert rules[0].type == "process"
    assert rules[0].source_corrections == ["C001"]
    assert rules[0].body == "This is a test rule."


def test_write_multiple_rules(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()

    write_rule(calx_dir, _make_rule(num=1, title="First"))
    write_rule(calx_dir, _make_rule(num=2, title="Second"))

    rules = read_rules(calx_dir, "api")
    assert len(rules) == 2
    assert rules[0].title == "First"
    assert rules[1].title == "Second"


def test_read_all_rules(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()

    write_rule(calx_dir, _make_rule(domain="api"))
    write_rule(calx_dir, _make_rule(domain="tests"))

    all_rules = read_all_rules(calx_dir)
    assert len(all_rules) == 2
    domains = {r.domain for r in all_rules}
    assert domains == {"api", "tests"}


def test_read_nonexistent_domain(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()
    assert read_rules(calx_dir, "missing") == []


def test_format_rule_block():
    rule = _make_rule(title="Don't mock the db", type="architectural")
    block = format_rule_block(rule)
    assert "### api-R001: Don't mock the db" in block
    assert "Type: architectural" in block
    assert "Source: C001" in block


def test_next_rule_id_empty(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()
    assert next_rule_id(calx_dir, "api") == "api-R001"


def test_next_rule_id_existing(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()
    write_rule(calx_dir, _make_rule(num=1))
    write_rule(calx_dir, _make_rule(num=2))
    assert next_rule_id(calx_dir, "api") == "api-R003"


def test_update_rule_status(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()
    write_rule(calx_dir, _make_rule())

    update_rule_status(calx_dir, "api-R001", "retired")

    rules = read_rules(calx_dir, "api")
    assert rules[0].status == "retired"


def test_architectural_type_preserved(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()
    write_rule(calx_dir, _make_rule(type="architectural"))

    rules = read_rules(calx_dir, "api")
    assert rules[0].type == "architectural"


def test_multiple_source_corrections(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()
    rule = _make_rule(source_corrections=["C001", "C003", "C007"])
    write_rule(calx_dir, rule)

    rules = read_rules(calx_dir, "api")
    assert rules[0].source_corrections == ["C001", "C003", "C007"]
