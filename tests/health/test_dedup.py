"""Tests for calx.health.dedup."""

from __future__ import annotations

from calx.core.rules import Rule
from calx.health.dedup import find_duplicates


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


def test_duplicate_rules_detected():
    """Rules with high keyword overlap are flagged as duplicates."""
    rules = [
        _make_rule("api-R001", title="Always validate input parameters",
                    body="Validate all input parameters before processing."),
        _make_rule("api-R002", title="Validate input parameters always",
                    body="Input parameters must be validated before processing."),
    ]
    pairs = find_duplicates(rules, threshold=0.4)
    assert len(pairs) >= 1
    assert pairs[0].rule_a == "api-R001"
    assert pairs[0].rule_b == "api-R002"
    assert pairs[0].similarity >= 0.4


def test_non_duplicates_ignored():
    """Rules with low keyword overlap are not flagged."""
    rules = [
        _make_rule("api-R001", title="Always validate input parameters",
                    body="Validate all input parameters."),
        _make_rule("api-R002", title="Use dependency injection for services",
                    body="Services should use dependency injection patterns."),
    ]
    pairs = find_duplicates(rules, threshold=0.5)
    assert pairs == []


def test_empty_list_returns_empty():
    """Empty rules list returns empty pairs list."""
    pairs = find_duplicates([], threshold=0.5)
    assert pairs == []


def test_single_rule_no_pairs():
    """A single rule cannot form a duplicate pair."""
    rules = [_make_rule("api-R001", title="Always validate", body="Validate input.")]
    pairs = find_duplicates(rules, threshold=0.5)
    assert pairs == []


def test_threshold_sensitivity():
    """Higher threshold yields fewer matches."""
    rules = [
        _make_rule("api-R001", title="Validate input data carefully",
                    body="Check input data types and ranges."),
        _make_rule("api-R002", title="Check input data types",
                    body="Ensure input data is correctly typed."),
    ]
    low_threshold = find_duplicates(rules, threshold=0.2)
    high_threshold = find_duplicates(rules, threshold=0.9)
    assert len(low_threshold) >= len(high_threshold)
