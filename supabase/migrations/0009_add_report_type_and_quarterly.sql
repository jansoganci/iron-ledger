-- Migration 0009: Add report_type and quarterly support
-- This promotes quarterly reports from stateless compute-on-demand to persisted artifacts.

-- 1. reports: add type + quarter coordinates
ALTER TABLE reports
  ADD COLUMN report_type TEXT NOT NULL DEFAULT 'monthly',
  ADD COLUMN quarter      SMALLINT NULL,         -- 1, 2, 3, 4
  ADD COLUMN year         SMALLINT NULL;          -- e.g. 2026

-- 2. reports: unique constraints (using partial indexes)
-- Monthly reports: unique per (company_id, report_type, period)
CREATE UNIQUE INDEX reports_monthly_unique
  ON reports (company_id, report_type, period)
  WHERE report_type = 'monthly';

-- Quarterly reports: unique per (company_id, report_type, year, quarter)
CREATE UNIQUE INDEX reports_quarterly_unique
  ON reports (company_id, report_type, year, quarter)
  WHERE report_type = 'quarterly';

-- 3. reports: add is_stale flag and quarterly_data JSONB for quarterly reports
ALTER TABLE reports
  ADD COLUMN is_stale BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN quarterly_data JSONB NULL;

-- 4. anomalies: add is_recurring flag
ALTER TABLE anomalies
  ADD COLUMN is_recurring BOOLEAN NOT NULL DEFAULT FALSE;

-- 5. backfill is_recurring from history
-- An anomaly is recurring if the same account was flagged (severity != 'low')
-- in at least 1 other period within the prior 6 months.
UPDATE anomalies a
SET is_recurring = TRUE
WHERE severity != 'low'
  AND EXISTS (
    SELECT 1 FROM anomalies b
    WHERE b.company_id = a.company_id
      AND b.account_id = a.account_id
      AND b.period     < a.period
      AND b.period     >= a.period - interval '6 months'
      AND b.severity   != 'low'
      AND b.id         != a.id
  );
