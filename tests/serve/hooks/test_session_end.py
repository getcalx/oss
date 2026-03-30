"""Tests for hooks/session_end.py."""

import pytest


def test_session_end_cleans_up_marker(tmp_path, monkeypatch):
    """Session end removes the .session_start marker."""
    from calx.serve.hooks.session_end import main

    calx = tmp_path / ".calx"
    calx.mkdir()
    (calx / ".session_start").write_text("12345:2026-03-27T00:00:00Z")
    monkeypatch.chdir(tmp_path)

    main()

    assert not (calx / ".session_start").exists()


def test_session_end_cleans_up_oriented(tmp_path, monkeypatch):
    """Session end removes the .oriented sentinel."""
    from calx.serve.hooks.session_end import main

    calx = tmp_path / ".calx"
    calx.mkdir()
    (calx / ".oriented").write_text("test-session")
    monkeypatch.chdir(tmp_path)

    main()

    assert not (calx / ".oriented").exists()


def test_session_end_no_calx_dir(tmp_path, monkeypatch):
    """Exits cleanly when no .calx/ directory exists."""
    from calx.serve.hooks.session_end import main

    monkeypatch.chdir(tmp_path)
    main()  # should not raise


def test_session_end_missing_markers(tmp_path, monkeypatch):
    """Handles missing markers gracefully."""
    from calx.serve.hooks.session_end import main

    calx = tmp_path / ".calx"
    calx.mkdir()
    monkeypatch.chdir(tmp_path)

    main()  # should not raise even with no markers to clean
