"""Tests for calx.health.staleness."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from calx.core.corrections import CorrectionEvent, append_event
from calx.core.rules import Rule, write_rule
from calx.health.staleness import find_stale_rules


def _make_rule(domain: str = "api", num: int = 1, **kwargs) -> Rule:
    defaults = {
        "id": f"{domain}-R{num:03d}",
        "domain": domain,
        "type": "process",
        "source_corrections": ["C001"],
        "added": "2026-03-21",
        "status": "active",
        "title": "Test rule",
        "body": "This is a test rule.",
    }
    defaults.update(kwargs)
    return Rule(**defaults)


def _setup_calx(tmp_path: Path) -> Path:
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()
    return calx_dir


def test_stale_process_rule_detected(tmp_path: Path):
    """Process rule older than threshold is flagged as stale."""
    calx_dir = _setup_calx(tmp_path)
    old_date = (date.today() - timedelta(days=60)).isoformat()
    write_rule(calx_dir, _make_rule(added=old_date))

    stale = find_stale_rules(calx_dir, days=30)
    assert len(stale) == 1
    assert stale[0].rule_id == "api-R001"
    assert stale[0].days_since >= 60


def test_architectural_rules_exempt(tmp_path: Path):
    """Architectural rules are never flagged as stale."""
    calx_dir = _setup_calx(tmp_path)
    old_date = (date.today() - timedelta(days=90)).isoformat()
    write_rule(calx_dir, _make_rule(type="architectural", added=old_date))

    stale = find_stale_rules(calx_dir, days=30)
    assert stale == []


def test_recent_rules_not_flagged(tmp_path: Path):
    """Rules newer than the threshold are not flagged."""
    calx_dir = _setup_calx(tmp_path)
    recent_date = (date.today() - timedelta(days=5)).isoformat()
    write_rule(calx_dir, _make_rule(added=recent_date))

    stale = find_stale_rules(calx_dir, days=30)
    assert stale == []


def test_non_active_rules_skipped(tmp_path: Path):
    """Rules with status other than active are not flagged."""
    calx_dir = _setup_calx(tmp_path)
    old_date = (date.today() - timedelta(days=60)).isoformat()
    write_rule(calx_dir, _make_rule(added=old_date, status="retired"))

    stale = find_stale_rules(calx_dir, days=30)
    assert stale == []


def test_stale_rule_with_reinforcement(tmp_path: Path):
    """Stale rule shows last_reinforcement when corrections cite it."""
    calx_dir = _setup_calx(tmp_path)
    old_date = (date.today() - timedelta(days=60)).isoformat()
    write_rule(calx_dir, _make_rule(added=old_date))

    # Create a correction and distill it to the rule
    append_event(calx_dir, CorrectionEvent(
        timestamp="2026-03-15T00:00:00+00:00",
        event_type="created",
        correction_id="C001",
        data={"uuid": "u1", "domain": "api", "description": "test"},
    ))
    append_event(calx_dir, CorrectionEvent(
        timestamp="2026-03-15T00:00:00+00:00",
        event_type="distilled",
        correction_id="C001",
        data={"rule_ids": ["api-R001"]},
    ))

    stale = find_stale_rules(calx_dir, days=30)
    assert len(stale) == 1
    assert stale[0].last_reinforcement == "2026-03-15"


def test_empty_calx_dir(tmp_path: Path):
    """Empty calx dir returns no stale rules."""
    calx_dir = _setup_calx(tmp_path)
    stale = find_stale_rules(calx_dir, days=30)
    assert stale == []
