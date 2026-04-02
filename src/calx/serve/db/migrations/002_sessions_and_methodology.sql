-- Migration 002: Sessions, handoffs, board state, foil reviews, compilation events
-- Also adds learning_mode and health columns to existing tables.
-- Version: 1 -> 2

-- Sessions: enforcement lifecycle
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    surface TEXT NOT NULL,
    surface_type TEXT NOT NULL,
    oriented INTEGER NOT NULL DEFAULT 0,
    token_estimate INTEGER NOT NULL DEFAULT 0,
    soft_cap INTEGER NOT NULL,
    ceiling INTEGER NOT NULL,
    tool_call_count INTEGER NOT NULL DEFAULT 0,
    server_fail_mode TEXT NOT NULL DEFAULT 'open',
    collapse_fail_mode TEXT NOT NULL DEFAULT 'closed',
    started_at TEXT NOT NULL,
    ended_at TEXT
);

-- Handoffs: session-end coordination documents
CREATE TABLE IF NOT EXISTS handoffs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    what_changed TEXT NOT NULL,
    what_others_need TEXT,
    decisions_deferred TEXT,
    next_priorities TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_handoffs_session ON handoffs(session_id);
CREATE INDEX IF NOT EXISTS idx_handoffs_created ON handoffs(created_at);

-- Board state: cross-agent coordination
CREATE TABLE IF NOT EXISTS board_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('blocked', 'in_progress', 'needs_review', 'done')),
    blocked_reason TEXT,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_board_state_status ON board_state(status);
CREATE INDEX IF NOT EXISTS idx_board_state_domain ON board_state(domain);

-- Foil reviews: adversarial cross-domain review records
CREATE TABLE IF NOT EXISTS foil_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    spec_reference TEXT NOT NULL,
    reviewer_domain TEXT NOT NULL,
    verdict TEXT NOT NULL CHECK(verdict IN ('approve', 'revise')),
    findings TEXT,
    round INTEGER NOT NULL DEFAULT 1,
    session_id TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_foil_reviews_spec ON foil_reviews(spec_reference);

-- Compilation events: process -> architectural transition dataset
CREATE TABLE IF NOT EXISTS compilation_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id TEXT NOT NULL,
    source_correction_id TEXT,
    rule_text TEXT NOT NULL,
    learning_mode_before TEXT NOT NULL,
    mechanism_type TEXT NOT NULL CHECK(mechanism_type IN ('code_change', 'config_change', 'hook_addition', 'architecture_change')),
    mechanism_description TEXT NOT NULL,
    mechanism_reference TEXT,
    recurrence_count_at_compilation INTEGER NOT NULL,
    rule_age_days INTEGER NOT NULL,
    correction_chain_length INTEGER NOT NULL,
    post_compilation_recurrence INTEGER NOT NULL DEFAULT 0,
    verified_at TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    FOREIGN KEY (rule_id) REFERENCES rules(id),
    FOREIGN KEY (source_correction_id) REFERENCES corrections(id)
);

CREATE INDEX IF NOT EXISTS idx_compilation_events_rule ON compilation_events(rule_id);

-- Add learning_mode to corrections
ALTER TABLE corrections ADD COLUMN learning_mode TEXT NOT NULL DEFAULT 'unknown';

-- Add methodology columns to rules
ALTER TABLE rules ADD COLUMN learning_mode TEXT NOT NULL DEFAULT 'unknown';
ALTER TABLE rules ADD COLUMN health_score REAL NOT NULL DEFAULT 1.0;
ALTER TABLE rules ADD COLUMN health_status TEXT NOT NULL DEFAULT 'healthy';
ALTER TABLE rules ADD COLUMN last_validated_at TEXT;
ALTER TABLE rules ADD COLUMN compiled_at TEXT;
ALTER TABLE rules ADD COLUMN compiled_via TEXT;
ALTER TABLE rules ADD COLUMN compiled_from_mode TEXT;
ALTER TABLE rules ADD COLUMN recurrence_at_compilation INTEGER;
