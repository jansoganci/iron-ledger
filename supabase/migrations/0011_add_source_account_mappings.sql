-- Persistent source-value → GL mappings for vendors and expense items.
-- Payroll and GL names are intentionally excluded (CHECK + application).
-- company_id is always server-resolved; RLS mirrors accounts/runs.

CREATE TABLE IF NOT EXISTS source_account_mappings (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id      UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  file_type       TEXT NOT NULL,
  source_pattern  TEXT NOT NULL,
  gl_account      TEXT NOT NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT source_account_mappings_unique
    UNIQUE (company_id, file_type, source_pattern),
  CONSTRAINT source_account_mappings_file_type_chk
    CHECK (
      file_type IN (
        'supplier_invoices',
        'contracts',
        'bank_statement',
        'processor_settlement'
      )
    ),
  CONSTRAINT source_account_mappings_pattern_chk
    CHECK (char_length(btrim(source_pattern)) > 0),
  CONSTRAINT source_account_mappings_gl_chk
    CHECK (char_length(btrim(gl_account)) > 0)
);

CREATE INDEX IF NOT EXISTS idx_source_account_mappings_company_type
  ON source_account_mappings (company_id, file_type);

ALTER TABLE source_account_mappings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS source_account_mappings_via_company ON source_account_mappings;
CREATE POLICY source_account_mappings_via_company ON source_account_mappings
  FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM companies c
      WHERE c.id = source_account_mappings.company_id
        AND c.owner_id = auth.uid()
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM companies c
      WHERE c.id = source_account_mappings.company_id
        AND c.owner_id = auth.uid()
    )
  );
