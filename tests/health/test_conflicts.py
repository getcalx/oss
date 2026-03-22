"""Tests for calx.health.conflicts."""

from __future__ import annotations

from calx.core.rules import Rule
from calx.health.conflicts import Conflict, _extract_polarity, detect_conflicts


def _make_rule(rule_id: str = "api-R001", title: str = "Test rule", body: str = "") -> Rule:
    return Rule(
        id=rule_id,
        domain=rule_id.rsplit("-R", 1)[0],
        type="process",
        source_corrections=["C001"],
        added="2026-03-21",
        status="active",
        title=title,
        body=body,
    )


# --- _extract_polarity ---


def test_extract_polarity_always():
    result = _extract_polarity("always use mocks in tests")
    assert len(result) >= 1
    subjects = [s for s, p in result]
    polarities = [p for s, p in result]
    assert "always" in polarities
    assert any("mocks" in s for s in subjects)


def test_extract_polarity_never():
    result = _extract_polarity("never use mocks in tests")
    assert len(result) >= 1
    polarities = [p for s, p in result]
    assert "never" in polarities


def test_extract_polarity_use_and_avoid():
    result_use = _extract_polarity("use dependency injection")
    result_avoid = _extract_polarity("avoid dependency injection")
    assert any(p == "use" for _, p in result_use)
    assert any(p == "avoid" for _, p in result_avoid)


def test_extract_polarity_no_match():
    result = _extract_polarity("the sky is blue")
    assert result == []


def test_extract_polarity_must_not():
    result = _extract_polarity("must not call external APIs")
    polarities = [p for _, p in result]
    assert "must not" in polarities


# --- detect_conflicts ---


def test_detect_always_vs_never():
    rules = [
        _make_rule("api-R001", title="Always use mocks", body="Always use mocks in unit tests."),
        _make_rule("api-R002", title="Never use mocks", body="Never use mocks in unit tests."),
    ]
    conflicts = detect_conflicts(rules)
    assert len(conflicts) >= 1
    c = conflicts[0]
    assert c.rule_a == "api-R001"
    assert c.rule_b == "api-R002"
    assert "always" in c.reason or "never" in c.reason


def test_detect_use_vs_avoid():
    rules = [
        _make_rule("api-R001", title="Use retries", body="Use retries for network calls."),
        _make_rule("api-R002", title="Avoid retries", body="Avoid retries for network calls."),
    ]
    conflicts = detect_conflicts(rules)
    assert len(conflicts) >= 1
    c = conflicts[0]
    assert {c.rule_a, c.rule_b} == {"api-R001", "api-R002"}


def test_no_false_positives_non_conflicting():
    rules = [
        _make_rule("api-R001", title="Always log errors", body="Always log errors to stderr."),
        _make_rule("api-R002", title="Always validate input", body="Always validate input params."),
    ]
    conflicts = detect_conflicts(rules)
    assert conflicts == []


def test_empty_rules_no_conflicts():
    conflicts = detect_conflicts([])
    assert conflicts == []


def test_different_subjects_no_conflict():
    rules = [
        _make_rule("api-R001", title="Always use mocks", body="Always use mocks for testing."),
        _make_rule(
            "api-R002",
            title="Never skip validation",
            body="Never skip validation on input.",
        ),
    ]
    conflicts = detect_conflicts(rules)
    assert conflicts == []


def test_single_rule_no_conflict():
    rules = [
        _make_rule("api-R001", title="Always use mocks", body="Always use mocks in tests."),
    ]
    conflicts = detect_conflicts([rules[0]])
    assert conflicts == []
