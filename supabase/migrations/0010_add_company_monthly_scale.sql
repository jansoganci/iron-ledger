-- Item 5: revenue-scaled flux materiality.
-- Band lives on companies (server-side comparison reads by company_id).
-- NULL is intentional: existing rows and skip-the-question keep today's $50k/$10k fail-safe.
-- Do not put this on auth.users raw_user_meta_data.

ALTER TABLE companies
  ADD COLUMN IF NOT EXISTS monthly_revenue_band TEXT;

ALTER TABLE companies
  ADD CONSTRAINT companies_monthly_revenue_band_chk
  CHECK (
    monthly_revenue_band IS NULL
    OR monthly_revenue_band IN (
      'under_100k',
      '100k_250k',
      '250k_500k',
      '500k_plus'
    )
  );
