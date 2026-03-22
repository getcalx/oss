"""Tier 2 promotion: binary approve/reject at recurrence threshold."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from calx.core.corrections import CorrectionEvent, CorrectionState, append_event, materialize
from calx.core.events import Event, log_event
from calx.core.rules import Rule, write_rule, next_rule_id
from calx.distillation.recurrence import RecurrenceChain, get_promotion_candidates


@dataclass
class PromotionCandidate:
    chain: RecurrenceChain
    prompt: str


def get_pending_promotions(
    calx_dir: Path, threshold: int = 3, max_per_session: int = 3
) -> list[PromotionCandidate]:
    """Get promotion candidates, capped at max_per_session."""
    chains = get_promotion_candidates(calx_dir, threshold)
    candidates: list[PromotionCandidate] = []
    for chain in chains[:max_per_session]:
        prompt = format_promotion_prompt(chain)
        candidates.append(PromotionCandidate(chain=chain, prompt=prompt))
    return candidates


def format_promotion_prompt(chain: RecurrenceChain) -> str:
    """Format the temporal chain prompt showing the developer's own escalating language."""
    lines = ["This keeps coming up:", ""]
    for corr in chain.corrections:
        ts = corr.timestamp[:10]  # date portion
        lines.append(f'  {corr.id} ({ts}): "{corr.description}"')
    lines.append("")
    lines.append("Lock as a rule? [y/n]")
    return "\n".join(lines)


def promote(calx_dir: Path, chain: RecurrenceChain) -> Rule:
    """Promote a recurrence chain to a rule.

    1. Auto-generate rule title from most recent correction description
    2. Write to .calx/rules/{domain}.md
    3. Append 'promoted' event to each correction in chain
    4. Log promotion event
    """
    # Most recent correction has the clearest description (refined through repetition)
    if not chain.corrections:
        raise ValueError(f"Cannot promote chain {chain.original_id}: no corrections")
    latest = chain.corrections[-1]
    title = latest.description[:80]  # Truncate if very long

    rule_id = next_rule_id(calx_dir, chain.domain)
    source_ids = [c.id for c in chain.corrections]

    rule = Rule(
        id=rule_id,
        domain=chain.domain,
        type="process",  # Default — can be reclassified later
        source_corrections=source_ids,
        added=date.today().isoformat(),
        status="active",
        title=title,
        body=latest.description,
    )

    # Check for conflicts before writing
    try:
        from calx.core.rules import read_rules
        from calx.health.conflicts import detect_conflicts

        existing = read_rules(calx_dir, chain.domain)
        conflicts = detect_conflicts(existing + [rule])
        # If conflicts exist, still write but add a note
        if conflicts:
            rule.body += (
                "\n\nNote: This rule may conflict with existing rules."
                " Run `calx health conflicts` to review."
            )
    except ImportError:
        pass

    write_rule(calx_dir, rule)

    # Append promoted event for the original correction
    ts = datetime.now(timezone.utc).isoformat()
    append_event(
        calx_dir,
        CorrectionEvent(
            timestamp=ts,
            event_type="promoted",
            correction_id=chain.original_id,
            data={"rule_id": rule_id},
        ),
    )

    # Also mark as distilled
    append_event(
        calx_dir,
        CorrectionEvent(
            timestamp=ts,
            event_type="distilled",
            correction_id=chain.original_id,
            data={"rule_ids": [rule_id]},
        ),
    )

    # Log event
    log_event(
        calx_dir,
        Event(
            timestamp=ts,
            event="rule_created",
            data={"rule_id": rule_id, "domain": chain.domain, "source": "promotion"},
        ),
    )

    return rule


def reject_promotion(calx_dir: Path, correction_id: str) -> None:
    """Reject a promotion — append rejected event, resets recurrence count eligibility."""
    ts = datetime.now(timezone.utc).isoformat()
    append_event(
        calx_dir,
        CorrectionEvent(
            timestamp=ts,
            event_type="rejected",
            correction_id=correction_id,
            data={"reason": "Developer rejected promotion"},
        ),
    )
