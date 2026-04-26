-- Month Proof — Database Schema
-- Run against a Supabase PostgreSQL project.
-- Supabase Auth must be enabled (auth.users exists).
--
-- Tables: 7
--   companies, account_categories, accounts,
--   monthly_entries, anomalies, reports, runs
-- RLS is enabled on every company-owning table.
-- account_categories is a public lookup table (no RLS).

-- =====================================================================
-- 1. companies
-- =====================================================================
CREATE TABLE IF NOT EXISTS companies (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id   UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  name       TEXT NOT NULL,
  sector     TEXT,
  currency   TEXT DEFAULT 'USD',
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_companies_owner ON companies(owner_id);

-- =====================================================================
-- 2. account_categories  (public lookup — no RLS)
-- =====================================================================
CREATE TABLE IF NOT EXISTS account_categories (
  id   SERIAL PRIMARY KEY,
  name TEXT NOT NULL UNIQUE  -- REVENUE, COGS, OPEX, G&A, R&D, OTHER_INCOME
);

-- Insertion order determines SERIAL id. OTHER is id=7 — used by Parser as
-- the catch-all for low-confidence Haiku mappings. SKIP is NOT seeded here;
-- it is a frontend-only sentinel in MappingConfirmModal.
INSERT INTO account_categories (name) VALUES
  ('REVENUE'),       -- id=1
  ('COGS'),          -- id=2
  ('OPEX'),          -- id=3
  ('G&A'),           -- id=4
  ('R&D'),           -- id=5
  ('OTHER_INCOME'),  -- id=6
  ('OTHER')          -- id=7
ON CONFLICT (name) DO NOTHING;

-- =====================================================================
-- 3. accounts
-- =====================================================================
CREATE TABLE IF NOT EXISTS accounts (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id  UUID REFERENCES companies(id) ON DELETE CASCADE,
  category_id INT  REFERENCES account_categories(id),
  name        TEXT NOT NULL,
  code        TEXT,
  is_active   BOOLEAN DEFAULT TRUE,
  created_by  TEXT DEFAULT 'agent',
  created_at  TIMESTAMP DEFAULT NOW()
);

-- =====================================================================
-- 4. monthly_entries
-- =====================================================================
CREATE TABLE IF NOT EXISTS monthly_entries (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id    UUID REFERENCES companies(id) ON DELETE CASCADE,
  account_id    UUID REFERENCES accounts(id),
  period        DATE NOT NULL,  -- first day of month: 2026-02-01 = February 2026
  actual_amount DECIMAL(15,2),
  source_file   TEXT,
  agent_notes   TEXT,
  created_at    TIMESTAMP DEFAULT NOW(),
  CONSTRAINT unique_entry UNIQUE (company_id, account_id, period)
);

CREATE INDEX IF NOT EXISTS idx_monthly_entries_company_period
  ON monthly_entries(company_id, period);

-- =====================================================================
-- 5. anomalies
-- =====================================================================
CREATE TABLE IF NOT EXISTS anomalies (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id   UUID REFERENCES companies(id) ON DELETE CASCADE,
  account_id   UUID REFERENCES accounts(id),
  period       DATE NOT NULL,
  anomaly_type TEXT NOT NULL,  -- 'error' | 'warning' | 'anomaly'
  severity     TEXT NOT NULL,  -- 'low' | 'medium' | 'high'  (set by Python, not Claude)
  description  TEXT NOT NULL,
  variance_pct DECIMAL(8,2),
  status       TEXT DEFAULT 'open',
  created_at   TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_anomalies_company_period
  ON anomalies(company_id, period);

-- =====================================================================
-- 6. reports
-- =====================================================================
CREATE TABLE IF NOT EXISTS reports (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id    UUID REFERENCES companies(id) ON DELETE CASCADE,
  period        DATE NOT NULL,
  summary       TEXT NOT NULL,
  anomaly_count INT DEFAULT 0,
  error_count   INT DEFAULT 0,
  mail_sent     BOOLEAN DEFAULT FALSE,
  mail_sent_at  TIMESTAMP,
  created_at    TIMESTAMP DEFAULT NOW()
);

-- =====================================================================
-- 7. runs
-- =====================================================================
CREATE TABLE IF NOT EXISTS runs (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id    UUID REFERENCES companies(id) ON DELETE CASCADE,
  period        DATE NOT NULL,
  status        TEXT DEFAULT 'pending',
  -- pending → parsing → mapping → comparing → generating → complete → guardrail_failed
  step          INT DEFAULT 0,
  total_steps   INT DEFAULT 4,
  step_label    TEXT,
  progress_pct  INT DEFAULT 0,
  report_id     UUID REFERENCES reports(id),
  raw_data_url              TEXT,
  error_message             TEXT,
  low_confidence_columns    JSONB DEFAULT '[]'::jsonb,
  created_at                TIMESTAMP DEFAULT NOW(),
  updated_at                TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_runs_company_period ON runs(company_id, period);

-- =====================================================================
-- Row Level Security
-- =====================================================================
ALTER TABLE companies        ENABLE ROW LEVEL SECURITY;
ALTER TABLE accounts         ENABLE ROW LEVEL SECURITY;
ALTER TABLE monthly_entries  ENABLE ROW LEVEL SECURITY;
ALTER TABLE anomalies        ENABLE ROW LEVEL SECURITY;
ALTER TABLE reports          ENABLE ROW LEVEL SECURITY;
ALTER TABLE runs             ENABLE ROW LEVEL SECURITY;
-- account_categories: intentionally NO RLS (public lookup)

-- companies: direct ownership
DROP POLICY IF EXISTS company_owner ON companies;
CREATE POLICY company_owner ON companies
  FOR ALL
  USING  (owner_id = auth.uid())
  WITH CHECK (owner_id = auth.uid());

-- accounts / monthly_entries / anomalies / reports / runs: gated via owned company
DROP POLICY IF EXISTS accounts_via_company ON accounts;
CREATE POLICY accounts_via_company ON accounts
  FOR ALL USING (EXISTS (
    SELECT 1 FROM companies c
    WHERE c.id = accounts.company_id AND c.owner_id = auth.uid()
  ));

DROP POLICY IF EXISTS monthly_entries_via_company ON monthly_entries;
CREATE POLICY monthly_entries_via_company ON monthly_entries
  FOR ALL USING (EXISTS (
    SELECT 1 FROM companies c
    WHERE c.id = monthly_entries.company_id AND c.owner_id = auth.uid()
  ));

DROP POLICY IF EXISTS anomalies_via_company ON anomalies;
CREATE POLICY anomalies_via_company ON anomalies
  FOR ALL USING (EXISTS (
    SELECT 1 FROM companies c
    WHERE c.id = anomalies.company_id AND c.owner_id = auth.uid()
  ));

DROP POLICY IF EXISTS reports_via_company ON reports;
CREATE POLICY reports_via_company ON reports
  FOR ALL USING (EXISTS (
    SELECT 1 FROM companies c
    WHERE c.id = reports.company_id AND c.owner_id = auth.uid()
  ));

DROP POLICY IF EXISTS runs_via_company ON runs;
CREATE POLICY runs_via_company ON runs
  FOR ALL USING (EXISTS (
    SELECT 1 FROM companies c
    WHERE c.id = runs.company_id AND c.owner_id = auth.uid()
  ));

-- =====================================================================
-- Storage bucket RLS
-- Bucket `financial-uploads` must be created via Supabase Dashboard or API.
-- Uploads are scoped to the authenticated user's own folder:
--   financial-uploads/{auth.uid()}/{period}/{filename}
-- =====================================================================
DROP POLICY IF EXISTS user_owns_upload ON storage.objects;
CREATE POLICY user_owns_upload
  ON storage.objects
  FOR ALL
  USING (
    bucket_id = 'financial-uploads'
    AND (storage.foldername(name))[1] = auth.uid()::text
  );
