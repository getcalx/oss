"""Tests for calx.health.scoring."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from calx.core.corrections import CorrectionEvent, append_event
from calx.core.rules import Rule, write_rule
from calx.health.scoring import score_rules


def _make_rule(domain: str = "api", num: int = 1, **kwargs) -> Rule:
    defaults = {
        "id": f"{domain}-R{num:03d}",
        "domain": domain,
        "type": "process",
        "source_corrections": ["C001"],
        "added": date.today().isoformat(),
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


def test_clean_rule_scores_healthy(tmp_path: Path):
    """A rule with no penalties scores 1.0 (healthy)."""
    calx_dir = _setup_calx(tmp_path)
    write_rule(calx_dir, _make_rule())

    scores = score_rules(calx_dir)
    assert len(scores) == 1
    assert scores[0].score == 1.0
    assert scores[0].level == "healthy"


def test_recurrence_penalty_applied(tmp_path: Path):
    """Recurrence corrections in same domain after rule creation penalize score."""
    calx_dir = _setup_calx(tmp_path)
    today = date.today().isoformat()
    write_rule(calx_dir, _make_rule(added=today))

    # Create a correction that is a recurrence
    ts = f"{today}T00:00:00+00:00"
    append_event(calx_dir, CorrectionEvent(
        timestamp=ts, event_type="created", correction_id="C001",
        data={"uuid": "u1", "domain": "api", "description": "test"},
    ))
    append_event(calx_dir, CorrectionEvent(
        timestamp=ts, event_type="recurrence", correction_id="C001",
        data={"original_id": "C000"},
    ))

    scores = score_rules(calx_dir)
    assert len(scores) == 1
    assert scores[0].score < 1.0
    assert any("recurrence" in f for f in scores[0].factors)


def test_conflict_penalty_applied(tmp_path: Path):
    """Rules in conflict receive a -0.2 penalty."""
    calx_dir = _setup_calx(tmp_path)
    write_rule(calx_dir, _make_rule(
        num=1, title="Always use mocks", body="Always use mocks in unit tests.",
    ))
    write_rule(calx_dir, _make_rule(
        num=2, title="Never use mocks", body="Never use mocks in unit tests.",
    ))

    scores = score_rules(calx_dir)
    assert len(scores) == 2
    for s in scores:
        assert s.score <= 0.8
        assert any("conflict" in f for f in s.factors)


def test_process_rule_age_decay(tmp_path: Path):
    """Process rules lose score from age decay."""
    calx_dir = _setup_calx(tmp_path)
    old_date = (date.today() - timedelta(days=90)).isoformat()
    write_rule(calx_dir, _make_rule(added=old_date))

    scores = score_rules(calx_dir)
    assert len(scores) == 1
    assert scores[0].score < 1.0
    assert any("staleness" in f for f in scores[0].factors)


def test_architectural_rules_no_age_decay(tmp_path: Path):
    """Architectural rules don't get age decay."""
    calx_dir = _setup_calx(tmp_path)
    old_date = (date.today() - timedelta(days=90)).isoformat()
    write_rule(calx_dir, _make_rule(type="architectural", added=old_date))

    scores = score_rules(calx_dir)
    assert len(scores) == 1
    assert scores[0].score == 1.0
    assert not any("staleness" in f for f in scores[0].factors)


def test_score_never_below_zero(tmp_path: Path):
    """Score is floored at 0.0 even with massive penalties."""
    calx_dir = _setup_calx(tmp_path)
    very_old = (date.today() - timedelta(days=3650)).isoformat()
    write_rule(calx_dir, _make_rule(added=very_old))

    # Create many recurrence corrections
    for i in range(10):
        cid = f"C{i:03d}"
        ts = f"{date.today().isoformat()}T00:00:00+00:00"
        append_event(calx_dir, CorrectionEvent(
            timestamp=ts, event_type="created", correction_id=cid,
            data={"uuid": f"u{i}", "domain": "api", "description": "test"},
        ))
        append_event(calx_dir, CorrectionEvent(
            timestamp=ts, event_type="recurrence", correction_id=cid,
            data={"original_id": f"C{i-1:03d}"},
        ))

    scores = score_rules(calx_dir)
    assert len(scores) == 1
    assert scores[0].score == 0.0
    assert scores[0].level == "critical"


def test_domain_filter(tmp_path: Path):
    """Scoring with domain filter only returns rules in that domain."""
    calx_dir = _setup_calx(tmp_path)
    write_rule(calx_dir, _make_rule(domain="api", num=1))
    write_rule(calx_dir, _make_rule(domain="frontend", num=1))

    scores = score_rules(calx_dir, domain="api")
    assert len(scores) == 1
    assert scores[0].domain == "api"
