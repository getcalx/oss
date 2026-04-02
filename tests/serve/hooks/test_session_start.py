"""Tests for hooks/session_start.py."""

import json


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
    # New session_start outputs rules to stdout (for agent context), status to stderr
    assert "general-R001" in captured.out or "Never mock" in captured.out


def test_session_start_falls_back_to_files(tmp_path, monkeypatch, capsys):
    """Without a running server, session start falls back to file-based rules."""
    from calx.serve.hooks.session_start import main

    calx = tmp_path / ".calx"
    calx.mkdir()
    rules_dir = calx / "rules"
    rules_dir.mkdir()
    (rules_dir / "general.md").write_text("# Rules\n\n### general-R001: Test\nTest rule.\n")
    monkeypatch.chdir(tmp_path)

    main()

    captured = capsys.readouterr()
    assert "Server unreachable" in captured.err
    assert "general-R001" in captured.out


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
