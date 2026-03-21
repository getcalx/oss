"""Tests for calx.core.state."""

from pathlib import Path

from calx.core.state import (
    HealthState,
    RuleHealthData,
    check_clean_exit,
    load_state,
    remove_clean_exit,
    save_state,
    write_clean_exit,
)


def test_clean_exit_cycle(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()

    # No marker = dirty
    status = check_clean_exit(calx_dir)
    assert not status.was_clean

    # Write marker = clean
    write_clean_exit(calx_dir)
    status = check_clean_exit(calx_dir)
    assert status.was_clean
    assert status.last_exit_time is not None

    # Remove marker = dirty again
    remove_clean_exit(calx_dir)
    status = check_clean_exit(calx_dir)
    assert not status.was_clean


def test_state_save_load(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()

    state = HealthState(
        last_health_check="2026-03-21",
        rule_scores={
            "api-R001": RuleHealthData(score=0.8, recurrence_count=2),
        },
        correction_rate_history=[
            {"date": "2026-03-21", "corrections": 3},
        ],
    )
    save_state(calx_dir, state)

    loaded = load_state(calx_dir)
    assert loaded.last_health_check == "2026-03-21"
    assert loaded.rule_scores["api-R001"].score == 0.8
    assert loaded.rule_scores["api-R001"].recurrence_count == 2
    assert len(loaded.correction_rate_history) == 1


def test_load_missing(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()
    state = load_state(calx_dir)
    assert state.schema_version == "1.0"
    assert state.rule_scores == {}


def test_load_malformed(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    health_dir = calx_dir / "health"
    health_dir.mkdir(parents=True)
    (health_dir / "state.json").write_text("{bad", encoding="utf-8")

    state = load_state(calx_dir)
    assert state.schema_version == "1.0"
