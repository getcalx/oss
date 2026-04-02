-- 003_methodology.sql
-- Ensure indexes exist for health queries (may already exist from initial schema)
CREATE INDEX IF NOT EXISTS idx_rules_health_status ON rules(health_status);
CREATE INDEX IF NOT EXISTS idx_rules_learning_mode ON rules(learning_mode);
CREATE INDEX IF NOT EXISTS idx_compilation_events_verified ON compilation_events(verified_at);
CREATE INDEX IF NOT EXISTS idx_compilation_events_rule_id ON compilation_events(rule_id);
