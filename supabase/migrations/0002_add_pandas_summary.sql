-- Add pandas_summary JSONB column to runs for raw data download on guardrail_failed
ALTER TABLE runs ADD COLUMN IF NOT EXISTS pandas_summary JSONB;
