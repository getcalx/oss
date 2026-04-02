"""Health scoring engine for rule lifecycle management.

Computes health scores for rules based on recurrence, conflict,
superseded counts, and age-based staleness decay. Pure functions
for scoring, async functions for DB-backed scoring.
"""
from dataclasses import dataclass
from datetime import datetime, timezone

from calx.serve.db.engine import RuleRow

# Penalty constants
RECURRENCE_PENALTY = 0.3
CONFLICT_PENALTY = 0.2
SUPERSEDED_PENALTY = 0.15
AGE_DECAY_RATE = 0.05

# Thresholds for auto_deactivate (kept for backwards compatibility)
CRITICAL_THRESHOLD = 0.3
WARNING_THRESHOLD = 0.5


@dataclass
class HealthResult:
    rule_id: str
    old_score: float
    new_score: float
    old_status: str
    new_status: str
    decay_factors: list[str]


def compute_health_score(
    learning_mode: str,
    recurrence_count: int,
    conflict_count: int,
    superseded_count: int,
    age_days: int,
    staleness_period_days: int = 30,
    days_since_reinforcement: int | None = None,
) -> tuple[float, list[str]]:
    """Compute a health score for a rule. Pure function, no DB access.

    Starts at 1.0 and applies penalties for recurrence, conflict,
    superseded counts, and (for process rules) age-based staleness.

    Returns (score clamped to [0.0, 1.0], list of decay factor names).
    """
    score = 1.0
    factors: list[str] = []

    if recurrence_count > 0:
        score -= recurrence_count * RECURRENCE_PENALTY
        factors.append("recurrence")

    if conflict_count > 0:
        score -= conflict_count * CONFLICT_PENALTY
        factors.append("conflict")

    if superseded_count > 0:
        score -= superseded_count * SUPERSEDED_PENALTY
        factors.append("superseded")

    if learning_mode == "process":
        apply_age_decay = True
        if days_since_reinforcement is not None and days_since_reinforcement < staleness_period_days:
            apply_age_decay = False

        if apply_age_decay and staleness_period_days > 0:
            periods = age_days // staleness_period_days
            if periods > 0:
                score -= periods * AGE_DECAY_RATE
                factors.append("age")

    score = max(0.0, min(1.0, score))
    score = round(score, 10)

    return score, factors


def health_status_from_score(score: float) -> str:
    """Map a health score to a status label."""
    if score >= 0.7:
        return "healthy"
    elif score >= 0.4:
        return "warning"
    else:
        return "critical"


async def score_rule(
    db: object,
    rule: RuleRow,
    now: datetime | None = None,
) -> HealthResult:
    """Score a single rule by querying DB for decay signals."""
    if now is None:
        now = datetime.now(timezone.utc)

    rule_created = datetime.fromisoformat(rule.created_at.replace("Z", "+00:00"))
    age_days = (now - rule_created).days

    corrections = await db.find_corrections(domain=rule.domain)  # type: ignore[attr-defined]
    recurrence_count = 0
    for c in corrections:
        c_created = datetime.fromisoformat(c.created_at.replace("Z", "+00:00"))
        if c_created > rule_created:
            recurrence_count += 1

    rules = await db.find_rules(domain=rule.domain, active_only=True)  # type: ignore[attr-defined]
    from calx.serve.engine.conflict_detection import detect_conflicts
    other_texts = [r.rule_text for r in rules if r.id != rule.id]
    conflict_count = len(detect_conflicts(rule.rule_text, other_texts))

    all_rules = await db.find_rules(domain=rule.domain, active_only=False)  # type: ignore[attr-defined]
    superseded_count = sum(1 for r in all_rules if not r.active and r.id != rule.id)

    old_score = rule.health_score
    old_status = getattr(rule, "health_status", "healthy")

    new_score, decay_factors = compute_health_score(
        learning_mode=getattr(rule, "learning_mode", "unknown"),
        recurrence_count=recurrence_count,
        conflict_count=conflict_count,
        superseded_count=superseded_count,
        age_days=age_days,
    )
    new_status = health_status_from_score(new_score)

    return HealthResult(
        rule_id=rule.id,
        old_score=old_score,
        new_score=new_score,
        old_status=old_status,
        new_status=new_status,
        decay_factors=decay_factors,
    )


async def score_all_rules(
    db: object,
    now: datetime | None = None,
) -> list[HealthResult]:
    """Score all active rules and persist results to DB."""
    if now is None:
        now = datetime.now(timezone.utc)

    rules = await db.find_rules(active_only=True)  # type: ignore[attr-defined]
    results: list[HealthResult] = []

    for rule in rules:
        result = await score_rule(db, rule, now=now)
        results.append(result)

        await db.update_rule(  # type: ignore[attr-defined]
            result.rule_id,
            health_score=result.new_score,
            health_status=result.new_status,
            last_validated_at=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        )

    return results


async def auto_deactivate_unhealthy_rules(db: object) -> list[dict]:
    """Deactivate rules at critical health. Returns list of actions taken."""
    all_rules = await db.find_rules(active_only=True)  # type: ignore[attr-defined]
    deactivated: list[dict] = []
    warnings: list[dict] = []

    for rule in all_rules:
        if rule.health_score < CRITICAL_THRESHOLD:
            await db.update_rule(rule.id, active=0)  # type: ignore[attr-defined]
            deactivated.append({
                "rule_id": rule.id,
                "health_score": rule.health_score,
                "action": "deactivated",
            })
        elif rule.health_score < WARNING_THRESHOLD:
            warnings.append({
                "rule_id": rule.id,
                "health_score": rule.health_score,
                "action": "warning",
            })

    return deactivated + warnings
