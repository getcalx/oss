"""Database schema version and type mappings."""

SCHEMA_VERSION = 6

PRAGMA_WAL = "PRAGMA journal_mode=WAL"

# Type mapping for validate_schema(): Python annotation string -> SQLite affinity
PYTHON_TO_SQLITE_TYPE = {
    "str": "TEXT",
    "int": "INTEGER",
    "float": "REAL",
    "str | None": "TEXT",
    "int | None": "INTEGER",
    "float | None": "REAL",
}


def _get_dataclass_table_map() -> dict:
    """Lazy import to avoid circular dependency (schema -> engine -> schema)."""
    from calx.serve.db.engine import (
        BoardStateRow, CompilationEventRow, ContextRow,
        CorrectionRow, DecisionRow, FoilReviewRow,
        HandoffRow, MetricRow, PipelineRow, PlanRow, RuleRow, SessionRow,
    )
    return {
        CorrectionRow: "corrections",
        RuleRow: "rules",
        MetricRow: "metrics",
        PipelineRow: "pipeline",
        DecisionRow: "decisions",
        ContextRow: "context",
        SessionRow: "sessions",
        HandoffRow: "handoffs",
        BoardStateRow: "board_state",
        FoilReviewRow: "foil_reviews",
        CompilationEventRow: "compilation_events",
        PlanRow: "plans",
    }
