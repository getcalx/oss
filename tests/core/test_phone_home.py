"""Tests for calx.core.phone_home."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from calx.core.config import CalxConfig, save_config
from calx.core.phone_home import _post, send_event


def _setup(tmp_path: Path, **overrides) -> Path:
    """Create a .calx dir with config and return calx_dir."""
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()
    defaults = {
        "install_id": "inst-001",
        "anonymous_id": "anon-uuid-1234",
        "domains": ["api"],
        "phone_home": True,
        "api_url": "https://calx.sh/api/v1/events",
    }
    defaults.update(overrides)
    save_config(calx_dir, CalxConfig(**defaults))
    return calx_dir


# --- Payload shape ---


def test_send_event_payload_shape(tmp_path: Path):
    """The POST body contains all required fields."""
    calx_dir = _setup(tmp_path)
    captured: list[dict] = []

    def fake_post(url: str, body: dict) -> None:
        captured.append(body)

    with (
        patch("calx.core.phone_home._post", side_effect=fake_post),
        patch("calx.core.phone_home.threading") as mock_threading,
    ):
            # Make the thread run synchronously
            mock_thread = MagicMock()
            mock_threading.Thread.return_value = mock_thread

            def run_target(**kwargs):
                pass

            def capture_start():
                # Extract the target and args from the Thread constructor call
                call_kwargs = mock_threading.Thread.call_args
                target = call_kwargs.kwargs.get("target") or call_kwargs[1].get("target")
                args = call_kwargs.kwargs.get("args") or call_kwargs[1].get("args", ())
                if target is None:
                    _, kw = call_kwargs
                    target = kw.get("target")
                    args = kw.get("args", ())
                target(*args)

            mock_thread.start = capture_start
            send_event(calx_dir, "install", {"foo": "bar"})

    assert len(captured) == 1
    body = captured[0]
    assert body["anonymous_id"] == "anon-uuid-1234"
    assert body["event_type"] == "install"
    assert body["payload"] == {"foo": "bar"}
    assert "calx_version" in body
    assert "os" in body
    assert "python_version" in body


def test_send_event_payload_shape_simple(tmp_path: Path):
    """Verify payload via direct _post mock with synchronous thread execution."""
    calx_dir = _setup(tmp_path)
    captured_bodies: list[dict] = []

    def intercept_post(url: str, body: dict) -> None:
        captured_bodies.append(body)

    with patch("calx.core.phone_home._post", side_effect=intercept_post):
        # Run send_event but intercept the thread to run synchronously
        import calx.core.phone_home as ph

        original_thread = ph.threading.Thread

        class SyncThread:
            def __init__(self, *, target, args, daemon=False):
                self._target = target
                self._args = args

            def start(self):
                self._target(*self._args)

        ph.threading.Thread = SyncThread  # type: ignore[assignment]
        try:
            send_event(calx_dir, "session", {"correction_count": 5})
        finally:
            ph.threading.Thread = original_thread  # type: ignore[assignment]

    assert len(captured_bodies) == 1
    body = captured_bodies[0]
    assert body["anonymous_id"] == "anon-uuid-1234"
    assert body["event_type"] == "session"
    assert body["payload"]["correction_count"] == 5
    assert "calx_version" in body
    assert "os" in body
    assert "python_version" in body


# --- Opt-out ---


def test_send_event_disabled(tmp_path: Path):
    """No POST when phone_home is False."""
    calx_dir = _setup(tmp_path, phone_home=False)

    with patch("calx.core.phone_home._post") as mock_post:
        send_event(calx_dir, "install")

    mock_post.assert_not_called()


def test_send_event_no_anonymous_id(tmp_path: Path):
    """No POST when anonymous_id is empty."""
    calx_dir = _setup(tmp_path, anonymous_id="")

    with patch("calx.core.phone_home._post") as mock_post:
        send_event(calx_dir, "install")

    mock_post.assert_not_called()


# --- Missing / corrupt config ---


def test_send_event_missing_config(tmp_path: Path):
    """No crash when calx_dir has no config file."""
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()
    # Don't create calx.json -- load_config returns defaults (anonymous_id="")

    with patch("calx.core.phone_home._post") as mock_post:
        send_event(calx_dir, "install")

    mock_post.assert_not_called()


def test_send_event_corrupt_config(tmp_path: Path):
    """No crash when config is corrupt JSON."""
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()
    (calx_dir / "calx.json").write_text("not json at all", encoding="utf-8")

    with patch("calx.core.phone_home._post") as mock_post:
        # Should not raise
        send_event(calx_dir, "install")

    mock_post.assert_not_called()


# --- Silent failure ---


def test_post_swallows_connection_error():
    """_post swallows network errors silently."""
    # Should not raise
    _post("http://localhost:1", {"test": True})


def test_post_swallows_timeout():
    """_post swallows timeout errors silently."""
    with patch("calx.core.phone_home.urllib.request.urlopen", side_effect=TimeoutError):
        _post("https://calx.sh/api/v1/events", {"test": True})


def test_post_swallows_value_error():
    """_post swallows ValueError silently."""
    with patch(
        "calx.core.phone_home.urllib.request.urlopen",
        side_effect=ValueError("bad url"),
    ):
        _post("https://calx.sh/api/v1/events", {"test": True})


# --- Non-blocking ---


def test_send_event_uses_daemon_thread(tmp_path: Path):
    """send_event starts a daemon thread."""
    calx_dir = _setup(tmp_path)

    with patch("calx.core.phone_home.threading.Thread") as mock_thread_cls:
        mock_instance = MagicMock()
        mock_thread_cls.return_value = mock_instance

        send_event(calx_dir, "install")

        mock_thread_cls.assert_called_once()
        call_kwargs = mock_thread_cls.call_args
        assert call_kwargs.kwargs.get("daemon") is True
        mock_instance.start.assert_called_once()


# --- Empty payload ---


def test_send_event_no_payload(tmp_path: Path):
    """Payload defaults to empty dict when None."""
    calx_dir = _setup(tmp_path)
    captured: list[dict] = []

    import calx.core.phone_home as ph

    original_thread = ph.threading.Thread

    class SyncThread:
        def __init__(self, *, target, args, daemon=False):
            self._target = target
            self._args = args

        def start(self):
            self._target(*self._args)

    def intercept(url, body):
        captured.append(body)

    with patch("calx.core.phone_home._post", side_effect=intercept):
        ph.threading.Thread = SyncThread  # type: ignore[assignment]
        try:
            send_event(calx_dir, "install")
        finally:
            ph.threading.Thread = original_thread  # type: ignore[assignment]

    assert captured[0]["payload"] == {}
