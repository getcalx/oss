"""Tests for calx.distillation.promotion."""

from __future__ import annotations

from pathlib import Path

from calx.core.corrections import (
    CorrectionEvent,
    append_event,
    create_correction,
)
from calx.core.corrections import (
    read_events as read_correction_events,
)
from calx.core.events import read_events as read_general_events
from calx.core.rules import read_rules
from calx.distillation.promotion import (
    get_pending_promotions,
    promote,
    reject_promotion,
)


def _setup_chain(calx_dir: Path, count: int = 3) -> tuple:
    """Helper: create original correction + `count` recurrences."""
    c1 = create_correction(calx_dir, domain="api", description="original correction")
    recurrences = []
    for i in range(count):
        recur = create_correction(
            calx_dir, domain="api", description=f"recurrence {i} of original"
        )
        append_event(
            calx_dir,
            CorrectionEvent(
                timestamp=f"2026-03-21T0{i + 1}:00:00+00:00",
                event_type="recurrence",
                correction_id=recur.id,
                data={"original_id": c1.id},
            ),
        )
        recurrences.append(recur)
    return c1, recurrences


# --- get_pending_promotions ---


def test_get_pending_promotions_returns_candidates_above_threshold(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()

    _setup_chain(calx_dir, count=3)

    candidates = get_pending_promotions(calx_dir, threshold=3)
    assert len(candidates) == 1
    assert candidates[0].chain.count == 3
    assert candidates[0].prompt  # non-empty prompt string


def test_get_pending_promotions_respects_max_per_session(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()

    # Create 4 separate chains, each with 3 recurrences
    for domain_num in range(4):
        domain = f"domain{domain_num}"
        c = create_correction(calx_dir, domain=domain, description=f"original in {domain}")
        for i in range(3):
            recur = create_correction(
                calx_dir, domain=domain, description=f"recurrence {i} in {domain}"
            )
            append_event(
                calx_dir,
                CorrectionEvent(
                    timestamp=f"2026-03-21T0{i + 1}:00:00+00:00",
                    event_type="recurrence",
                    correction_id=recur.id,
                    data={"original_id": c.id},
                ),
            )

    # Should cap at max_per_session=2
    candidates = get_pending_promotions(calx_dir, threshold=3, max_per_session=2)
    assert len(candidates) == 2


# --- format_promotion_prompt ---


def test_format_promotion_prompt_includes_descriptions_and_yn(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()

    c1, recurrences = _setup_chain(calx_dir, count=3)

    candidates = get_pending_promotions(calx_dir, threshold=3)
    assert len(candidates) == 1

    prompt = candidates[0].prompt
    assert "[y/n]" in prompt
    assert "This keeps coming up:" in prompt
    # Should include correction descriptions
    assert "original correction" in prompt


# --- promote ---


def test_promote_creates_rule_in_rules_file(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()

    c1, _ = _setup_chain(calx_dir, count=3)

    candidates = get_pending_promotions(calx_dir, threshold=3)
    chain = candidates[0].chain

    rule = promote(calx_dir, chain)

    assert rule.id.startswith("api-R")
    assert rule.domain == "api"
    assert rule.status == "active"

    # Verify rule was written to file
    rules = read_rules(calx_dir, "api")
    assert len(rules) == 1
    assert rules[0].id == rule.id


def test_promote_appends_promoted_and_distilled_events(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()

    c1, _ = _setup_chain(calx_dir, count=3)

    candidates = get_pending_promotions(calx_dir, threshold=3)
    chain = candidates[0].chain

    rule = promote(calx_dir, chain)

    events = read_correction_events(calx_dir)

    promoted_events = [
        e for e in events if e.event_type == "promoted" and e.correction_id == c1.id
    ]
    assert len(promoted_events) == 1
    assert promoted_events[0].data["rule_id"] == rule.id

    distilled_events = [
        e for e in events if e.event_type == "distilled" and e.correction_id == c1.id
    ]
    assert len(distilled_events) == 1
    assert rule.id in distilled_events[0].data["rule_ids"]


def test_promote_logs_rule_created_event(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()

    _setup_chain(calx_dir, count=3)

    candidates = get_pending_promotions(calx_dir, threshold=3)
    chain = candidates[0].chain

    rule = promote(calx_dir, chain)

    events = read_general_events(calx_dir, event_type="rule_created")
    assert len(events) == 1
    assert events[0].data["rule_id"] == rule.id
    assert events[0].data["domain"] == "api"
    assert events[0].data["source"] == "promotion"


# --- reject_promotion ---


def test_reject_promotion_appends_rejected_event(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()

    c1, _ = _setup_chain(calx_dir, count=3)

    reject_promotion(calx_dir, c1.id)

    events = read_correction_events(calx_dir)
    rejected_events = [
        e for e in events if e.event_type == "rejected" and e.correction_id == c1.id
    ]
    assert len(rejected_events) == 1
    assert "rejected" in rejected_events[0].data["reason"].lower()


# --- Integration: promoted corrections no longer appear as candidates ---


def test_promoted_corrections_no_longer_appear_as_candidates(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()

    c1, _ = _setup_chain(calx_dir, count=3)

    # Verify candidate exists before promotion
    candidates_before = get_pending_promotions(calx_dir, threshold=3)
    assert len(candidates_before) == 1

    # Promote
    promote(calx_dir, candidates_before[0].chain)

    # Should no longer appear (distilled_to is now populated)
    candidates_after = get_pending_promotions(calx_dir, threshold=3)
    assert len(candidates_after) == 0
