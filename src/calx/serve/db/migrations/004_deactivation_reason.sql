-- 004_deactivation_reason.sql
-- Add deactivation_reason column to rules table for architectural persistence of why a rule was deactivated.
ALTER TABLE rules ADD COLUMN deactivation_reason TEXT;
