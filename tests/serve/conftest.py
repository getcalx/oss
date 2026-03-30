"""Shared test fixtures for calx-serve."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
import pytest_asyncio

from calx.serve.db.engine import (
    CorrectionRow,
    RuleRow,
)

# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_correction(
    id: str = "C001",
    uuid: str = "abc123",
    correction: str = "Don't mock the database in integration tests",
    domain: str = "general",
    category: str = "procedural",
    **overrides,
) -> CorrectionRow:
    defaults = dict(
        id=id, uuid=uuid, correction=correction, domain=domain,
        category=category, created_at=_now(), updated_at=_now(),
    )
    defaults.update(overrides)
    return CorrectionRow(**defaults)


def make_rule(
    id: str = "general-R001",
    rule_text: str = "Use real database connections in integration tests",
    domain: str = "general",
    **overrides,
) -> RuleRow:
    defaults = dict(
        id=id, rule_text=rule_text, domain=domain,
        created_at=_now(), updated_at=_now(),
    )
    defaults.update(overrides)
    return RuleRow(**defaults)


# ---------------------------------------------------------------------------
# Database fixture (in-memory SQLite)
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def db():
    """In-memory SQLite engine with schema applied."""
    from calx.serve.db.sqlite import SQLiteEngine

    engine = SQLiteEngine(db_path=":memory:")
    await engine.initialize()
    yield engine
    await engine.close()


@pytest_asyncio.fixture
async def populated_db(db):
    """Database pre-loaded with sample corrections and rules."""
    corrections = [
        make_correction(id="C001", uuid="u1", domain="general",
                        correction="Don't mock the database in integration tests",
                        surface="reid", confidence="high", recurrence_count=3),
        make_correction(id="C002", uuid="u2", domain="general",
                        correction="Use real database connections",
                        surface="reid", recurrence_of="C001",
                        root_correction_id="C001"),
        make_correction(id="C003", uuid="u3", domain="strategy",
                        correction="Don't negotiate cap in pitches",
                        surface="chat", category="tonal"),
        make_correction(id="C004", uuid="u4", domain="general",
                        correction="Never say 43K lines",
                        surface="cowork", category="factual"),
        make_correction(id="C005", uuid="u5", domain="general",
                        correction="Quarantined test",
                        surface="cli", quarantined=1,
                        quarantine_reason="test quarantine"),
    ]
    for c in corrections:
        await db.insert_correction(c)

    rules = [
        make_rule(id="general-R001",
                  rule_text="Use real database connections in integration tests",
                  domain="general", surface="reid",
                  source_correction_id="C001"),
        make_rule(id="strategy-R001",
                  rule_text="Redirect cap questions to fit, not negotiation",
                  domain="strategy", surface="chat",
                  source_correction_id="C003"),
    ]
    for r in rules:
        await db.insert_rule(r)

    return db


# ---------------------------------------------------------------------------
# File-based .calx/ fixture (for migration tests)
# ---------------------------------------------------------------------------

@pytest.fixture
def calx_dir(tmp_path: Path) -> Path:
    """Temporary .calx/ directory with sample file-based data."""
    calx = tmp_path / ".calx"
    calx.mkdir()

    # calx.json
    config = {
        "schema_version": "1.0",
        "install_id": "test-install",
        "anonymous_id": "test-anon",
        "domains": ["general", "tests"],
        "domain_paths": {},
        "agent_naming": "self",
        "token_discipline": {
            "soft_cap": 200000,
            "ceiling": 250000,
            "model_context_window": 1000000,
        },
        "staleness_days": 30,
        "promotion_threshold": 3,
        "max_prompts_per_session": 3,
    }
    (calx / "calx.json").write_text(json.dumps(config, indent=2))

    # corrections.jsonl (event-sourced format from CLI)
    events = [
        {
            "timestamp": "2026-03-20T10:00:00Z",
            "event_type": "created",
            "correction_id": "C001",
            "data": {
                "uuid": "file-uuid-1",
                "domain": "general",
                "type": "process",
                "description": "Don't mock the database",
                "context": "",
                "source": "explicit",
                "session_id": "sess1",
            },
        },
        {
            "timestamp": "2026-03-21T10:00:00Z",
            "event_type": "created",
            "correction_id": "C002",
            "data": {
                "uuid": "file-uuid-2",
                "domain": "general",
                "type": "process",
                "description": "Use real DB connections",
                "context": "",
                "source": "explicit",
                "session_id": "sess2",
            },
        },
        {
            "timestamp": "2026-03-21T10:01:00Z",
            "event_type": "recurrence",
            "correction_id": "C002",
            "data": {"original_id": "C001"},
        },
    ]
    jsonl_path = calx / "corrections.jsonl"
    with open(jsonl_path, "w") as f:
        for event in events:
            f.write(json.dumps(event) + "\n")

    # rules/general.md
    rules_dir = calx / "rules"
    rules_dir.mkdir()
    (rules_dir / "general.md").write_text(
        "# Rules: general\n\n"
        "### general-R001: Never mock the database in integration tests\n"
        "Source: C001, C002 | Added: 2026-03-21 | Status: active | Type: process\n\n"
        "Use real database connections in integration tests.\n"
    )

    return calx
