"""Correction-to-rule coverage analysis for Calx."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from calx.core.corrections import materialize
from calx.core.rules import read_all_rules


@dataclass
class CoverageReport:
    total_corrections: int
    distilled: int
    pending: int
    gaps: list[str] = field(default_factory=list)


def check_coverage(calx_dir: Path) -> CoverageReport:
    """Check bidirectional correction-to-rule traceability.

    Checks:
    1. Corrections without distilled_to (pending distillation)
    2. Rules without source_corrections (orphan rules -- source is "seed" doesn't count)
    3. Corrections citing rule IDs that don't exist
    4. Rules citing correction IDs that don't exist
    """
    corrections = materialize(calx_dir)
    rules = read_all_rules(calx_dir)

    # Build lookup sets
    correction_ids = {c.id for c in corrections}
    rule_ids = {r.id for r in rules}

    gaps: list[str] = []

    # 1. Corrections without distilled_to
    pending = [c for c in corrections if c.status == "confirmed" and not c.distilled_to]
    distilled = [c for c in corrections if c.distilled_to]

    # 2. Orphan rules (no source corrections, excluding "seed" source)
    for rule in rules:
        real_sources = [s for s in rule.source_corrections if s != "seed"]
        if not real_sources:
            if "seed" not in rule.source_corrections:
                gaps.append(f"Rule {rule.id} has no source corrections")
            continue  # seed rules are expected to have no correction source

    # 3. Rules citing correction IDs that don't exist
    for rule in rules:
        real_sources = [s for s in rule.source_corrections if s != "seed"]
        for source_id in real_sources:
            if source_id not in correction_ids:
                gaps.append(f"Rule {rule.id} cites correction {source_id} which does not exist")

    # 4. Corrections citing rule IDs that don't exist
    for corr in corrections:
        for rule_id in corr.distilled_to:
            if rule_id not in rule_ids:
                gaps.append(f"Correction {corr.id} distilled to rule {rule_id} which does not exist")

    return CoverageReport(
        total_corrections=len(corrections),
        distilled=len(distilled),
        pending=len(pending),
        gaps=gaps,
    )
