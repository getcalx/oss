"""Tests for calx.health.conversion."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from calx.core.corrections import CorrectionEvent, append_event
from calx.core.rules import Rule, write_rule
from calx.health.conversion import find_conversion_candidates


def _make_rule(domain: str = "api", num: int = 1, **kwargs) -> Rule:
    defaults = {
        "id": f"{domain}-R{num:03d}",
        "domain": domain,
        "type": "process",
        "source_corrections": ["C001"],
        "added": "2026-01-01",
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


def test_process_rule_with_violations_flagged(tmp_path: Path):
    """Process rules with 2+ post-creation recurrence violations are flagged."""
    calx_dir = _setup_calx(tmp_path)
    write_rule(calx_dir, _make_rule(added="2026-01-01"))

    # Create 2 recurrence corrections after the rule was created
    for i, cid in enumerate(["C010", "C011"]):
        ts = f"2026-02-{10 + i:02d}T00:00:00+00:00"
        append_event(calx_dir, CorrectionEvent(
            timestamp=ts, event_type="created", correction_id=cid,
            data={"uuid": f"u{i}", "domain": "api", "description": f"violation {i}"},
        ))
        append_event(calx_dir, CorrectionEvent(
            timestamp=ts, event_type="recurrence", correction_id=cid,
            data={"original_id": "C001"},
        ))

    candidates = find_conversion_candidates(calx_dir)
    assert len(candidates) == 1
    assert candidates[0].rule_id == "api-R001"
    assert candidates[0].recurrence_count == 2


def test_architectural_rules_excluded(tmp_path: Path):
    """Architectural rules are never flagged for conversion."""
    calx_dir = _setup_calx(tmp_path)
    write_rule(calx_dir, _make_rule(type="architectural", added="2026-01-01"))

    for i, cid in enumerate(["C010", "C011"]):
        ts = f"2026-02-{10 + i:02d}T00:00:00+00:00"
        append_event(calx_dir, CorrectionEvent(
            timestamp=ts, event_type="created", correction_id=cid,
            data={"uuid": f"u{i}", "domain": "api", "description": f"violation {i}"},
        ))
        append_event(calx_dir, CorrectionEvent(
            timestamp=ts, event_type="recurrence", correction_id=cid,
            data={"original_id": "C001"},
        ))

    candidates = find_conversion_candidates(calx_dir)
    assert candidates == []


def test_message_format_includes_rule_id(tmp_path: Path):
    """Conversion message includes the rule ID."""
    calx_dir = _setup_calx(tmp_path)
    write_rule(calx_dir, _make_rule(added="2026-01-01"))

    for i, cid in enumerate(["C010", "C011", "C012"]):
        ts = f"2026-02-{10 + i:02d}T00:00:00+00:00"
        append_event(calx_dir, CorrectionEvent(
            timestamp=ts, event_type="created", correction_id=cid,
            data={"uuid": f"u{i}", "domain": "api", "description": f"violation {i}"},
        ))
        append_event(calx_dir, CorrectionEvent(
            timestamp=ts, event_type="recurrence", correction_id=cid,
            data={"original_id": "C001"},
        ))

    candidates = find_conversion_candidates(calx_dir)
    assert len(candidates) == 1
    assert "api-R001" in candidates[0].message
    assert "architectural" in candidates[0].message


def test_single_violation_not_flagged(tmp_path: Path):
    """A rule with only 1 post-creation violation is not flagged."""
    calx_dir = _setup_calx(tmp_path)
    write_rule(calx_dir, _make_rule(added="2026-01-01"))

    ts = "2026-02-10T00:00:00+00:00"
    append_event(calx_dir, CorrectionEvent(
        timestamp=ts, event_type="created", correction_id="C010",
        data={"uuid": "u1", "domain": "api", "description": "violation"},
    ))
    append_event(calx_dir, CorrectionEvent(
        timestamp=ts, event_type="recurrence", correction_id="C010",
        data={"original_id": "C001"},
    ))

    candidates = find_conversion_candidates(calx_dir)
    assert candidates == []


def test_empty_calx_dir(tmp_path: Path):
    """Empty calx dir returns no candidates."""
    calx_dir = _setup_calx(tmp_path)
    candidates = find_conversion_candidates(calx_dir)
    assert candidates == []
