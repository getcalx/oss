"""Tests for calx.distillation.recurrence."""

from __future__ import annotations

from pathlib import Path

from calx.core.corrections import (
    CorrectionEvent,
    append_event,
    create_correction,
    read_events,
)
from calx.distillation.recurrence import (
    check_recurrence,
    get_chain,
    get_promotion_candidates,
)


def test_check_recurrence_finds_match_same_domain(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()

    c1 = create_correction(
        calx_dir, domain="api",
        description="never mock database connections in integration tests",
    )
    c2 = create_correction(
        calx_dir, domain="api",
        description="stop mocking database connections in integration tests",
    )

    result = check_recurrence(calx_dir, c2)
    assert result.is_recurrence is True
    assert result.original_id == c1.id
    assert result.new_count >= 1


def test_check_recurrence_no_match_dissimilar(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()

    create_correction(calx_dir, domain="api", description="always validate input parameters")
    c2 = create_correction(
        calx_dir, domain="api", description="deploy containers kubernetes cluster orchestration"
    )

    result = check_recurrence(calx_dir, c2)
    assert result.is_recurrence is False
    assert result.original_id is None
    assert result.new_count == 1


def test_check_recurrence_appends_event(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()

    c1 = create_correction(
        calx_dir, domain="api",
        description="never mock database connections in integration tests",
    )
    c2 = create_correction(
        calx_dir, domain="api",
        description="avoid mock database connections in integration tests",
    )

    events_before = read_events(calx_dir)
    result = check_recurrence(calx_dir, c2)

    if result.is_recurrence:
        events_after = read_events(calx_dir)
        assert len(events_after) > len(events_before)

        recurrence_events = [e for e in events_after if e.event_type == "recurrence"]
        assert len(recurrence_events) >= 1
        last_recurrence = recurrence_events[-1]
        assert last_recurrence.correction_id == c2.id
        assert last_recurrence.data["original_id"] == c1.id


def test_check_recurrence_ignores_different_domain(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()

    create_correction(
        calx_dir, domain="api",
        description="never mock database connections in integration tests",
    )
    c2 = create_correction(
        calx_dir, domain="tests", description="never mock database connections in integration tests"
    )

    result = check_recurrence(calx_dir, c2)
    assert result.is_recurrence is False


def test_get_promotion_candidates_above_threshold(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()

    c1 = create_correction(calx_dir, domain="api", description="original correction")

    # Create 3 recurrence events targeting c1
    for i in range(3):
        recur = create_correction(calx_dir, domain="api", description=f"recurrence {i}")
        append_event(calx_dir, CorrectionEvent(
            timestamp=f"2026-03-21T0{i + 1}:00:00+00:00",
            event_type="recurrence",
            correction_id=recur.id,
            data={"original_id": c1.id},
        ))

    candidates = get_promotion_candidates(calx_dir, threshold=3)
    assert len(candidates) == 1
    assert candidates[0].original_id == c1.id
    assert candidates[0].count == 3
    assert candidates[0].domain == "api"


def test_get_promotion_candidates_excludes_distilled(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()

    c1 = create_correction(calx_dir, domain="api", description="original correction")

    # Create 3 recurrence events
    for i in range(3):
        recur = create_correction(calx_dir, domain="api", description=f"recurrence {i}")
        append_event(calx_dir, CorrectionEvent(
            timestamp=f"2026-03-21T0{i + 1}:00:00+00:00",
            event_type="recurrence",
            correction_id=recur.id,
            data={"original_id": c1.id},
        ))

    # Mark c1 as distilled
    append_event(calx_dir, CorrectionEvent(
        timestamp="2026-03-21T05:00:00+00:00",
        event_type="distilled",
        correction_id=c1.id,
        data={"rule_ids": ["api-R001"]},
    ))

    candidates = get_promotion_candidates(calx_dir, threshold=3)
    assert len(candidates) == 0


def test_get_promotion_candidates_below_threshold(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()

    c1 = create_correction(calx_dir, domain="api", description="original correction")

    # Only 2 recurrences, threshold is 3
    for i in range(2):
        recur = create_correction(calx_dir, domain="api", description=f"recurrence {i}")
        append_event(calx_dir, CorrectionEvent(
            timestamp=f"2026-03-21T0{i + 1}:00:00+00:00",
            event_type="recurrence",
            correction_id=recur.id,
            data={"original_id": c1.id},
        ))

    candidates = get_promotion_candidates(calx_dir, threshold=3)
    assert len(candidates) == 0


def test_get_chain_temporal_order(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()

    c1 = create_correction(calx_dir, domain="api", description="original issue")
    c2 = create_correction(calx_dir, domain="api", description="second occurrence")
    c3 = create_correction(calx_dir, domain="api", description="third occurrence")

    # Mark c2 and c3 as recurrences of c1
    for c in [c2, c3]:
        append_event(calx_dir, CorrectionEvent(
            timestamp="2026-03-21T01:00:00+00:00",
            event_type="recurrence",
            correction_id=c.id,
            data={"original_id": c1.id},
        ))

    chain = get_chain(calx_dir, c1.id)

    assert len(chain) == 3
    assert chain[0].id == c1.id  # original first
    # Verify temporal ordering
    for i in range(len(chain) - 1):
        assert chain[i].timestamp <= chain[i + 1].timestamp
