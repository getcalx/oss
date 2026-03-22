"""Stale rule detection for Calx."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from calx.core.corrections import materialize
from calx.core.rules import read_all_rules


@dataclass
class StaleRule:
    rule_id: str
    domain: str
    added: str
    days_since: int
    last_reinforcement: str | None


def find_stale_rules(calx_dir: Path, days: int = 30) -> list[StaleRule]:
    """Find process rules older than `days` with no recent correction reinforcement.

    Architectural rules are exempt — they don't decay from dormancy.
    """
    rules = read_all_rules(calx_dir)
    corrections = materialize(calx_dir)
    today = date.today()
    stale: list[StaleRule] = []

    for rule in rules:
        if rule.type != "process" or rule.status != "active":
            continue
        try:
            added_date = date.fromisoformat(rule.added)
        except (ValueError, TypeError):
            continue

        age = (today - added_date).days
        if age < days:
            continue

        # Check for reinforcement: corrections citing this rule after it was created
        last_reinforcement = None
        for corr in corrections:
            if rule.id in corr.distilled_to:
                corr_date = corr.timestamp[:10]  # ISO date portion
                if last_reinforcement is None or corr_date > last_reinforcement:
                    last_reinforcement = corr_date

        stale.append(StaleRule(
            rule_id=rule.id,
            domain=rule.domain,
            added=rule.added,
            days_since=age,
            last_reinforcement=last_reinforcement,
        ))

    return stale
