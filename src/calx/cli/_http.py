"""Shared HTTP helpers for CLI commands that talk to the calx enforcement server."""
from __future__ import annotations

import json
import sys
import urllib.request

import click

DEFAULT_SERVER = "http://127.0.0.1:4195"


def _get_json(path: str, server_url: str = DEFAULT_SERVER) -> dict | None:
    try:
        req = urllib.request.Request(f"{server_url}{path}", method="GET")
        resp = urllib.request.urlopen(req, timeout=5)
        return json.loads(resp.read())
    except Exception:
        return None


def _post_json(path: str, payload: dict, server_url: str = DEFAULT_SERVER) -> dict | None:
    try:
        body = json.dumps(payload).encode()
        req = urllib.request.Request(f"{server_url}{path}", data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        resp = urllib.request.urlopen(req, timeout=5)
        return json.loads(resp.read())
    except Exception:
        return None


def _fail_unreachable():
    click.echo("Failed to reach calx server. Is `calx serve` running?", err=True)
    sys.exit(1)
