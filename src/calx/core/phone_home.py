"""Anonymous phone-home telemetry for Calx.

Non-blocking, silent on failure. Uses a background thread so the CLI
never waits on network I/O. Respects the ``phone_home`` config toggle.
"""

from __future__ import annotations

import json
import platform
import threading
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_API_URL = "https://calx.sh/api/v1/events"
_TIMEOUT_SECONDS = 2


def send_event(
    calx_dir: Path,
    event_type: str,
    payload: dict | None = None,
) -> None:
    """Fire an anonymous event in a background thread.

    Reads config from *calx_dir*/calx.json. If ``phone_home`` is False
    or anything goes wrong reading config, returns immediately.
    The POST itself runs in a daemon thread -- the CLI never blocks.
    """
    try:
        from calx.core.config import load_config

        config = load_config(calx_dir)

        if not config.phone_home:
            return

        anonymous_id = config.anonymous_id
        if not anonymous_id:
            return

        api_url = config.api_url or DEFAULT_API_URL
    except Exception:
        return

    try:
        from calx import __version__ as calx_version
    except Exception:
        calx_version = "unknown"

    body = {
        "anonymous_id": anonymous_id,
        "event_type": event_type,
        "calx_version": calx_version,
        "os": platform.system(),
        "python_version": platform.python_version(),
        "payload": payload or {},
    }

    thread = threading.Thread(
        target=_post,
        args=(api_url, body),
        daemon=True,
    )
    thread.start()


def _post(url: str, body: dict) -> None:
    """POST JSON to *url*. Swallows every exception."""
    try:
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS)
    except Exception:
        pass
