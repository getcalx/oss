"""Process-to-architectural conversion surfacing for Calx."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from calx.core.corrections import materialize
from calx.core.rules import read_all_rules


@dataclass
class ConversionCandidate:
    rule_id: str
    domain: str
    recurrence_count: int
    correction_ids: list[str] = field(default_factory=list)
    message: str = ""


def find_conversion_candidates(calx_dir: Path) -> list[ConversionCandidate]:
    """Find process rules with repeated violations — candidates for architectural conversion."""
    rules = read_all_rules(calx_dir)
    corrections = materialize(calx_dir)
    candidates: list[ConversionCandidate] = []

    for rule in rules:
        if rule.type != "process" or rule.status != "active":
            continue
        # Find corrections in same domain after rule was created
        post_violations = [
            c for c in corrections
            if c.domain == rule.domain and c.timestamp[:10] >= rule.added
            and c.recurrence_of is not None
        ]
        if len(post_violations) >= 2:
            ids = [c.id for c in post_violations]
            msg = (
                f"This process rule ({rule.id}) has been violated {len(post_violations)} times "
                f"(corrections {', '.join(ids)}). Process rules have ~50% persistence. "
                f"Consider converting to an architectural fix: a linter rule, pre-commit hook, "
                f"type constraint, or structural change that makes this error class impossible."
            )
            candidates.append(ConversionCandidate(
                rule_id=rule.id, domain=rule.domain,
                recurrence_count=len(post_violations),
                correction_ids=ids, message=msg,
            ))
    return candidates
