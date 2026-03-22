"""Rule health scoring for Calx."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from calx.core.corrections import materialize
from calx.core.rules import Rule, read_all_rules, read_rules


@dataclass
class RuleScore:
    rule_id: str
    domain: str
    type: str
    score: float
    level: str  # "healthy" | "warning" | "critical"
    factors: list[str] = field(default_factory=list)


def score_rules(calx_dir: Path, domain: str | None = None) -> list[RuleScore]:
    """Score all rules (or rules in a domain). Returns RuleScore list."""
    rules = read_rules(calx_dir, domain) if domain else read_all_rules(calx_dir)

    corrections = materialize(calx_dir)
    from calx.health.conflicts import detect_conflicts
    conflicts = detect_conflicts(rules)
    conflict_ids: set[str] = set()
    for c in conflicts:
        conflict_ids.add(c.rule_a)
        conflict_ids.add(c.rule_b)

    results: list[RuleScore] = []
    for rule in rules:
        score, factors = _score_rule(rule, corrections, conflict_ids)
        level = "healthy" if score >= 0.7 else "warning" if score >= 0.4 else "critical"
        results.append(RuleScore(
            rule_id=rule.id, domain=rule.domain, type=rule.type,
            score=round(score, 2), level=level, factors=factors,
        ))
    return results


def _score_rule(rule: Rule, corrections: list, conflict_ids: set[str]) -> tuple[float, list[str]]:
    """Score a single rule. Start at 1.0, apply decay factors."""
    score = 1.0
    factors: list[str] = []

    # Recurrence penalty: corrections in same domain after rule was created
    post_rule_recurrences = sum(
        1 for c in corrections
        if c.domain == rule.domain and c.recurrence_of and c.timestamp[:10] >= rule.added
    )
    if post_rule_recurrences > 0:
        penalty = post_rule_recurrences * 0.3
        score -= penalty
        factors.append(f"-{penalty:.1f} from {post_rule_recurrences} recurrence(s)")

    # Conflict penalty
    if rule.id in conflict_ids:
        score -= 0.2
        factors.append("-0.2 from conflict")

    # Age decay (process rules only)
    if rule.type == "process":
        try:
            added = date.fromisoformat(rule.added)
            age_periods = (date.today() - added).days // 30
            if age_periods > 0:
                decay = age_periods * 0.05
                score -= decay
                factors.append(f"-{decay:.2f} from {age_periods} staleness period(s)")
        except (ValueError, TypeError):
            pass

    return max(score, 0.0), factors
