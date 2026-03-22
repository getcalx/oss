"""Near-duplicate rule detection for Calx."""

from __future__ import annotations

from dataclasses import dataclass

from calx.core.rules import Rule


@dataclass
class DuplicatePair:
    rule_a: str
    rule_b: str
    similarity: float


def find_duplicates(rules: list[Rule], threshold: float = 0.5) -> list[DuplicatePair]:
    """Find near-duplicate rules by Jaccard similarity on keywords."""
    from calx.distillation.similarity import _extract_keywords

    rule_kws = [(r, _extract_keywords(f"{r.title} {r.body}")) for r in rules]
    pairs: list[DuplicatePair] = []

    for i, (ra, kwa) in enumerate(rule_kws):
        for j, (rb, kwb) in enumerate(rule_kws):
            if j <= i:
                continue
            if not kwa or not kwb:
                continue
            sim = len(kwa & kwb) / len(kwa | kwb)
            if sim >= threshold:
                pairs.append(DuplicatePair(rule_a=ra.id, rule_b=rb.id, similarity=round(sim, 3)))

    return pairs
