"""Tests for calx.health.coverage."""

from __future__ import annotations

from pathlib import Path

from calx.core.corrections import CorrectionEvent, append_event, create_correction
from calx.core.rules import Rule, write_rule
from calx.health.coverage import check_coverage


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


def test_empty_calx_dir(tmp_path: Path):
    """Empty calx dir returns zero counts, no gaps."""
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()

    report = check_coverage(calx_dir)
    assert report.total_corrections == 0
    assert report.distilled == 0
    assert report.pending == 0
    assert report.gaps == []


def test_corrections_without_distilled_to_are_pending(tmp_path: Path):
    """Corrections without distilled_to show as pending."""
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()

    create_correction(calx_dir, domain="api", description="first")
    create_correction(calx_dir, domain="api", description="second")

    report = check_coverage(calx_dir)
    assert report.total_corrections == 2
    assert report.pending == 2
    assert report.distilled == 0


def test_distilled_corrections_counted(tmp_path: Path):
    """Distilled corrections counted correctly."""
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()

    c1 = create_correction(calx_dir, domain="api", description="first")
    create_correction(calx_dir, domain="api", description="second")

    # Write the rule so the distilled_to reference is valid
    write_rule(calx_dir, _make_rule(source_corrections=[c1.id]))

    # Distill c1
    append_event(calx_dir, CorrectionEvent(
        timestamp="2026-03-21T01:00:00+00:00",
        event_type="distilled",
        correction_id=c1.id,
        data={"rule_ids": ["api-R001"]},
    ))

    report = check_coverage(calx_dir)
    assert report.total_corrections == 2
    assert report.distilled == 1
    assert report.pending == 1


def test_orphan_rules_detected(tmp_path: Path):
    """Rules with no source corrections (not seed) detected as gaps."""
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()

    # Write a rules file directly with a missing metadata line so the parser
    # returns source_corrections=[] (write_rule would normalise [] to "seed").
    rules_dir = calx_dir / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "api.md").write_text(
        "# Rules: api\n\n### api-R001: Orphan rule\n\nRule body with no metadata.\n"
    )

    report = check_coverage(calx_dir)
    assert len(report.gaps) == 1
    assert "api-R001" in report.gaps[0]
    assert "no source corrections" in report.gaps[0]


def test_rules_citing_nonexistent_corrections(tmp_path: Path):
    """Rules citing non-existent corrections detected."""
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()

    write_rule(calx_dir, _make_rule(source_corrections=["C999"]))

    report = check_coverage(calx_dir)
    assert any("C999" in g and "does not exist" in g for g in report.gaps)


def test_corrections_citing_nonexistent_rules(tmp_path: Path):
    """Corrections citing non-existent rules detected."""
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()

    c1 = create_correction(calx_dir, domain="api", description="test")

    # Distill to a rule that doesn't exist
    append_event(calx_dir, CorrectionEvent(
        timestamp="2026-03-21T01:00:00+00:00",
        event_type="distilled",
        correction_id=c1.id,
        data={"rule_ids": ["api-R999"]},
    ))

    report = check_coverage(calx_dir)
    assert any("api-R999" in g and "does not exist" in g for g in report.gaps)


def test_seed_rules_not_flagged(tmp_path: Path):
    """Seed rules are NOT flagged as orphans."""
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()

    write_rule(calx_dir, _make_rule(source_corrections=["seed"]))

    report = check_coverage(calx_dir)
    assert report.gaps == []
