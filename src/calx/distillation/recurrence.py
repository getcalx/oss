"""Tier 1 recurrence detection for Calx."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from calx.core.corrections import (
    CorrectionEvent,
    CorrectionState,
    append_event,
    materialize,
    read_events,
)
from calx.distillation.similarity import find_most_similar


@dataclass
class RecurrenceResult:
    is_recurrence: bool
    original_id: str | None = None
    new_count: int = 0


@dataclass
class RecurrenceChain:
    original_id: str
    domain: str
    count: int
    corrections: list[CorrectionState] = field(default_factory=list)


def check_recurrence(calx_dir: Path, new_correction: CorrectionState) -> RecurrenceResult:
    """Check if a new correction is a recurrence of an existing one.

    1. Find existing corrections in same domain
    2. Run similarity match
    3. If match >= 0.3: append recurrence event, return match info
    4. If no match: return fresh entry
    """
    all_corrections = materialize(calx_dir)
    same_domain = [
        c for c in all_corrections
        if c.domain == new_correction.domain and c.id != new_correction.id
    ]

    matches = find_most_similar(new_correction.description, same_domain)
    if not matches:
        return RecurrenceResult(is_recurrence=False, new_count=1)

    original = matches[0][0]  # best match

    # Append recurrence event
    append_event(calx_dir, CorrectionEvent(
        timestamp=datetime.now(timezone.utc).isoformat(),
        event_type="recurrence",
        correction_id=new_correction.id,
        data={"original_id": original.id},
    ))

    # Count total recurrences targeting the original
    events = read_events(calx_dir)
    count = sum(
        1 for e in events
        if e.event_type == "recurrence" and e.data.get("original_id") == original.id
    )

    return RecurrenceResult(
        is_recurrence=True,
        original_id=original.id,
        new_count=count,
    )


def get_promotion_candidates(calx_dir: Path, threshold: int = 3) -> list[RecurrenceChain]:
    """Return chains where recurrence count >= threshold and original not yet distilled."""
    all_corrections = materialize(calx_dir)

    candidates: list[RecurrenceChain] = []
    seen: set[str] = set()

    for corr in all_corrections:
        if corr.recurrence_count >= threshold and not corr.distilled_to and corr.id not in seen:
            chain = get_chain(calx_dir, corr.id)
            candidates.append(RecurrenceChain(
                original_id=corr.id,
                domain=corr.domain,
                count=corr.recurrence_count,
                corrections=chain,
            ))
            seen.add(corr.id)

    return candidates


def get_chain(calx_dir: Path, correction_id: str) -> list[CorrectionState]:
    """Return the full temporal chain: original + all recurrences, ordered by timestamp."""
    all_corrections = materialize(calx_dir)

    chain = []
    for corr in all_corrections:
        if corr.id == correction_id or corr.recurrence_of == correction_id:
            chain.append(corr)

    chain.sort(key=lambda c: c.timestamp)
    return chain
