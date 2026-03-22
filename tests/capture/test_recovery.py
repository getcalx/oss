"""Tests for calx.capture.recovery."""

from pathlib import Path

from calx.capture.recovery import recovery_check
from calx.core.state import write_clean_exit


def test_returns_none_for_clean_exit(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()

    write_clean_exit(calx_dir)
    result = recovery_check(calx_dir)
    assert result is None


def test_returns_message_for_dirty_exit(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()

    # No clean-exit marker = dirty
    result = recovery_check(calx_dir)
    assert result is not None
    assert "did not exit cleanly" in result
    assert "calx status" in result
