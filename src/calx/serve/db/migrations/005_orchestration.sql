-- Migration 005: Orchestration infrastructure
-- Adds plans table and role column on rules.

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

CREATE TRIGGER IF NOT EXISTS trg_plans_updated_at AFTER UPDATE ON plans FOR EACH ROW BEGIN UPDATE plans SET updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = NEW.id; END;

ALTER TABLE rules ADD COLUMN role TEXT;
