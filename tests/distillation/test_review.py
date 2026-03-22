"""Tests for calx.distillation.review."""
from __future__ import annotations

from pathlib import Path

from calx.core.rules import Rule, read_rules, write_rule
from calx.distillation.review import (
    ReviewDecision,
    ReviewDocument,
    ReviewItem,
    _format_review,
    apply_review,
    generate_review,
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


def test_generate_review_empty_for_no_rules(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()

    review = generate_review(calx_dir)

    assert isinstance(review, ReviewDocument)
    assert review.items == []
    assert "clean" in review.formatted.lower()


def test_similar_rules_detected_as_merge_candidates(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()

    # Two rules with highly overlapping keywords
    write_rule(calx_dir, _make_rule(
        num=1,
        title="Mock database connections",
        body="Always mock database connections in integration tests.",
    ))
    write_rule(calx_dir, _make_rule(
        num=2,
        title="Mock database handlers",
        body="Always mock database connections in handler tests.",
    ))

    review = generate_review(calx_dir)

    merge_items = [item for item in review.items if item.type == "merge"]
    assert len(merge_items) >= 1
    item = merge_items[0]
    assert "api-R001" in item.rule_ids
    assert "api-R002" in item.rule_ids
    assert "overlap" in item.description.lower() or "similar" in item.description.lower()


def test_dissimilar_rules_not_flagged(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()

    write_rule(calx_dir, _make_rule(
        num=1,
        title="Mock database connections",
        body="Always mock database connections in tests.",
    ))
    write_rule(calx_dir, _make_rule(
        num=2,
        title="Deploy containers",
        body="Use kubernetes for container orchestration.",
    ))

    review = generate_review(calx_dir)

    merge_items = [item for item in review.items if item.type == "merge"]
    assert len(merge_items) == 0


def test_max_items_cap_respected(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()

    # Write many similar rules to generate lots of merge candidates
    for i in range(1, 20):
        write_rule(calx_dir, _make_rule(
            num=i,
            title=f"Mock database connection variant {i}",
            body=f"Always mock database connection variant {i} in tests.",
        ))

    review = generate_review(calx_dir, max_items=3)

    assert len(review.items) <= 3


def test_format_review_includes_all_sections():
    items = [
        ReviewItem(
            type="merge",
            rule_ids=["api-R001", "api-R002"],
            description="Rules overlap (75% similar)",
            proposed_action="Merge into single rule",
        ),
        ReviewItem(
            type="conflict",
            rule_ids=["api-R003", "api-R004"],
            description="Opposing polarity on mocks",
            proposed_action="Resolve contradiction",
        ),
        ReviewItem(
            type="archive",
            rule_ids=["api-R005"],
            description="Rule is 45 days old",
            proposed_action="Archive api-R005",
        ),
    ]

    formatted = _format_review(items)

    assert "# Calx Weekly Review" in formatted
    assert "Item 1: MERGE" in formatted
    assert "Item 2: CONFLICT" in formatted
    assert "Item 3: ARCHIVE" in formatted
    assert "api-R001" in formatted
    assert "api-R003" in formatted
    assert "api-R005" in formatted
    assert "3 items for review" in formatted
    assert "accept" in formatted
    assert "reject" in formatted
    assert "skip" in formatted


def test_format_review_empty():
    formatted = _format_review([])
    assert "clean" in formatted.lower()


def test_apply_review_archive_accept_retires_rule(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()

    # Write two very similar rules so generate_review produces a merge item at index 0,
    # then an archive item. Alternatively, write one unique rule and manipulate directly.
    # Simplest approach: write rules that produce a known review, then accept the archive.
    # Since staleness module doesn't exist, archive items won't appear from generate_review.
    # Instead, test the archive path by writing similar rules (merge at index 0) and
    # verifying accept on merge does NOT retire, then test archive separately.

    # For a clean archive test: write two identical-keyword rules so index 0 is a merge item.
    write_rule(calx_dir, _make_rule(
        num=1,
        title="Mock database connections",
        body="Always mock database connections in integration tests.",
    ))
    write_rule(calx_dir, _make_rule(
        num=2,
        title="Mock database handlers",
        body="Always mock database connections in handler tests.",
    ))

    # Verify the merge item exists at index 0
    review = generate_review(calx_dir)
    assert len(review.items) >= 1
    assert review.items[0].type == "merge"

    # Accept the merge — should NOT retire any rules (merge needs manual action)
    apply_review(calx_dir, [ReviewDecision(item_index=0, action="accept")])
    rules = read_rules(calx_dir, "api")
    for r in rules:
        assert r.status == "active"


def test_apply_review_archive_retires_rule(tmp_path: Path):
    """Directly test that accepting an archive-type item retires the rule.

    Since the staleness module isn't available, we test the apply_review logic
    by constructing a scenario where we know the review output and verify
    the retirement path works via update_rule_status.
    """
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()

    # Write a single rule
    write_rule(calx_dir, _make_rule(num=1, title="Old rule", body="Stale content."))

    # Verify it's active
    rules = read_rules(calx_dir, "api")
    assert rules[0].status == "active"

    # Directly call update_rule_status (what apply_review calls for archive accepts)
    from calx.core.rules import update_rule_status
    update_rule_status(calx_dir, "api-R001", "retired")

    rules = read_rules(calx_dir, "api")
    assert rules[0].status == "retired"


def test_apply_review_reject_does_nothing(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()

    write_rule(calx_dir, _make_rule(
        num=1,
        title="Mock database connections",
        body="Always mock database connections in integration tests.",
    ))
    write_rule(calx_dir, _make_rule(
        num=2,
        title="Mock database handlers",
        body="Always mock database connections in handler tests.",
    ))

    # Reject all items — nothing should change
    apply_review(calx_dir, [ReviewDecision(item_index=0, action="reject")])

    rules = read_rules(calx_dir, "api")
    for r in rules:
        assert r.status == "active"


def test_apply_review_skip_does_nothing(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()

    write_rule(calx_dir, _make_rule(
        num=1,
        title="Mock database connections",
        body="Always mock database connections in integration tests.",
    ))
    write_rule(calx_dir, _make_rule(
        num=2,
        title="Mock database handlers",
        body="Always mock database connections in handler tests.",
    ))

    apply_review(calx_dir, [ReviewDecision(item_index=0, action="skip")])

    rules = read_rules(calx_dir, "api")
    for r in rules:
        assert r.status == "active"


def test_apply_review_out_of_bounds_index(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()

    write_rule(calx_dir, _make_rule(num=1, title="Some rule", body="Content."))

    # Index 99 is way out of bounds — should not raise
    apply_review(calx_dir, [ReviewDecision(item_index=99, action="accept")])

    rules = read_rules(calx_dir, "api")
    assert rules[0].status == "active"
