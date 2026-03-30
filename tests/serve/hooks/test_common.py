"""Tests for hooks/_common.py utilities."""

import os
from pathlib import Path

import pytest


def test_find_calx_dir_walks_up(tmp_path, monkeypatch):
    """find_calx_dir should walk up from cwd to find .calx/."""
    from calx.serve.hooks._common import find_calx_dir

    calx = tmp_path / ".calx"
    calx.mkdir()
    subdir = tmp_path / "deep" / "nested"
    subdir.mkdir(parents=True)
    monkeypatch.chdir(subdir)

    result = find_calx_dir()
    assert result is not None
    assert result == calx


def test_find_calx_dir_returns_none_when_missing(tmp_path, monkeypatch):
    """find_calx_dir returns None when no .calx/ exists anywhere up."""
    from calx.serve.hooks._common import find_calx_dir

    monkeypatch.chdir(tmp_path)
    result = find_calx_dir()
    assert result is None


def test_get_session_id_from_env(monkeypatch):
    """get_session_id prefers CLAUDE_SESSION_ID env var."""
    from calx.serve.hooks._common import get_session_id

    monkeypatch.setenv("CLAUDE_SESSION_ID", "test-session-abc")
    assert get_session_id() == "test-session-abc"


def test_get_session_id_from_marker(tmp_path, monkeypatch):
    """get_session_id falls back to hashed session marker file."""
    from calx.serve.hooks._common import get_session_id

    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    calx = tmp_path / ".calx"
    calx.mkdir()
    (calx / ".session_start").write_text("12345:2026-03-27T00:00:00Z")
    monkeypatch.chdir(tmp_path)

    sid = get_session_id()
    assert isinstance(sid, str)
    assert len(sid) == 16  # sha256 hex prefix


def test_get_session_id_stable_for_same_marker(tmp_path, monkeypatch):
    """Same marker file should produce the same session ID."""
    from calx.serve.hooks._common import get_session_id

    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    calx = tmp_path / ".calx"
    calx.mkdir()
    (calx / ".session_start").write_text("12345:2026-03-27T00:00:00Z")
    monkeypatch.chdir(tmp_path)

    id1 = get_session_id()
    id2 = get_session_id()
    assert id1 == id2


def test_get_session_id_fallback_to_ppid(tmp_path, monkeypatch):
    """Falls back to parent PID when no env var or marker."""
    from calx.serve.hooks._common import get_session_id

    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    monkeypatch.chdir(tmp_path)  # no .calx/ dir

    sid = get_session_id()
    assert sid == str(os.getppid())


def test_log_hook_error_writes_timestamped(tmp_path, monkeypatch):
    """log_hook_error appends to .calx/hook-errors.log."""
    from calx.serve.hooks._common import log_hook_error

    calx = tmp_path / ".calx"
    calx.mkdir()
    monkeypatch.chdir(tmp_path)

    log_hook_error("orientation_gate: something broke")

    log_file = calx / "hook-errors.log"
    assert log_file.exists()
    content = log_file.read_text()
    assert "orientation_gate: something broke" in content
    assert "2026-" in content or "202" in content  # has timestamp


def test_log_hook_error_appends(tmp_path, monkeypatch):
    """Multiple errors append, don't overwrite."""
    from calx.serve.hooks._common import log_hook_error

    calx = tmp_path / ".calx"
    calx.mkdir()
    monkeypatch.chdir(tmp_path)

    log_hook_error("error one")
    log_hook_error("error two")

    content = (calx / "hook-errors.log").read_text()
    assert "error one" in content
    assert "error two" in content
