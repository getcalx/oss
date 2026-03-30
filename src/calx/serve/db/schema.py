"""Database schema DDL and initialization."""
from __future__ import annotations
SCHEMA_VERSION = 2

PRAGMA_WAL = "PRAGMA journal_mode=WAL"

TABLES_DDL = """
-- Corrections: cross-surface behavioral capture
CREATE TABLE IF NOT EXISTS corrections (
    id TEXT PRIMARY KEY,
    uuid TEXT UNIQUE NOT NULL,
    correction TEXT NOT NULL,
    domain TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'medium',
    confidence TEXT NOT NULL DEFAULT 'medium',
    surface TEXT NOT NULL,
    task_context TEXT,
    briefing_state TEXT,
    keywords TEXT,
    recurrence_of TEXT,
    root_correction_id TEXT,
    recurrence_count INTEGER NOT NULL DEFAULT 1,
    promoted INTEGER NOT NULL DEFAULT 0,
    quarantined INTEGER NOT NULL DEFAULT 0,
    quarantine_reason TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    FOREIGN KEY (recurrence_of) REFERENCES corrections(id),
    FOREIGN KEY (root_correction_id) REFERENCES corrections(id)
);

CREATE INDEX IF NOT EXISTS idx_corrections_domain ON corrections(domain);
CREATE INDEX IF NOT EXISTS idx_corrections_surface ON corrections(surface);
CREATE INDEX IF NOT EXISTS idx_corrections_recurrence ON corrections(recurrence_of);
CREATE INDEX IF NOT EXISTS idx_corrections_root ON corrections(root_correction_id);
CREATE INDEX IF NOT EXISTS idx_corrections_created ON corrections(created_at);

-- Rules: promoted corrections (surface column for briefing filtering)
CREATE TABLE IF NOT EXISTS rules (
    id TEXT PRIMARY KEY,
    rule_text TEXT NOT NULL,
    domain TEXT NOT NULL,
    surface TEXT,
    source_correction_id TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    health_score REAL DEFAULT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    FOREIGN KEY (source_correction_id) REFERENCES corrections(id)
);

CREATE INDEX IF NOT EXISTS idx_rules_domain ON rules(domain);
CREATE INDEX IF NOT EXISTS idx_rules_active ON rules(active);

-- Metrics: traction time series
CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    value REAL NOT NULL,
    source TEXT,
    metadata TEXT,
    measured_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_metrics_name ON metrics(name);
CREATE INDEX IF NOT EXISTS idx_metrics_measured ON metrics(measured_at);

-- Pipeline: investor pipeline
CREATE TABLE IF NOT EXISTS pipeline (
    investor TEXT PRIMARY KEY,
    status TEXT,
    gate TEXT,
    notes TEXT,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- Decisions: append-only decision log
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    decision TEXT NOT NULL,
    context TEXT,
    surface TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_decisions_created ON decisions(created_at);

-- Context: hot context key-value store
CREATE TABLE IF NOT EXISTS context (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    category TEXT,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- Telemetry: every MCP interaction
CREATE TABLE IF NOT EXISTS telemetry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    tool_or_resource TEXT NOT NULL,
    surface TEXT,
    params TEXT,
    response_status TEXT,
    latency_ms REAL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_telemetry_type ON telemetry(event_type);
CREATE INDEX IF NOT EXISTS idx_telemetry_created ON telemetry(created_at);

-- Triggers: auto-update updated_at
CREATE TRIGGER IF NOT EXISTS trg_corrections_updated_at
    AFTER UPDATE ON corrections
    FOR EACH ROW
    BEGIN
        UPDATE corrections SET updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
        WHERE id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS trg_rules_updated_at
    AFTER UPDATE ON rules
    FOR EACH ROW
    BEGIN
        UPDATE rules SET updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
        WHERE id = NEW.id;
    END;

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
"""
