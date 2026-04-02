"""Send telemetry payload to Supabase Edge Function.

Fire-and-forget with thread.join(timeout=6). Never raises.
Uses except Exception (not bare except) per panel 7/7 consensus.
"""
from __future__ import annotations

import json
import threading
import urllib.request

TELEMETRY_ENDPOINT = (
    "https://airkogwxvzmgdmaezcue.supabase.co/functions/v1/telemetry-ingest"
)


def _post_payload(payload: dict, endpoint_url: str) -> None:
    """POST JSON payload. Called in a background thread."""
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            endpoint_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass


def send_telemetry(
    payload: dict,
    endpoint_url: str = TELEMETRY_ENDPOINT,
) -> None:
    """Send telemetry in a background thread with join(timeout=6).

    Never raises. Never retries. Gives the send 6 seconds to complete
    before the process exits, avoiding systematic data loss.
    """
    try:
        t = threading.Thread(target=_post_payload, args=(payload, endpoint_url))
        t.start()
        t.join(timeout=6)
    except Exception:
        pass
