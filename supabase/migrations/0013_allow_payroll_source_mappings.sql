-- Remember payroll role → wage-account choices the same way vendor names
-- are remembered. The user confirms a role once. Later months reuse it
-- until the role is new or the saved wage account is gone from the GL.

ALTER TABLE source_account_mappings
  DROP CONSTRAINT IF EXISTS source_account_mappings_file_type_chk;

ALTER TABLE source_account_mappings
  ADD CONSTRAINT source_account_mappings_file_type_chk
  CHECK (
    file_type IN (
      'supplier_invoices',
      'contracts',
      'bank_statement',
      'processor_settlement',
      'payroll'
    )
  );
