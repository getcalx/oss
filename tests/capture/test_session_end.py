"""Tests for calx.capture.session_end."""

from pathlib import Path
from unittest.mock import patch

from calx.capture.session_end import session_end_prompt
from calx.core.config import default_config, save_config
from calx.core.corrections import create_correction
from calx.core.events import read_events
from calx.core.state import check_clean_exit


def _setup_calx_dir(tmp_path: Path) -> Path:
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()
    config = default_config(["api"])
    save_config(calx_dir, config)
    return calx_dir


def test_writes_clean_exit_marker(tmp_path: Path):
    calx_dir = _setup_calx_dir(tmp_path)

    with patch("calx.capture.session_end.subprocess.run") as mock_run:
        mock_run.return_value.stdout = ""
        session_end_prompt(calx_dir)

    status = check_clean_exit(calx_dir)
    assert status.was_clean


def test_reports_undistilled_corrections(tmp_path: Path):
    calx_dir = _setup_calx_dir(tmp_path)
    create_correction(calx_dir, domain="api", description="fix imports")
    create_correction(calx_dir, domain="api", description="use async")

    with patch("calx.capture.session_end.subprocess.run") as mock_run:
        mock_run.return_value.stdout = ""
        message = session_end_prompt(calx_dir)

    assert "2 undistilled correction(s)" in message
    assert "C001" in message
    assert "C002" in message
    assert "calx distill" in message


def test_reports_uncommitted_changes(tmp_path: Path):
    calx_dir = _setup_calx_dir(tmp_path)

    with patch("calx.capture.session_end.subprocess.run") as mock_run:
        mock_run.return_value.stdout = "M src/main.py\n"
        message = session_end_prompt(calx_dir)

    assert "Uncommitted changes" in message


def test_logs_session_end_event(tmp_path: Path):
    calx_dir = _setup_calx_dir(tmp_path)

    with patch("calx.capture.session_end.subprocess.run") as mock_run:
        mock_run.return_value.stdout = ""
        session_end_prompt(calx_dir)

    events = read_events(calx_dir, event_type="session_end")
    assert len(events) == 1
    assert events[0].event == "session_end"
    assert "undistilled_count" in events[0].data


def test_clean_session_end(tmp_path: Path):
    calx_dir = _setup_calx_dir(tmp_path)

    with patch("calx.capture.session_end.subprocess.run") as mock_run:
        mock_run.return_value.stdout = ""
        message = session_end_prompt(calx_dir)

    assert message == "Session ended cleanly. No pending items."
