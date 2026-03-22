"""Tests for calx.health.floor."""

from __future__ import annotations

from pathlib import Path

from calx.core.state import load_state, save_state, HealthState
from calx.health.floor import FloorTrajectory, get_trajectory, record_session


def _setup_calx(tmp_path: Path) -> Path:
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()
    return calx_dir


def test_record_session_appends_to_history(tmp_path: Path):
    """record_session appends an entry to correction_rate_history."""
    calx_dir = _setup_calx(tmp_path)

    record_session(calx_dir, corrections_in_session=3)
    record_session(calx_dir, corrections_in_session=1)

    state = load_state(calx_dir)
    assert len(state.correction_rate_history) == 2
    assert state.correction_rate_history[0]["corrections"] == 3
    assert state.correction_rate_history[1]["corrections"] == 1


def test_get_trajectory_returns_valid(tmp_path: Path):
    """get_trajectory returns a valid FloorTrajectory."""
    calx_dir = _setup_calx(tmp_path)

    record_session(calx_dir, corrections_in_session=5)
    record_session(calx_dir, corrections_in_session=3)

    traj = get_trajectory(calx_dir)
    assert isinstance(traj, FloorTrajectory)
    assert traj.total_sessions == 2
    assert traj.current_rate == 4.0  # avg of [5, 3]
    assert traj.trend in ("declining", "increasing", "plateau")


def test_plateau_detected_when_stable(tmp_path: Path):
    """Plateau is detected when correction rate is stable across many sessions."""
    calx_dir = _setup_calx(tmp_path)

    # Create 20 sessions with stable rate (2 corrections each)
    state = load_state(calx_dir)
    for i in range(20):
        state.correction_rate_history.append({
            "date": f"2026-03-{i + 1:02d}",
            "corrections": 2,
        })
    save_state(calx_dir, state)

    traj = get_trajectory(calx_dir)
    assert traj.is_at_floor is True
    assert traj.trend == "plateau"
    assert traj.message is not None
    assert "stabilized" in traj.message


def test_no_plateau_with_insufficient_data(tmp_path: Path):
    """Plateau is not detected with fewer than window * 3 sessions."""
    calx_dir = _setup_calx(tmp_path)

    # Only 5 sessions — not enough for plateau detection (window=5, need 15)
    state = load_state(calx_dir)
    for i in range(5):
        state.correction_rate_history.append({
            "date": f"2026-03-{i + 1:02d}",
            "corrections": 2,
        })
    save_state(calx_dir, state)

    traj = get_trajectory(calx_dir)
    assert traj.is_at_floor is False


def test_empty_history(tmp_path: Path):
    """Empty history returns zero rate, declining trend, no floor."""
    calx_dir = _setup_calx(tmp_path)

    traj = get_trajectory(calx_dir)
    assert traj.current_rate == 0.0
    assert traj.trend == "declining"
    assert traj.is_at_floor is False
    assert traj.total_sessions == 0


def test_declining_trend(tmp_path: Path):
    """Declining corrections detected as declining trend."""
    calx_dir = _setup_calx(tmp_path)

    state = load_state(calx_dir)
    # First half: high corrections, second half: low
    for i in range(10):
        state.correction_rate_history.append({
            "date": f"2026-03-{i + 1:02d}",
            "corrections": 10 if i < 5 else 1,
        })
    save_state(calx_dir, state)

    traj = get_trajectory(calx_dir)
    assert traj.trend == "declining"


def test_increasing_trend(tmp_path: Path):
    """Increasing corrections detected as increasing trend."""
    calx_dir = _setup_calx(tmp_path)

    state = load_state(calx_dir)
    # First half: low, second half: high
    for i in range(10):
        state.correction_rate_history.append({
            "date": f"2026-03-{i + 1:02d}",
            "corrections": 1 if i < 5 else 10,
        })
    save_state(calx_dir, state)

    traj = get_trajectory(calx_dir)
    assert traj.trend == "increasing"
