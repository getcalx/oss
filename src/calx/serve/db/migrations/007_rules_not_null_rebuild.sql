-- 007_rules_not_null_rebuild.sql
-- Rebuild rules table to enforce NOT NULL on health_score.
-- Some databases created via a legacy in-code DDL have health_score as nullable.
-- SQLite does not support ALTER COLUMN, so we rebuild the table.

CREATE TABLE rules_new (
    id TEXT PRIMARY KEY,
    rule_text TEXT NOT NULL,
    domain TEXT NOT NULL,
    surface TEXT,
    source_correction_id TEXT,
    learning_mode TEXT NOT NULL DEFAULT 'unknown',
    health_score REAL NOT NULL DEFAULT 1.0,
    health_status TEXT NOT NULL DEFAULT 'healthy',
    last_validated_at TEXT,
    compiled_at TEXT,
    compiled_via TEXT,
    compiled_from_mode TEXT,
    recurrence_at_compilation INTEGER,
    deactivation_reason TEXT,
    role TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    FOREIGN KEY (source_correction_id) REFERENCES corrections(id)
);

INSERT INTO rules_new
    SELECT id, rule_text, domain, surface, source_correction_id,
           COALESCE(learning_mode, 'unknown'),
           COALESCE(health_score, 1.0),
           COALESCE(health_status, 'healthy'),
           last_validated_at, compiled_at, compiled_via, compiled_from_mode,
           recurrence_at_compilation, deactivation_reason, role, active,
           created_at, updated_at
    FROM rules;

DROP TABLE rules;

ALTER TABLE rules_new RENAME TO rules;

CREATE INDEX IF NOT EXISTS idx_rules_domain ON rules(domain);
CREATE INDEX IF NOT EXISTS idx_rules_active ON rules(active);
CREATE INDEX IF NOT EXISTS idx_rules_health_status ON rules(health_status);
CREATE INDEX IF NOT EXISTS idx_rules_learning_mode ON rules(learning_mode);

CREATE TRIGGER IF NOT EXISTS trg_rules_updated_at
    AFTER UPDATE ON rules
    FOR EACH ROW
    BEGIN
        UPDATE rules SET updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
        WHERE id = NEW.id;
    END;

-- Schema version: 7
