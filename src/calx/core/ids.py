"""ID generation utilities for Calx."""

import re
import secrets
from uuid import uuid4


def generate_uuid() -> str:
    """Generate a compact UUID (no dashes)."""
    return uuid4().hex


def next_sequential_id(prefix: str, existing: list[str]) -> str:
    """Generate the next sequential ID.

    Given prefix "C" and existing ["C001", "C002"], returns "C003".
    Given prefix "C" and empty list, returns "C001".
    """
    if not existing:
        return f"{prefix}001"

    pattern = re.compile(rf"^{re.escape(prefix)}(\d+)$")
    max_num = 0
    for item in existing:
        match = pattern.match(item)
        if match:
            max_num = max(max_num, int(match.group(1)))

    return f"{prefix}{max_num + 1:03d}"


def generate_session_id() -> str:
    """Generate an 8-character random hex session ID."""
    return secrets.token_hex(4)
