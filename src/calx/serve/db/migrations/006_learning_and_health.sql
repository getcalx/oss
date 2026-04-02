-- Safety-net migration: ensures all Session 2-4 columns and objects exist.
-- Installs that ran TABLES_DDL directly have these columns already;
-- the migration runner catches duplicate-column errors as no-ops.

-- Backfill: 'unknown' is correct: existing corrections predate learning mode tracking
ALTER TABLE corrections ADD COLUMN learning_mode TEXT NOT NULL DEFAULT 'unknown';

-- Backfill: 1.0 / 'healthy' is correct: existing rules start healthy
ALTER TABLE rules ADD COLUMN learning_mode TEXT NOT NULL DEFAULT 'unknown';
ALTER TABLE rules ADD COLUMN health_score REAL NOT NULL DEFAULT 1.0;
ALTER TABLE rules ADD COLUMN health_status TEXT NOT NULL DEFAULT 'healthy';
ALTER TABLE rules ADD COLUMN last_validated_at TEXT;
ALTER TABLE rules ADD COLUMN compiled_at TEXT;
ALTER TABLE rules ADD COLUMN compiled_via TEXT;
ALTER TABLE rules ADD COLUMN compiled_from_mode TEXT;
ALTER TABLE rules ADD COLUMN recurrence_at_compilation INTEGER;
ALTER TABLE rules ADD COLUMN deactivation_reason TEXT;
ALTER TABLE rules ADD COLUMN role TEXT;

CREATE TABLE IF NOT EXISTS plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_description TEXT NOT NULL,
    chunks TEXT NOT NULL,
    dependency_edges TEXT NOT NULL,
    phase TEXT NOT NULL DEFAULT 'spec',
    spec_file TEXT,
    test_files TEXT,
    review_id INTEGER,
    current_wave INTEGER NOT NULL DEFAULT 1,
    wave_verification TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    FOREIGN KEY (review_id) REFERENCES foil_reviews(id)
);

CREATE INDEX IF NOT EXISTS idx_plans_status ON plans(status);
CREATE INDEX IF NOT EXISTS idx_rules_health_status ON rules(health_status);
CREATE INDEX IF NOT EXISTS idx_rules_learning_mode ON rules(learning_mode);

-- Schema version: 6
