"""Database engine protocol and row types."""
from __future__ import annotations

from dataclasses import dataclass, field
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
    learning_mode: str = "unknown"
    created_at: str = ""
    updated_at: str = ""


@dataclass
class RuleRow:
    id: str
    rule_text: str
    domain: str
    surface: str | None = None
    source_correction_id: str | None = None
    learning_mode: str = "unknown"
    health_score: float = 1.0
    health_status: str = "healthy"
    last_validated_at: str | None = None
    compiled_at: str | None = None
    compiled_via: str | None = None
    compiled_from_mode: str | None = None
    recurrence_at_compilation: int | None = None
    deactivation_reason: str | None = None
    role: str | None = None
    active: int = 1
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


@dataclass
class SessionRow:
    id: str
    surface: str
    surface_type: str
    oriented: int = 0
    token_estimate: int = 0
    soft_cap: int = 200000
    ceiling: int = 250000
    tool_call_count: int = 0
    server_fail_mode: str = "open"
    collapse_fail_mode: str = "closed"
    started_at: str = ""
    ended_at: str | None = None


@dataclass
class HandoffRow:
    id: int = 0
    session_id: str = ""
    what_changed: str = ""
    what_others_need: str | None = None
    decisions_deferred: str | None = None
    next_priorities: str | None = None
    created_at: str = ""


@dataclass
class BoardStateRow:
    id: int = 0
    domain: str = ""
    description: str = ""
    status: str = ""
    blocked_reason: str | None = None
    updated_at: str = ""


@dataclass
class FoilReviewRow:
    id: int = 0
    spec_reference: str = ""
    reviewer_domain: str = ""
    verdict: str = ""
    findings: str | None = None
    round: int = 1
    session_id: str | None = None
    created_at: str = ""


@dataclass
class CompilationEventRow:
    id: int = 0
    rule_id: str = ""
    source_correction_id: str | None = None
    rule_text: str = ""
    learning_mode_before: str = ""
    mechanism_type: str = ""
    mechanism_description: str = ""
    mechanism_reference: str | None = None
    recurrence_count_at_compilation: int = 0
    rule_age_days: int = 0
    correction_chain_length: int = 0
    post_compilation_recurrence: int = 0
    verified_at: str | None = None
    created_at: str = ""


@dataclass
class PlanRow:
    id: int = 0
    task_description: str = ""
    chunks: str = "[]"
    dependency_edges: str = "[]"
    phase: str = "spec"
    spec_file: str | None = None
    test_files: str | None = None
    review_id: int | None = None
    current_wave: int = 1
    wave_verification: str | None = None
    status: str = "active"
    created_at: str = ""
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

    # Sessions
    async def insert_session(self, session: SessionRow) -> str: ...
    async def get_session(self, session_id: str) -> SessionRow | None: ...
    async def update_session(self, session_id: str, **fields: object) -> None: ...
    async def get_active_session(self) -> SessionRow | None: ...

    # Handoffs
    async def insert_handoff(self, handoff: HandoffRow) -> int: ...
    async def get_latest_handoff(self, session_id: str | None = None) -> HandoffRow | None: ...

    # Board state
    async def insert_board_item(self, item: BoardStateRow) -> int: ...
    async def get_board_state(self, status: str | None = None) -> list[BoardStateRow]: ...
    async def update_board_item(self, item_id: int, **fields: object) -> None: ...

    # Foil reviews
    async def insert_foil_review(self, review: FoilReviewRow) -> int: ...
    async def get_foil_reviews(self, spec_reference: str | None = None) -> list[FoilReviewRow]: ...

    # Compilation events
    async def insert_compilation_event(self, event: CompilationEventRow) -> int: ...
    async def get_compilation_events(self, rule_id: str | None = None) -> list[CompilationEventRow]: ...
    async def update_compilation_event(self, event_id: int, **fields: object) -> None: ...

    # Plans
    async def insert_plan(self, plan: PlanRow) -> int: ...
    async def get_plan(self, plan_id: int) -> PlanRow | None: ...
    async def get_active_plan(self) -> PlanRow | None: ...
    async def update_plan(self, plan_id: int, **fields: object) -> None: ...

    # Schema
    async def get_schema_version(self) -> int: ...
    async def set_schema_version(self, version: int) -> None: ...

    # Lifecycle
    async def initialize(self) -> None: ...
    async def close(self) -> None: ...
