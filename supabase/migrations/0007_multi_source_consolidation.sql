-- 0007_multi_source_consolidation.sql
-- Additive columns for multi-file consolidation + cross-source reconciliation.
-- All columns nullable — existing rows are unaffected.

ALTER TABLE monthly_entries
    ADD COLUMN IF NOT EXISTS source_breakdown JSONB;
-- Shape: [{"source_file": "payroll.xlsx", "source_column": "Gross",
--          "amount": 47200.00, "row_count": 3}, ...]

ALTER TABLE reports
    ADD COLUMN IF NOT EXISTS reconciliations JSONB;
-- Shape: [{"account": "Payroll", "sources": [...], "delta": 700.00,
--          "severity": "high", "classification": "categorical_misclassification",
--          "narrative": "...", "suggested_action": "..."}, ...]

ALTER TABLE runs
    ADD COLUMN IF NOT EXISTS file_count INT NOT NULL DEFAULT 1;
