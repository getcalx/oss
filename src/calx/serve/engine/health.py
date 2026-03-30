"""Health-based rule auto-deactivation."""
from __future__ import annotations

CRITICAL_THRESHOLD = 0.3
WARNING_THRESHOLD = 0.5


async def auto_deactivate_unhealthy_rules(db: object) -> list[dict]:
    """Deactivate rules at critical health. Returns list of deactivated rules.

    Rules with health_score < CRITICAL_THRESHOLD are auto-deactivated.
    Rules with health_score < WARNING_THRESHOLD are flagged but kept active.
    """
    all_rules = await db.find_rules(active_only=True)  # type: ignore[attr-defined]
    deactivated: list[dict] = []
    warnings: list[dict] = []

    for rule in all_rules:
        if rule.health_score is None:
            continue

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
