"""Tests for hooks/session_start.py."""

import json
from pathlib import Path

import pytest


def test_session_start_with_no_calx_dir(tmp_path, monkeypatch, capsys):
    """Exits cleanly when no .calx/ directory exists."""
    from calx.serve.hooks.session_start import main

    monkeypatch.chdir(tmp_path)
    main()  # should not raise
    # No output expected when no calx dir


def test_session_start_injects_rules_from_files(tmp_path, monkeypatch, capsys):
    """File-based rule injection writes rule content to stderr."""
    from calx.serve.hooks.session_start import main

    calx = tmp_path / ".calx"
    calx.mkdir()

    rules_dir = calx / "rules"
    rules_dir.mkdir()
    (rules_dir / "general.md").write_text(
        "# Rules: general\n\n"
        "### general-R001: Never mock the database\n"
        "Use real connections.\n"
    )

    monkeypatch.chdir(tmp_path)
    main()

    captured = capsys.readouterr()
    assert "general-R001" in captured.err or "Never mock" in captured.err


def test_session_start_writes_session_marker(tmp_path, monkeypatch):
    """Session start writes .session_start marker for orientation gate."""
    from calx.serve.hooks.session_start import main

    calx = tmp_path / ".calx"
    calx.mkdir()
    monkeypatch.chdir(tmp_path)

    main()

    marker = calx / ".session_start"
    assert marker.exists()
    content = marker.read_text().strip()
    assert ":" in content  # ppid:timestamp format


def test_session_start_checks_jsonl_integrity(tmp_path, monkeypatch):
    """Session start runs integrity check on corrections.jsonl."""
    from calx.serve.hooks.session_start import main

    calx = tmp_path / ".calx"
    calx.mkdir()

    # Write valid JSONL
    events = [
        {"timestamp": "2026-03-20T10:00:00Z", "event_type": "created",
         "correction_id": "C001", "data": {"uuid": "u1"}},
    ]
    with open(calx / "corrections.jsonl", "w") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")

    monkeypatch.chdir(tmp_path)
    main()  # should not raise on valid JSONL
