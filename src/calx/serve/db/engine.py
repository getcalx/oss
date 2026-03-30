"""Database engine protocol and row types."""
from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class CorrectionRow:
    id: str
    uuid: str
    correction: str
    domain: str
    category: str
    severity: str = "medium"
    confidence: str = "medium"
    surface: str = "cli"
    task_context: str | None = None
    briefing_state: str | None = None
    keywords: str | None = None
    recurrence_of: str | None = None
    root_correction_id: str | None = None
    recurrence_count: int = 1
    promoted: int = 0
    quarantined: int = 0
    quarantine_reason: str | None = None
    created_at: str = ""
    updated_at: str = ""


@dataclass
class RuleRow:
    id: str
    rule_text: str
    domain: str
    surface: str | None = None
    source_correction_id: str | None = None
    active: int = 1
    health_score: float | None = None
    created_at: str = ""
    updated_at: str = ""


@dataclass
class MetricRow:
    id: int = 0
    name: str = ""
    value: float = 0.0
    source: str | None = None
    metadata: str | None = None
    measured_at: str = ""


@dataclass
class PipelineRow:
    investor: str = ""
    status: str | None = None
    gate: str | None = None
    notes: str | None = None
    updated_at: str = ""


@dataclass
class DecisionRow:
    id: int = 0
    decision: str = ""
    context: str | None = None
    surface: str | None = None
    created_at: str = ""


@dataclass
class ContextRow:
    key: str = ""
    value: str = ""
    category: str | None = None
    updated_at: str = ""


@runtime_checkable
class DatabaseEngine(Protocol):
    """Backend interface. SQLite and Postgres implement this."""

    # Corrections
    async def insert_correction(self, correction: CorrectionRow) -> str: ...
    async def get_correction(self, correction_id: str) -> CorrectionRow | None: ...
    async def correction_exists(self, uuid: str) -> bool: ...
    async def max_correction_num(self) -> int: ...
    async def find_corrections(
        self, domain: str | None = None, limit: int = 100,
    ) -> list[CorrectionRow]: ...
    async def find_corrections_by_keywords(
        self, keywords: list[str], domain: str | None = None, limit: int = 200,
    ) -> list[CorrectionRow]: ...
    async def update_correction(self, correction_id: str, **fields: object) -> None: ...
    async def increment_recurrence_count(self, correction_id: str) -> int: ...

    # Rules
    async def insert_rule(self, rule: RuleRow) -> str: ...
    async def get_rule(self, rule_id: str) -> RuleRow | None: ...
    async def rule_exists(self, rule_id: str) -> bool: ...
    async def find_rules(
        self, domain: str | None = None, active_only: bool = True,
    ) -> list[RuleRow]: ...
    async def next_rule_id(self, domain: str) -> str: ...
    async def update_rule(self, rule_id: str, **fields: object) -> None: ...

    # Metrics
    async def insert_metric(
        self, name: str, value: float,
        source: str | None = None, metadata: dict | None = None,
    ) -> int: ...
    async def get_latest_metrics(self, name: str | None = None) -> list[MetricRow]: ...

    # Pipeline
    async def upsert_pipeline(
        self, investor: str,
        status: str | None = None, gate: str | None = None, notes: str | None = None,
    ) -> None: ...
    async def get_pipeline(self, investor: str | None = None) -> list[PipelineRow]: ...

    # Decisions
    async def insert_decision(
        self, decision: str, context: str | None = None, surface: str | None = None,
    ) -> int: ...
    async def get_decisions(self, since: str | None = None) -> list[DecisionRow]: ...

    # Context
    async def set_context(
        self, key: str, value: str, category: str | None = None,
    ) -> None: ...
    async def get_context(self, category: str | None = None) -> list[ContextRow]: ...

    # Telemetry
    async def log_telemetry(
        self, event_type: str, tool_or_resource: str,
        surface: str | None = None, params: dict | None = None,
        response_status: str | None = None, latency_ms: float | None = None,
    ) -> None: ...

    # Schema
    async def get_schema_version(self) -> int: ...
    async def set_schema_version(self, version: int) -> None: ...

    # Transaction
    def transaction(self) -> AsyncIterator[None]: ...

    # Lifecycle
    async def initialize(self) -> None: ...
    async def close(self) -> None: ...
