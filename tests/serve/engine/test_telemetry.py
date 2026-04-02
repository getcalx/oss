"""Tests for telemetry: payload, sender, CLI.

Sender tests: 3 (unreachable, timeout, thread join)
Payload tests: 4 (shape, empty db, no sensitive data, new fields)
CLI tests: 3 (show, off, on)
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio

from tests.serve.conftest import make_correction, make_rule


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def db():
    """In-memory SQLite engine with schema applied."""
    from calx.serve.db.sqlite import SQLiteEngine

    engine = SQLiteEngine(db_path=":memory:")
    await engine.initialize()
    yield engine
    await engine.close()


# ---------------------------------------------------------------------------
# Payload tests
# ---------------------------------------------------------------------------

class TestBuildPayloadCorrectShape:

    @pytest.mark.asyncio
    async def test_build_payload_correct_shape(self, db):
        """Build payload from populated DB, verify all keys present."""
        from calx.serve.engine.telemetry_payload import build_telemetry_payload

        await db.insert_correction(make_correction(
            id="C001", uuid="u1", correction="test correction",
        ))
        await db.insert_rule(make_rule(
            id="general-R001", rule_text="test rule",
        ))

        payload = await build_telemetry_payload(db)

        required_keys = {
            "v", "install_id", "payload_id", "calx_version", "os",
            "arch", "python_version", "days_since_install",
            "session_duration_minutes", "tool_call_count",
            "features_used", "counts", "collapse_guard_fires", "dirty_exits",
        }
        for key in required_keys:
            assert key in payload, f"Missing key: {key}"
        assert payload["v"] == 1


class TestBuildPayloadEmptyDb:

    @pytest.mark.asyncio
    async def test_build_payload_empty_db(self, db):
        """Empty DB gives features_used all False, counts all 0."""
        from calx.serve.engine.telemetry_payload import build_telemetry_payload

        payload = await build_telemetry_payload(db)

        counts = payload["counts"]
        assert counts["total_corrections"] == 0
        assert counts["total_rules"] == 0

        features = payload["features_used"]
        assert all(v is False for v in features.values()), (
            f"Expected all features_used to be False for empty DB, got: {features}"
        )


class TestBuildPayloadNoSensitiveData:

    @pytest.mark.asyncio
    async def test_build_payload_no_sensitive_data(self, db):
        """Correction/rule text must NOT appear in serialized payload."""
        from calx.serve.engine.telemetry_payload import build_telemetry_payload

        sensitive_correction = "SUPER_SECRET_CORRECTION_TEXT_12345"
        sensitive_rule = "SUPER_SECRET_RULE_TEXT_67890"

        await db.insert_correction(make_correction(
            id="C099", uuid="u99", correction=sensitive_correction,
        ))
        await db.insert_rule(make_rule(
            id="general-R099", rule_text=sensitive_rule,
        ))

        payload = await build_telemetry_payload(db)
        serialized = json.dumps(payload)

        assert sensitive_correction not in serialized, (
            "Correction text leaked into telemetry payload"
        )
        assert sensitive_rule not in serialized, (
            "Rule text leaked into telemetry payload"
        )


class TestBuildPayloadHasNewFields:

    @pytest.mark.asyncio
    async def test_build_payload_has_new_fields(self, db):
        """Payload has install_id (UUID), python_version, arch, days_since_install."""
        from calx.serve.engine.telemetry_payload import build_telemetry_payload

        payload = await build_telemetry_payload(db)

        install_id = payload["install_id"]
        uuid.UUID(install_id)  # raises ValueError if not valid

        assert isinstance(payload["python_version"], str)
        assert len(payload["python_version"]) > 0

        assert isinstance(payload["arch"], str)
        assert len(payload["arch"]) > 0

        assert isinstance(payload["days_since_install"], (int, float))


# ---------------------------------------------------------------------------
# Sender tests
# ---------------------------------------------------------------------------

class TestSendUnreachableFailsSilently:

    def test_send_unreachable_fails_silently(self):
        """POST to non-routable IP raises no exception."""
        from calx.serve.engine.telemetry_sender import send_telemetry

        # 198.51.100.1 is TEST-NET-2 (RFC 5737), non-routable
        send_telemetry({"test": True}, endpoint_url="http://198.51.100.1:9999/telemetry")


class TestSendTimeout:

    def test_send_timeout(self):
        """Mock urlopen to raise timeout, no exception propagated."""
        import socket
        from calx.serve.engine import telemetry_sender

        with patch("urllib.request.urlopen", side_effect=socket.timeout("timed out")):
            telemetry_sender.send_telemetry({"test": True})


class TestSendJoinsThread:

    def test_send_joins_thread(self):
        """Sender uses thread.join(timeout=6), not daemon fire-and-forget."""
        from calx.serve.engine import telemetry_sender

        with patch("threading.Thread") as MockThread:
            mock_thread_instance = MagicMock()
            MockThread.return_value = mock_thread_instance

            telemetry_sender.send_telemetry({"test": True})

            mock_thread_instance.start.assert_called_once()
            mock_thread_instance.join.assert_called_once()
            join_args = mock_thread_instance.join.call_args
            assert join_args is not None
            timeout_val = join_args[1].get("timeout") if join_args[1] else (
                join_args[0][0] if join_args[0] else None
            )
            assert timeout_val == 6, f"Expected join(timeout=6), got timeout={timeout_val}"


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------

class TestCliTelemetryShow:

    def test_cli_telemetry_show(self, tmp_path, monkeypatch):
        """calx telemetry --show outputs valid JSON with correct shape."""
        from click.testing import CliRunner
        from calx.cli.telemetry_cmd import telemetry

        calx_dir = tmp_path / ".calx"
        calx_dir.mkdir()
        calx_json = {
            "schema_version": "2.0",
            "telemetry": {
                "enabled": True,
                "install_id": str(uuid.uuid4()),
            },
        }
        (calx_dir / "calx.json").write_text(json.dumps(calx_json))

        monkeypatch.setattr(
            "calx.cli.telemetry_cmd.find_calx_dir", lambda: calx_dir,
        )

        runner = CliRunner()
        result = runner.invoke(telemetry, ["--show"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "enabled" in data
        assert "install_id" in data


class TestCliTelemetryOff:

    def test_cli_telemetry_off(self, tmp_path, monkeypatch):
        """calx telemetry --off sets telemetry.enabled=false in calx.json."""
        from click.testing import CliRunner
        from calx.cli.telemetry_cmd import telemetry

        calx_dir = tmp_path / ".calx"
        calx_dir.mkdir()
        calx_json = {
            "schema_version": "2.0",
            "telemetry": {"enabled": True},
        }
        (calx_dir / "calx.json").write_text(json.dumps(calx_json))

        monkeypatch.setattr(
            "calx.cli.telemetry_cmd.find_calx_dir", lambda: calx_dir,
        )

        runner = CliRunner()
        result = runner.invoke(telemetry, ["--off"])

        updated = json.loads((calx_dir / "calx.json").read_text())
        assert updated["telemetry"]["enabled"] is False


class TestCliTelemetryOn:

    def test_cli_telemetry_on(self, tmp_path, monkeypatch):
        """calx telemetry --on sets telemetry.enabled=true in calx.json."""
        from click.testing import CliRunner
        from calx.cli.telemetry_cmd import telemetry

        calx_dir = tmp_path / ".calx"
        calx_dir.mkdir()
        calx_json = {
            "schema_version": "2.0",
            "telemetry": {"enabled": False},
        }
        (calx_dir / "calx.json").write_text(json.dumps(calx_json))

        monkeypatch.setattr(
            "calx.cli.telemetry_cmd.find_calx_dir", lambda: calx_dir,
        )

        runner = CliRunner()
        result = runner.invoke(telemetry, ["--on"])

        updated = json.loads((calx_dir / "calx.json").read_text())
        assert updated["telemetry"]["enabled"] is True
