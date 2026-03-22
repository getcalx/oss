"""Tier 3 weekly batch review for Calx."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from calx.core.rules import Rule, read_all_rules, update_rule_status


@dataclass
class ReviewItem:
    type: str  # "merge" | "conflict" | "archive"
    rule_ids: list[str] = field(default_factory=list)
    description: str = ""
    proposed_action: str = ""


@dataclass
class ReviewDocument:
    items: list[ReviewItem] = field(default_factory=list)
    formatted: str = ""


@dataclass
class ReviewDecision:
    item_index: int
    action: str  # "accept" | "reject" | "skip"


def generate_review(calx_dir: Path, max_items: int = 10) -> ReviewDocument:
    """Generate a weekly review document.

    Consolidates:
    1. Overlapping rules (similarity > 0.5) -> merge candidates
    2. Contradictions -> conflict items
    3. Stale rules (inactive 30+ days) -> archive candidates

    Capped at max_items to keep review under 5 minutes.
    """
    rules = read_all_rules(calx_dir)
    items: list[ReviewItem] = []

    # 1. Find merge candidates (similar rules)
    from calx.distillation.similarity import _extract_keywords

    rule_kws = [(r, _extract_keywords(f"{r.title} {r.body}")) for r in rules]
    seen_pairs: set[tuple[str, str]] = set()

    for i, (ra, kwa) in enumerate(rule_kws):
        for j, (rb, kwb) in enumerate(rule_kws):
            if j <= i or not kwa or not kwb:
                continue
            pair = (ra.id, rb.id)
            if pair in seen_pairs:
                continue
            sim = len(kwa & kwb) / len(kwa | kwb)
            if sim > 0.5:
                seen_pairs.add(pair)
                items.append(ReviewItem(
                    type="merge",
                    rule_ids=[ra.id, rb.id],
                    description=f"Rules {ra.id} and {rb.id} overlap ({sim:.0%} similar)",
                    proposed_action=f"Merge into single rule covering both: '{ra.title}' and '{rb.title}'",
                ))

    # 2. Find conflicts
    try:
        from calx.health.conflicts import detect_conflicts

        conflicts = detect_conflicts(rules)
        for conflict in conflicts:
            items.append(ReviewItem(
                type="conflict",
                rule_ids=[conflict.rule_a, conflict.rule_b],
                description=conflict.reason,
                proposed_action="Resolve contradiction — retire or modify one rule",
            ))
    except ImportError:
        pass

    # 3. Find stale rules for archival
    try:
        from calx.health.staleness import find_stale_rules

        stale = find_stale_rules(calx_dir)
        for s in stale:
            items.append(ReviewItem(
                type="archive",
                rule_ids=[s.rule_id],
                description=f"Rule {s.rule_id} is {s.days_since} days old with no reinforcement",
                proposed_action=f"Archive {s.rule_id} — no activity in {s.days_since} days",
            ))
    except ImportError:
        pass

    # Cap at max_items
    items = items[:max_items]

    # Format
    formatted = _format_review(items)
    return ReviewDocument(items=items, formatted=formatted)


def _format_review(items: list[ReviewItem]) -> str:
    """Format review items as a readable document."""
    if not items:
        return "No items to review. Your rule set is clean."

    lines: list[str] = ["# Calx Weekly Review", ""]
    for i, item in enumerate(items):
        lines.append(f"## Item {i + 1}: {item.type.upper()}")
        lines.append(f"Rules: {', '.join(item.rule_ids)}")
        lines.append(f"Issue: {item.description}")
        lines.append(f"Proposed: {item.proposed_action}")
        lines.append(f"Action: [ ] accept  [ ] reject  [ ] skip")
        lines.append("")

    lines.append(f"---")
    lines.append(f"{len(items)} items for review.")
    return "\n".join(lines)


def apply_review(calx_dir: Path, decisions: list[ReviewDecision]) -> None:
    """Apply review decisions.

    - accept on "archive" -> set rule status to "retired"
    - accept on "merge" -> no auto-action (needs manual merge), but flag for follow-up
    - accept on "conflict" -> no auto-action, flag for follow-up
    - reject -> no action
    - skip -> no action
    """
    review = generate_review(calx_dir)

    for decision in decisions:
        if decision.action != "accept":
            continue
        if decision.item_index >= len(review.items):
            continue

        item = review.items[decision.item_index]
        if item.type == "archive":
            for rule_id in item.rule_ids:
                update_rule_status(calx_dir, rule_id, "retired")
