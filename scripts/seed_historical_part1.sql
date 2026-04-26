-- =============================================================================
-- Month Proof — Sentinel Secure Historical Seed (PART 1 of 4)
-- =============================================================================
-- company_id : 7696819b-a525-4bd7-85e9-baecc635465a
-- Periods    : 2024-10-01 through 2025-01-01  (4 months)
-- Accounts   : 21  (REVENUE:5, COGS:3, OPEX:5, G&A:5, R&D:3)
-- Entries    : 21 × 4 = 84 monthly_entries rows
-- Reports    : 4   |   Runs: 4
--
-- Run Parts 2–4 after this succeeds.
-- Safe to re-run: ON CONFLICT clauses guard every INSERT.
--
-- Account UUIDs are hardcoded (GL code embedded in last 6 digits) so they
-- stay stable across all four parts and across re-runs.
-- =============================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 1: Accounts  (one-time; Parts 2–4 reference these same UUIDs)
-- ─────────────────────────────────────────────────────────────────────────────
INSERT INTO accounts (id, company_id, category_id, name, code, created_by)
VALUES
  -- REVENUE  (category_id = 1)
  ('00000000-0000-0000-0000-000000004000', '7696819b-a525-4bd7-85e9-baecc635465a', 1, 'SaaS Subscriptions',             '4000', 'historical_seed'),
  ('00000000-0000-0000-0000-000000004010', '7696819b-a525-4bd7-85e9-baecc635465a', 1, 'Professional Services',          '4010', 'historical_seed'),
  ('00000000-0000-0000-0000-000000004020', '7696819b-a525-4bd7-85e9-baecc635465a', 1, 'Implementation Fees',            '4020', 'historical_seed'),
  ('00000000-0000-0000-0000-000000004030', '7696819b-a525-4bd7-85e9-baecc635465a', 1, 'Training Revenue',               '4030', 'historical_seed'),
  ('00000000-0000-0000-0000-000000004040', '7696819b-a525-4bd7-85e9-baecc635465a', 1, 'Maintenance Contracts',          '4040', 'historical_seed'),
  -- COGS  (category_id = 2)
  ('00000000-0000-0000-0000-000000005000', '7696819b-a525-4bd7-85e9-baecc635465a', 2, 'Cloud Infrastructure',           '5000', 'historical_seed'),
  ('00000000-0000-0000-0000-000000005010', '7696819b-a525-4bd7-85e9-baecc635465a', 2, 'Support Staff Salaries',         '5010', 'historical_seed'),
  ('00000000-0000-0000-0000-000000005020', '7696819b-a525-4bd7-85e9-baecc635465a', 2, 'Third-Party Licenses',           '5020', 'historical_seed'),
  -- OPEX  (category_id = 3)
  ('00000000-0000-0000-0000-000000006000', '7696819b-a525-4bd7-85e9-baecc635465a', 3, 'Sales Salaries & Commission',    '6000', 'historical_seed'),
  ('00000000-0000-0000-0000-000000006010', '7696819b-a525-4bd7-85e9-baecc635465a', 3, 'Marketing & Advertising',        '6010', 'historical_seed'),
  ('00000000-0000-0000-0000-000000006020', '7696819b-a525-4bd7-85e9-baecc635465a', 3, 'Travel & Entertainment',         '6020', 'historical_seed'),
  ('00000000-0000-0000-0000-000000006030', '7696819b-a525-4bd7-85e9-baecc635465a', 3, 'Office Rent & Utilities',        '6030', 'historical_seed'),
  ('00000000-0000-0000-0000-000000006040', '7696819b-a525-4bd7-85e9-baecc635465a', 3, 'Software Tools & Subscriptions', '6040', 'historical_seed'),
  -- G&A  (category_id = 4)
  ('00000000-0000-0000-0000-000000007000', '7696819b-a525-4bd7-85e9-baecc635465a', 4, 'Executive Salaries',             '7000', 'historical_seed'),
  ('00000000-0000-0000-0000-000000007010', '7696819b-a525-4bd7-85e9-baecc635465a', 4, 'Admin Staff Salaries',           '7010', 'historical_seed'),
  ('00000000-0000-0000-0000-000000007020', '7696819b-a525-4bd7-85e9-baecc635465a', 4, 'Legal & Professional Fees',      '7020', 'historical_seed'),
  ('00000000-0000-0000-0000-000000007030', '7696819b-a525-4bd7-85e9-baecc635465a', 4, 'Insurance',                      '7030', 'historical_seed'),
  ('00000000-0000-0000-0000-000000007040', '7696819b-a525-4bd7-85e9-baecc635465a', 4, 'Office Supplies & Misc',         '7040', 'historical_seed'),
  -- R&D  (category_id = 5)
  ('00000000-0000-0000-0000-000000008000', '7696819b-a525-4bd7-85e9-baecc635465a', 5, 'Engineering Salaries',           '8000', 'historical_seed'),
  ('00000000-0000-0000-0000-000000008010', '7696819b-a525-4bd7-85e9-baecc635465a', 5, 'Development Tools & Services',   '8010', 'historical_seed'),
  ('00000000-0000-0000-0000-000000008020', '7696819b-a525-4bd7-85e9-baecc635465a', 5, 'Patent & IP Costs',              '8020', 'historical_seed')
ON CONFLICT (id) DO NOTHING;


-- ─────────────────────────────────────────────────────────────────────────────
-- MONTH 1 : October 2024
-- Revenue $285,000 | Costs $260,000 | Profit $25,000
-- Baseline month. No anomalies.
-- ─────────────────────────────────────────────────────────────────────────────
WITH
  rep AS (
    INSERT INTO reports (id, company_id, period, summary, anomaly_count, error_count)
    VALUES (
      gen_random_uuid(),
      '7696819b-a525-4bd7-85e9-baecc635465a',
      '2024-10-01',
      'Sentinel Secure closed October with $285K in revenue and a $25K operating profit. SaaS subscription growth of 3.5% month-over-month reflects continued new logo acquisition. Operating costs were on-plan at $260K with no unusual line items.',
      0, 0
    )
    RETURNING id, company_id, period
  ),
  run AS (
    INSERT INTO runs (id, company_id, period, status, step, total_steps, progress_pct, opus_status, report_id)
    SELECT gen_random_uuid(), company_id, period, 'complete', 4, 4, 100, 'done', id
    FROM rep
  )
INSERT INTO monthly_entries (id, company_id, account_id, period, actual_amount, source_file)
SELECT gen_random_uuid(), '7696819b-a525-4bd7-85e9-baecc635465a', e.account_id, '2024-10-01', e.amount, 'historical_seed'
FROM (VALUES
  -- REVENUE  (total: 285,000)
  ('00000000-0000-0000-0000-000000004000'::uuid,  199500.00),  -- SaaS Subscriptions
  ('00000000-0000-0000-0000-000000004010'::uuid,   71250.00),  -- Professional Services
  ('00000000-0000-0000-0000-000000004020'::uuid,    8550.00),  -- Implementation Fees
  ('00000000-0000-0000-0000-000000004030'::uuid,    4275.00),  -- Training Revenue
  ('00000000-0000-0000-0000-000000004040'::uuid,    1425.00),  -- Maintenance Contracts
  -- COGS  (total: 72,000)
  ('00000000-0000-0000-0000-000000005000'::uuid,   18000.00),  -- Cloud Infrastructure
  ('00000000-0000-0000-0000-000000005010'::uuid,   42000.00),  -- Support Staff Salaries
  ('00000000-0000-0000-0000-000000005020'::uuid,   12000.00),  -- Third-Party Licenses
  -- OPEX  (total: 65,000)
  ('00000000-0000-0000-0000-000000006000'::uuid,   32000.00),  -- Sales Salaries & Commission
  ('00000000-0000-0000-0000-000000006010'::uuid,   15000.00),  -- Marketing & Advertising
  ('00000000-0000-0000-0000-000000006020'::uuid,    4500.00),  -- Travel & Entertainment
  ('00000000-0000-0000-0000-000000006030'::uuid,    8000.00),  -- Office Rent & Utilities
  ('00000000-0000-0000-0000-000000006040'::uuid,    5500.00),  -- Software Tools & Subscriptions
  -- G&A  (total: 49,000)
  ('00000000-0000-0000-0000-000000007000'::uuid,   28000.00),  -- Executive Salaries
  ('00000000-0000-0000-0000-000000007010'::uuid,   14000.00),  -- Admin Staff Salaries
  ('00000000-0000-0000-0000-000000007020'::uuid,    3500.00),  -- Legal & Professional Fees
  ('00000000-0000-0000-0000-000000007030'::uuid,    2200.00),  -- Insurance
  ('00000000-0000-0000-0000-000000007040'::uuid,    1300.00),  -- Office Supplies & Misc
  -- R&D  (total: 74,000)
  ('00000000-0000-0000-0000-000000008000'::uuid,   60000.00),  -- Engineering Salaries
  ('00000000-0000-0000-0000-000000008010'::uuid,    8000.00),  -- Development Tools & Services
  ('00000000-0000-0000-0000-000000008020'::uuid,    6000.00)   -- Patent & IP Costs
) AS e(account_id, amount)
ON CONFLICT ON CONSTRAINT unique_entry DO NOTHING;


-- ─────────────────────────────────────────────────────────────────────────────
-- MONTH 2 : November 2024
-- Revenue $295,000 | Costs $265,000 | Profit $30,000
-- Steady MoM growth. No anomalies.
-- ─────────────────────────────────────────────────────────────────────────────
WITH
  rep AS (
    INSERT INTO reports (id, company_id, period, summary, anomaly_count, error_count)
    VALUES (
      gen_random_uuid(),
      '7696819b-a525-4bd7-85e9-baecc635465a',
      '2024-11-01',
      'November delivered $295K in revenue, a $10K improvement over October, with SaaS subscriptions growing 3.5% to $206.5K. Costs increased modestly to $265K, maintaining healthy unit economics. Net income of $30K marks the second consecutive month of profitable operations.',
      0, 0
    )
    RETURNING id, company_id, period
  ),
  run AS (
    INSERT INTO runs (id, company_id, period, status, step, total_steps, progress_pct, opus_status, report_id)
    SELECT gen_random_uuid(), company_id, period, 'complete', 4, 4, 100, 'done', id
    FROM rep
  )
INSERT INTO monthly_entries (id, company_id, account_id, period, actual_amount, source_file)
SELECT gen_random_uuid(), '7696819b-a525-4bd7-85e9-baecc635465a', e.account_id, '2024-11-01', e.amount, 'historical_seed'
FROM (VALUES
  -- REVENUE  (total: 295,000)
  ('00000000-0000-0000-0000-000000004000'::uuid,  206500.00),  -- SaaS Subscriptions
  ('00000000-0000-0000-0000-000000004010'::uuid,   73750.00),  -- Professional Services
  ('00000000-0000-0000-0000-000000004020'::uuid,    8850.00),  -- Implementation Fees
  ('00000000-0000-0000-0000-000000004030'::uuid,    4425.00),  -- Training Revenue
  ('00000000-0000-0000-0000-000000004040'::uuid,    1475.00),  -- Maintenance Contracts
  -- COGS  (total: 73,500)
  ('00000000-0000-0000-0000-000000005000'::uuid,   18500.00),  -- Cloud Infrastructure
  ('00000000-0000-0000-0000-000000005010'::uuid,   43000.00),  -- Support Staff Salaries
  ('00000000-0000-0000-0000-000000005020'::uuid,   12000.00),  -- Third-Party Licenses
  -- OPEX  (total: 66,500)
  ('00000000-0000-0000-0000-000000006000'::uuid,   33000.00),  -- Sales Salaries & Commission
  ('00000000-0000-0000-0000-000000006010'::uuid,   15500.00),  -- Marketing & Advertising
  ('00000000-0000-0000-0000-000000006020'::uuid,    4000.00),  -- Travel & Entertainment
  ('00000000-0000-0000-0000-000000006030'::uuid,    8000.00),  -- Office Rent & Utilities
  ('00000000-0000-0000-0000-000000006040'::uuid,    6000.00),  -- Software Tools & Subscriptions
  -- G&A  (total: 50,000)
  ('00000000-0000-0000-0000-000000007000'::uuid,   28500.00),  -- Executive Salaries
  ('00000000-0000-0000-0000-000000007010'::uuid,   14500.00),  -- Admin Staff Salaries
  ('00000000-0000-0000-0000-000000007020'::uuid,    3500.00),  -- Legal & Professional Fees
  ('00000000-0000-0000-0000-000000007030'::uuid,    2200.00),  -- Insurance
  ('00000000-0000-0000-0000-000000007040'::uuid,    1300.00),  -- Office Supplies & Misc
  -- R&D  (total: 75,000)
  ('00000000-0000-0000-0000-000000008000'::uuid,   61500.00),  -- Engineering Salaries
  ('00000000-0000-0000-0000-000000008010'::uuid,    7500.00),  -- Development Tools & Services
  ('00000000-0000-0000-0000-000000008020'::uuid,    6000.00)   -- Patent & IP Costs
) AS e(account_id, amount)
ON CONFLICT ON CONSTRAINT unique_entry DO NOTHING;


-- ─────────────────────────────────────────────────────────────────────────────
-- MONTH 3 : December 2024
-- Revenue $310,000 | Costs $290,000 | Profit $20,000
-- Holiday bonuses in G&A (Executive +$14K, Admin +$5K) and R&D compress margin.
-- ─────────────────────────────────────────────────────────────────────────────
WITH
  rep AS (
    INSERT INTO reports (id, company_id, period, summary, anomaly_count, error_count)
    VALUES (
      gen_random_uuid(),
      '7696819b-a525-4bd7-85e9-baecc635465a',
      '2024-12-01',
      'December revenue reached a new high of $310K on strong year-end contract signings. Operating costs of $290K were elevated by seasonal factors: executive year-end bonuses added $14K above the October baseline and engineering bonuses added $4K, compressing net income to $20K despite record revenue.',
      0, 0
    )
    RETURNING id, company_id, period
  ),
  run AS (
    INSERT INTO runs (id, company_id, period, status, step, total_steps, progress_pct, opus_status, report_id)
    SELECT gen_random_uuid(), company_id, period, 'complete', 4, 4, 100, 'done', id
    FROM rep
  )
INSERT INTO monthly_entries (id, company_id, account_id, period, actual_amount, source_file)
SELECT gen_random_uuid(), '7696819b-a525-4bd7-85e9-baecc635465a', e.account_id, '2024-12-01', e.amount, 'historical_seed'
FROM (VALUES
  -- REVENUE  (total: 310,000)
  ('00000000-0000-0000-0000-000000004000'::uuid,  217000.00),  -- SaaS Subscriptions
  ('00000000-0000-0000-0000-000000004010'::uuid,   77500.00),  -- Professional Services
  ('00000000-0000-0000-0000-000000004020'::uuid,    9300.00),  -- Implementation Fees
  ('00000000-0000-0000-0000-000000004030'::uuid,    4650.00),  -- Training Revenue
  ('00000000-0000-0000-0000-000000004040'::uuid,    1550.00),  -- Maintenance Contracts
  -- COGS  (total: 75,000)
  ('00000000-0000-0000-0000-000000005000'::uuid,   19000.00),  -- Cloud Infrastructure
  ('00000000-0000-0000-0000-000000005010'::uuid,   44000.00),  -- Support Staff Salaries
  ('00000000-0000-0000-0000-000000005020'::uuid,   12000.00),  -- Third-Party Licenses
  -- OPEX  (total: 69,000)
  ('00000000-0000-0000-0000-000000006000'::uuid,   34000.00),  -- Sales Salaries & Commission
  ('00000000-0000-0000-0000-000000006010'::uuid,   16000.00),  -- Marketing & Advertising
  ('00000000-0000-0000-0000-000000006020'::uuid,    5500.00),  -- Travel & Entertainment (holiday parties)
  ('00000000-0000-0000-0000-000000006030'::uuid,    8000.00),  -- Office Rent & Utilities
  ('00000000-0000-0000-0000-000000006040'::uuid,    5500.00),  -- Software Tools & Subscriptions
  -- G&A  (total: 71,000) ← holiday bonuses inflating this line vs Oct/Nov baseline
  ('00000000-0000-0000-0000-000000007000'::uuid,   42000.00),  -- Executive Salaries  (+$14K bonus vs Oct)
  ('00000000-0000-0000-0000-000000007010'::uuid,   19500.00),  -- Admin Staff Salaries (+$5K bonus vs Oct)
  ('00000000-0000-0000-0000-000000007020'::uuid,    4000.00),  -- Legal & Professional Fees
  ('00000000-0000-0000-0000-000000007030'::uuid,    2200.00),  -- Insurance
  ('00000000-0000-0000-0000-000000007040'::uuid,    3300.00),  -- Office Supplies & Misc (gifts, parties)
  -- R&D  (total: 75,000) ← engineer bonuses bump this +$4K vs Nov
  ('00000000-0000-0000-0000-000000008000'::uuid,   66000.00),  -- Engineering Salaries (incl. year-end bonuses)
  ('00000000-0000-0000-0000-000000008010'::uuid,    7500.00),  -- Development Tools & Services
  ('00000000-0000-0000-0000-000000008020'::uuid,    1500.00)   -- Patent & IP Costs
) AS e(account_id, amount)
ON CONFLICT ON CONSTRAINT unique_entry DO NOTHING;


-- ─────────────────────────────────────────────────────────────────────────────
-- MONTH 4 : January 2025
-- Revenue $320,000 | Costs $275,000 | Profit $45,000
-- Strong new-year start. Annual contracts activate. Bonuses roll off.
-- ─────────────────────────────────────────────────────────────────────────────
WITH
  rep AS (
    INSERT INTO reports (id, company_id, period, summary, anomaly_count, error_count)
    VALUES (
      gen_random_uuid(),
      '7696819b-a525-4bd7-85e9-baecc635465a',
      '2025-01-01',
      'January 2025 opened with $320K in revenue as new annual SaaS contracts activated and professional services engagements began. Costs fell to $275K as December bonuses rolled off, producing a $45K net income — the best single month in company history and a strong foundation for Q1.',
      0, 0
    )
    RETURNING id, company_id, period
  ),
  run AS (
    INSERT INTO runs (id, company_id, period, status, step, total_steps, progress_pct, opus_status, report_id)
    SELECT gen_random_uuid(), company_id, period, 'complete', 4, 4, 100, 'done', id
    FROM rep
  )
INSERT INTO monthly_entries (id, company_id, account_id, period, actual_amount, source_file)
SELECT gen_random_uuid(), '7696819b-a525-4bd7-85e9-baecc635465a', e.account_id, '2025-01-01', e.amount, 'historical_seed'
FROM (VALUES
  -- REVENUE  (total: 320,000)
  ('00000000-0000-0000-0000-000000004000'::uuid,  224000.00),  -- SaaS Subscriptions
  ('00000000-0000-0000-0000-000000004010'::uuid,   80000.00),  -- Professional Services
  ('00000000-0000-0000-0000-000000004020'::uuid,    9600.00),  -- Implementation Fees
  ('00000000-0000-0000-0000-000000004030'::uuid,    4800.00),  -- Training Revenue
  ('00000000-0000-0000-0000-000000004040'::uuid,    1600.00),  -- Maintenance Contracts
  -- COGS  (total: 76,000)
  ('00000000-0000-0000-0000-000000005000'::uuid,   19500.00),  -- Cloud Infrastructure
  ('00000000-0000-0000-0000-000000005010'::uuid,   45000.00),  -- Support Staff Salaries
  ('00000000-0000-0000-0000-000000005020'::uuid,   11500.00),  -- Third-Party Licenses
  -- OPEX  (total: 67,000)
  ('00000000-0000-0000-0000-000000006000'::uuid,   34500.00),  -- Sales Salaries & Commission
  ('00000000-0000-0000-0000-000000006010'::uuid,   14000.00),  -- Marketing & Advertising (post-holiday dip)
  ('00000000-0000-0000-0000-000000006020'::uuid,    3500.00),  -- Travel & Entertainment
  ('00000000-0000-0000-0000-000000006030'::uuid,    8000.00),  -- Office Rent & Utilities
  ('00000000-0000-0000-0000-000000006040'::uuid,    7000.00),  -- Software Tools & Subscriptions (new-year budget)
  -- G&A  (total: 51,000) ← normalized post-December
  ('00000000-0000-0000-0000-000000007000'::uuid,   29000.00),  -- Executive Salaries (normal rate, no bonus)
  ('00000000-0000-0000-0000-000000007010'::uuid,   14500.00),  -- Admin Staff Salaries
  ('00000000-0000-0000-0000-000000007020'::uuid,    3500.00),  -- Legal & Professional Fees
  ('00000000-0000-0000-0000-000000007030'::uuid,    2200.00),  -- Insurance
  ('00000000-0000-0000-0000-000000007040'::uuid,    1800.00),  -- Office Supplies & Misc
  -- R&D  (total: 81,000) ← Jan salary raises + new patent filing
  ('00000000-0000-0000-0000-000000008000'::uuid,   63000.00),  -- Engineering Salaries (annual raise applied)
  ('00000000-0000-0000-0000-000000008010'::uuid,    8000.00),  -- Development Tools & Services
  ('00000000-0000-0000-0000-000000008020'::uuid,   10000.00)   -- Patent & IP Costs (new filing Jan)
) AS e(account_id, amount)
ON CONFLICT ON CONSTRAINT unique_entry DO NOTHING;


-- ─────────────────────────────────────────────────────────────────────────────
-- PART 1 VALIDATION
-- Run these after executing Part 1 to confirm correctness before Part 2.
-- ─────────────────────────────────────────────────────────────────────────────

-- 1. Confirm 21 accounts exist
-- SELECT COUNT(*) FROM accounts WHERE company_id = '7696819b-a525-4bd7-85e9-baecc635465a';
-- Expected: 21

-- 2. Confirm 84 monthly_entries (21 accounts × 4 months)
-- SELECT COUNT(*) FROM monthly_entries
-- WHERE company_id = '7696819b-a525-4bd7-85e9-baecc635465a'
--   AND source_file = 'historical_seed';
-- Expected: 84

-- 3. Confirm 4 runs each linked to a report
-- SELECT r.period, r.status, r.opus_status, r.progress_pct,
--        CASE WHEN r.report_id IS NOT NULL THEN 'linked' ELSE 'MISSING' END AS report_link
-- FROM runs r
-- WHERE r.company_id = '7696819b-a525-4bd7-85e9-baecc635465a'
-- ORDER BY r.period;
-- Expected: 4 rows, all status='complete', opus_status='done', progress_pct=100, report_link='linked'

-- 4. Confirm per-month revenue totals
-- SELECT period, SUM(actual_amount) AS total_revenue
-- FROM monthly_entries
-- WHERE company_id = '7696819b-a525-4bd7-85e9-baecc635465a'
--   AND account_id IN (
--     '00000000-0000-0000-0000-000000004000',
--     '00000000-0000-0000-0000-000000004010',
--     '00000000-0000-0000-0000-000000004020',
--     '00000000-0000-0000-0000-000000004030',
--     '00000000-0000-0000-0000-000000004040'
--   )
-- GROUP BY period ORDER BY period;
-- Expected: 2024-10-01→285000 | 2024-11-01→295000 | 2024-12-01→310000 | 2025-01-01→320000


-- =============================================================================
-- PART 2 OF 4
-- Periods : 2025-02-01 through 2025-05-01  (4 months)
-- Entries : 21 × 4 = 84 monthly_entries rows
-- Reports : 4   |   Runs: 4
-- Anomalies in scope:
--   2025-04 : Legal & Professional Fees $43K penalty (AWS outage)  anomaly_count=1
--   2025-05 : Engineering Salaries +$65K (3 hires) + Executive +$30K (signing)  anomaly_count=2
-- =============================================================================


-- ─────────────────────────────────────────────────────────────────────────────
-- MONTH 5 : February 2025
-- Revenue $335,000 | Costs $310,000 | Profit $25,000
-- Trade show season: Marketing +$11K and Travel +$8K above January baseline.
-- ─────────────────────────────────────────────────────────────────────────────
WITH
  rep AS (
    INSERT INTO reports (id, company_id, period, summary, anomaly_count, error_count)
    VALUES (
      gen_random_uuid(),
      '7696819b-a525-4bd7-85e9-baecc635465a',
      '2025-02-01',
      'February revenue grew to $335K, a 4.7% increase over January, as SaaS subscriptions crossed $234K. Costs rose to $310K due to trade show season: marketing spend increased by $11K for RSA Conference sponsorship and travel climbed $8K for the field sales team. Net income of $25K reflects planned investment in pipeline generation.',
      0, 0
    )
    RETURNING id, company_id, period
  ),
  run AS (
    INSERT INTO runs (id, company_id, period, status, step, total_steps, progress_pct, opus_status, report_id)
    SELECT gen_random_uuid(), company_id, period, 'complete', 4, 4, 100, 'done', id
    FROM rep
  )
INSERT INTO monthly_entries (id, company_id, account_id, period, actual_amount, source_file)
SELECT gen_random_uuid(), '7696819b-a525-4bd7-85e9-baecc635465a', e.account_id, '2025-02-01', e.amount, 'historical_seed'
FROM (VALUES
  -- REVENUE  (total: 335,000)
  ('00000000-0000-0000-0000-000000004000'::uuid,  234500.00),  -- SaaS Subscriptions
  ('00000000-0000-0000-0000-000000004010'::uuid,   83750.00),  -- Professional Services
  ('00000000-0000-0000-0000-000000004020'::uuid,   10050.00),  -- Implementation Fees
  ('00000000-0000-0000-0000-000000004030'::uuid,    5025.00),  -- Training Revenue
  ('00000000-0000-0000-0000-000000004040'::uuid,    1675.00),  -- Maintenance Contracts
  -- COGS  (total: 79,000)
  ('00000000-0000-0000-0000-000000005000'::uuid,   20000.00),  -- Cloud Infrastructure
  ('00000000-0000-0000-0000-000000005010'::uuid,   47000.00),  -- Support Staff Salaries
  ('00000000-0000-0000-0000-000000005020'::uuid,   12000.00),  -- Third-Party Licenses
  -- OPEX  (total: 87,000) ← trade show spike
  ('00000000-0000-0000-0000-000000006000'::uuid,   35500.00),  -- Sales Salaries & Commission
  ('00000000-0000-0000-0000-000000006010'::uuid,   25000.00),  -- Marketing & Advertising (+$11K RSA Conference)
  ('00000000-0000-0000-0000-000000006020'::uuid,   11500.00),  -- Travel & Entertainment  (+$8K field sales)
  ('00000000-0000-0000-0000-000000006030'::uuid,    8000.00),  -- Office Rent & Utilities
  ('00000000-0000-0000-0000-000000006040'::uuid,    7000.00),  -- Software Tools & Subscriptions
  -- G&A  (total: 52,000)
  ('00000000-0000-0000-0000-000000007000'::uuid,   29500.00),  -- Executive Salaries
  ('00000000-0000-0000-0000-000000007010'::uuid,   14500.00),  -- Admin Staff Salaries
  ('00000000-0000-0000-0000-000000007020'::uuid,    3500.00),  -- Legal & Professional Fees
  ('00000000-0000-0000-0000-000000007030'::uuid,    2200.00),  -- Insurance
  ('00000000-0000-0000-0000-000000007040'::uuid,    2300.00),  -- Office Supplies & Misc
  -- R&D  (total: 92,000)
  ('00000000-0000-0000-0000-000000008000'::uuid,   76000.00),  -- Engineering Salaries
  ('00000000-0000-0000-0000-000000008010'::uuid,   10000.00),  -- Development Tools & Services
  ('00000000-0000-0000-0000-000000008020'::uuid,    6000.00)   -- Patent & IP Costs
) AS e(account_id, amount)
ON CONFLICT ON CONSTRAINT unique_entry DO NOTHING;


-- ─────────────────────────────────────────────────────────────────────────────
-- MONTH 6 : March 2025
-- Revenue $350,000 | Costs $320,000 | Profit $30,000
-- Trade show wind-down. Steady growth. No anomalies.
-- ─────────────────────────────────────────────────────────────────────────────
WITH
  rep AS (
    INSERT INTO reports (id, company_id, period, summary, anomaly_count, error_count)
    VALUES (
      gen_random_uuid(),
      '7696819b-a525-4bd7-85e9-baecc635465a',
      '2025-03-01',
      'March delivered $350K in revenue, continuing the steady upward trajectory with SaaS subscriptions at $245K. Costs of $320K reflect normalized operations as trade show spending wound down and spring marketing campaigns launched. Net income of $30K is in line with Q1 expectations.',
      0, 0
    )
    RETURNING id, company_id, period
  ),
  run AS (
    INSERT INTO runs (id, company_id, period, status, step, total_steps, progress_pct, opus_status, report_id)
    SELECT gen_random_uuid(), company_id, period, 'complete', 4, 4, 100, 'done', id
    FROM rep
  )
INSERT INTO monthly_entries (id, company_id, account_id, period, actual_amount, source_file)
SELECT gen_random_uuid(), '7696819b-a525-4bd7-85e9-baecc635465a', e.account_id, '2025-03-01', e.amount, 'historical_seed'
FROM (VALUES
  -- REVENUE  (total: 350,000)
  ('00000000-0000-0000-0000-000000004000'::uuid,  245000.00),  -- SaaS Subscriptions
  ('00000000-0000-0000-0000-000000004010'::uuid,   87500.00),  -- Professional Services
  ('00000000-0000-0000-0000-000000004020'::uuid,   10500.00),  -- Implementation Fees
  ('00000000-0000-0000-0000-000000004030'::uuid,    5250.00),  -- Training Revenue
  ('00000000-0000-0000-0000-000000004040'::uuid,    1750.00),  -- Maintenance Contracts
  -- COGS  (total: 82,000)
  ('00000000-0000-0000-0000-000000005000'::uuid,   21000.00),  -- Cloud Infrastructure
  ('00000000-0000-0000-0000-000000005010'::uuid,   49000.00),  -- Support Staff Salaries
  ('00000000-0000-0000-0000-000000005020'::uuid,   12000.00),  -- Third-Party Licenses
  -- OPEX  (total: 80,000) ← trade show ends, normal spring spend
  ('00000000-0000-0000-0000-000000006000'::uuid,   36500.00),  -- Sales Salaries & Commission
  ('00000000-0000-0000-0000-000000006010'::uuid,   18000.00),  -- Marketing & Advertising (normalized)
  ('00000000-0000-0000-0000-000000006020'::uuid,    5500.00),  -- Travel & Entertainment  (normalized)
  ('00000000-0000-0000-0000-000000006030'::uuid,    8000.00),  -- Office Rent & Utilities
  ('00000000-0000-0000-0000-000000006040'::uuid,   12000.00),  -- Software Tools & Subscriptions (spring renewal)
  -- G&A  (total: 54,000)
  ('00000000-0000-0000-0000-000000007000'::uuid,   30500.00),  -- Executive Salaries
  ('00000000-0000-0000-0000-000000007010'::uuid,   15000.00),  -- Admin Staff Salaries
  ('00000000-0000-0000-0000-000000007020'::uuid,    3500.00),  -- Legal & Professional Fees
  ('00000000-0000-0000-0000-000000007030'::uuid,    2200.00),  -- Insurance
  ('00000000-0000-0000-0000-000000007040'::uuid,    2800.00),  -- Office Supplies & Misc
  -- R&D  (total: 104,000)
  ('00000000-0000-0000-0000-000000008000'::uuid,   85000.00),  -- Engineering Salaries
  ('00000000-0000-0000-0000-000000008010'::uuid,   13000.00),  -- Development Tools & Services
  ('00000000-0000-0000-0000-000000008020'::uuid,    6000.00)   -- Patent & IP Costs
) AS e(account_id, amount)
ON CONFLICT ON CONSTRAINT unique_entry DO NOTHING;


-- ─────────────────────────────────────────────────────────────────────────────
-- MONTH 7 : April 2025  ⚠ ANOMALY 1
-- Revenue $340,000 | Costs $360,000 | Loss -$20,000
-- AWS outage caused customer churn → revenue dips below March.
-- One-time $43K legal penalty in G&A (7020) for SLA breach.
-- ─────────────────────────────────────────────────────────────────────────────
WITH
  rep AS (
    INSERT INTO reports (id, company_id, period, summary, anomaly_count, error_count)
    VALUES (
      gen_random_uuid(),
      '7696819b-a525-4bd7-85e9-baecc635465a',
      '2025-04-01',
      'April was a challenging month. A multi-day AWS infrastructure outage caused service disruptions for 12 enterprise customers, leading to a $10K revenue decline from March as affected clients paused expansion. A $43K one-time legal and settlement fee related to SLA breach penalties pushed costs to $360K, resulting in a -$20K operating loss. Infrastructure remediation costs were fully absorbed in the month.',
      1, 0
    )
    RETURNING id, company_id, period
  ),
  run AS (
    INSERT INTO runs (id, company_id, period, status, step, total_steps, progress_pct, opus_status, report_id)
    SELECT gen_random_uuid(), company_id, period, 'complete', 4, 4, 100, 'done', id
    FROM rep
  )
INSERT INTO monthly_entries (id, company_id, account_id, period, actual_amount, source_file)
SELECT gen_random_uuid(), '7696819b-a525-4bd7-85e9-baecc635465a', e.account_id, '2025-04-01', e.amount, 'historical_seed'
FROM (VALUES
  -- REVENUE  (total: 340,000) ← SaaS flat due to churn from outage
  ('00000000-0000-0000-0000-000000004000'::uuid,  238000.00),  -- SaaS Subscriptions  (flat vs Mar)
  ('00000000-0000-0000-0000-000000004010'::uuid,   85000.00),  -- Professional Services (paused engagements)
  ('00000000-0000-0000-0000-000000004020'::uuid,   10200.00),  -- Implementation Fees
  ('00000000-0000-0000-0000-000000004030'::uuid,    5100.00),  -- Training Revenue
  ('00000000-0000-0000-0000-000000004040'::uuid,    1700.00),  -- Maintenance Contracts
  -- COGS  (total: 84,000)
  ('00000000-0000-0000-0000-000000005000'::uuid,   22000.00),  -- Cloud Infrastructure
  ('00000000-0000-0000-0000-000000005010'::uuid,   50000.00),  -- Support Staff Salaries
  ('00000000-0000-0000-0000-000000005020'::uuid,   12000.00),  -- Third-Party Licenses
  -- OPEX  (total: 80,000)
  ('00000000-0000-0000-0000-000000006000'::uuid,   37000.00),  -- Sales Salaries & Commission
  ('00000000-0000-0000-0000-000000006010'::uuid,   18500.00),  -- Marketing & Advertising
  ('00000000-0000-0000-0000-000000006020'::uuid,    5500.00),  -- Travel & Entertainment
  ('00000000-0000-0000-0000-000000006030'::uuid,    8000.00),  -- Office Rent & Utilities
  ('00000000-0000-0000-0000-000000006040'::uuid,   11000.00),  -- Software Tools & Subscriptions
  -- G&A  (total: 93,000) ← 7020 Legal is the anomaly: $43K vs ~$3.5K baseline
  ('00000000-0000-0000-0000-000000007000'::uuid,   30500.00),  -- Executive Salaries
  ('00000000-0000-0000-0000-000000007010'::uuid,   15000.00),  -- Admin Staff Salaries
  ('00000000-0000-0000-0000-000000007020'::uuid,   43000.00),  -- Legal & Professional Fees ← $43K SLA penalty
  ('00000000-0000-0000-0000-000000007030'::uuid,    2200.00),  -- Insurance
  ('00000000-0000-0000-0000-000000007040'::uuid,    2300.00),  -- Office Supplies & Misc
  -- R&D  (total: 103,000)
  ('00000000-0000-0000-0000-000000008000'::uuid,   85000.00),  -- Engineering Salaries
  ('00000000-0000-0000-0000-000000008010'::uuid,   12000.00),  -- Development Tools & Services
  ('00000000-0000-0000-0000-000000008020'::uuid,    6000.00)   -- Patent & IP Costs
) AS e(account_id, amount)
ON CONFLICT ON CONSTRAINT unique_entry DO NOTHING;


-- ─────────────────────────────────────────────────────────────────────────────
-- MONTH 8 : May 2025  ⚠ ANOMALY 2  (largest cost event in the dataset)
-- Revenue $355,000 | Costs $450,000 | Loss -$95,000
-- Intentional investment month: 3 senior engineers hired + signing bonuses.
--   8000 Engineering Salaries: $85K → $150K  (+$65K, +76%)
--   7000 Executive Salaries:   $30.5K → $61K (+$30.5K, +100% — signing bonuses)
-- ─────────────────────────────────────────────────────────────────────────────
WITH
  rep AS (
    INSERT INTO reports (id, company_id, period, summary, anomaly_count, error_count)
    VALUES (
      gen_random_uuid(),
      '7696819b-a525-4bd7-85e9-baecc635465a',
      '2025-05-01',
      'May marks a strategic inflection point. Sentinel Secure hired three senior engineers to accelerate the roadmap, adding $65K in first-month engineering payroll including partial-month salary and onboarding equipment. Executive signing bonuses of $30K were also recognized in the period. Combined, these investments drove total costs to $450K and a -$95K operating loss. Revenue recovered to $355K as the April outage impact resolved. The hiring investment is expected to pay off in H2 2025 product velocity.',
      2, 0
    )
    RETURNING id, company_id, period
  ),
  run AS (
    INSERT INTO runs (id, company_id, period, status, step, total_steps, progress_pct, opus_status, report_id)
    SELECT gen_random_uuid(), company_id, period, 'complete', 4, 4, 100, 'done', id
    FROM rep
  )
INSERT INTO monthly_entries (id, company_id, account_id, period, actual_amount, source_file)
SELECT gen_random_uuid(), '7696819b-a525-4bd7-85e9-baecc635465a', e.account_id, '2025-05-01', e.amount, 'historical_seed'
FROM (VALUES
  -- REVENUE  (total: 355,000) ← recovery from April outage
  ('00000000-0000-0000-0000-000000004000'::uuid,  248500.00),  -- SaaS Subscriptions  (recovering)
  ('00000000-0000-0000-0000-000000004010'::uuid,   88750.00),  -- Professional Services
  ('00000000-0000-0000-0000-000000004020'::uuid,   10650.00),  -- Implementation Fees
  ('00000000-0000-0000-0000-000000004030'::uuid,    5325.00),  -- Training Revenue
  ('00000000-0000-0000-0000-000000004040'::uuid,    1775.00),  -- Maintenance Contracts
  -- COGS  (total: 89,000)
  ('00000000-0000-0000-0000-000000005000'::uuid,   23000.00),  -- Cloud Infrastructure
  ('00000000-0000-0000-0000-000000005010'::uuid,   53500.00),  -- Support Staff Salaries
  ('00000000-0000-0000-0000-000000005020'::uuid,   12500.00),  -- Third-Party Licenses
  -- OPEX  (total: 86,000) ← slight T&E uptick for engineering onboarding travel
  ('00000000-0000-0000-0000-000000006000'::uuid,   38000.00),  -- Sales Salaries & Commission
  ('00000000-0000-0000-0000-000000006010'::uuid,   19000.00),  -- Marketing & Advertising
  ('00000000-0000-0000-0000-000000006020'::uuid,    7000.00),  -- Travel & Entertainment (onboarding travel)
  ('00000000-0000-0000-0000-000000006030'::uuid,    8000.00),  -- Office Rent & Utilities
  ('00000000-0000-0000-0000-000000006040'::uuid,   14000.00),  -- Software Tools & Subscriptions (3 new licenses)
  -- G&A  (total: 89,000) ← 7000 Executive signing bonuses: +$30.5K vs April
  ('00000000-0000-0000-0000-000000007000'::uuid,   61000.00),  -- Executive Salaries (incl. $30.5K signing bonuses)
  ('00000000-0000-0000-0000-000000007010'::uuid,   16000.00),  -- Admin Staff Salaries
  ('00000000-0000-0000-0000-000000007020'::uuid,    3500.00),  -- Legal & Professional Fees (normalized)
  ('00000000-0000-0000-0000-000000007030'::uuid,    2200.00),  -- Insurance
  ('00000000-0000-0000-0000-000000007040'::uuid,    6300.00),  -- Office Supplies & Misc (desks/equip for 3 hires)
  -- R&D  (total: 186,000) ← 8000 Engineering is the primary anomaly: +$65K vs April
  ('00000000-0000-0000-0000-000000008000'::uuid,  150000.00),  -- Engineering Salaries (3 new senior engineers)
  ('00000000-0000-0000-0000-000000008010'::uuid,   30000.00),  -- Development Tools & Services (laptops + licenses)
  ('00000000-0000-0000-0000-000000008020'::uuid,    6000.00)   -- Patent & IP Costs
) AS e(account_id, amount)
ON CONFLICT ON CONSTRAINT unique_entry DO NOTHING;


-- ─────────────────────────────────────────────────────────────────────────────
-- PART 2 VALIDATION
-- ─────────────────────────────────────────────────────────────────────────────

-- 1. Confirm 168 monthly_entries after Parts 1+2 (21 × 8 months)
-- SELECT COUNT(*) FROM monthly_entries
-- WHERE company_id = '7696819b-a525-4bd7-85e9-baecc635465a'
--   AND source_file = 'historical_seed';
-- Expected: 168

-- 2. Confirm anomaly months have anomaly_count > 0
-- SELECT period, anomaly_count, LEFT(summary, 60) AS summary_preview
-- FROM reports
-- WHERE company_id = '7696819b-a525-4bd7-85e9-baecc635465a'
--   AND anomaly_count > 0
-- ORDER BY period;
-- Expected: 2025-04-01 → 1 | 2025-05-01 → 2

-- 3. Spot-check anomaly values
-- SELECT a.name, me.period, me.actual_amount
-- FROM monthly_entries me
-- JOIN accounts a ON a.id = me.account_id
-- WHERE me.company_id = '7696819b-a525-4bd7-85e9-baecc635465a'
--   AND a.code IN ('7020', '8000')
--   AND me.period IN ('2025-04-01', '2025-05-01')
-- ORDER BY me.period, a.code;
-- Expected: 7020/2025-04→43000 | 8000/2025-05→150000


-- =============================================================================
-- PART 3 OF 4
-- Periods : 2025-06-01 through 2025-10-01  (5 months)
-- Entries : 21 × 5 = 105 monthly_entries rows
-- Reports : 5   |   Runs: 5
-- Recovery arc post May hiring spike. Q4 marketing push in October.
-- No anomaly flags — all cost movements are explainable by narrative.
-- Engineering Salaries stabilise at new run-rate (~$97K Jun → $130K Oct).
-- =============================================================================


-- ─────────────────────────────────────────────────────────────────────────────
-- MONTH 9 : June 2025
-- Revenue $370,000 | Costs $340,000 | Profit $30,000
-- Recovery month. May signing bonuses don't recur; Engineering settles at
-- new run-rate ($97K). Sales and support costs step up with headcount.
-- ─────────────────────────────────────────────────────────────────────────────
WITH
  rep AS (
    INSERT INTO reports (id, company_id, period, summary, anomaly_count, error_count)
    VALUES (
      gen_random_uuid(),
      '7696819b-a525-4bd7-85e9-baecc635465a',
      '2025-06-01',
      'June marked a return to profitability with $370K in revenue and $30K net income. The May signing bonuses did not recur, bringing engineering costs back to a steady-state run-rate. SaaS subscriptions grew to $259K and professional services recovered to $92.5K as customers resumed paused engagements following the April outage resolution.',
      0, 0
    )
    RETURNING id, company_id, period
  ),
  run AS (
    INSERT INTO runs (id, company_id, period, status, step, total_steps, progress_pct, opus_status, report_id)
    SELECT gen_random_uuid(), company_id, period, 'complete', 4, 4, 100, 'done', id
    FROM rep
  )
INSERT INTO monthly_entries (id, company_id, account_id, period, actual_amount, source_file)
SELECT gen_random_uuid(), '7696819b-a525-4bd7-85e9-baecc635465a', e.account_id, '2025-06-01', e.amount, 'historical_seed'
FROM (VALUES
  -- REVENUE  (total: 370,000)
  ('00000000-0000-0000-0000-000000004000'::uuid,  259000.00),  -- SaaS Subscriptions
  ('00000000-0000-0000-0000-000000004010'::uuid,   92500.00),  -- Professional Services
  ('00000000-0000-0000-0000-000000004020'::uuid,   11100.00),  -- Implementation Fees
  ('00000000-0000-0000-0000-000000004030'::uuid,    5550.00),  -- Training Revenue
  ('00000000-0000-0000-0000-000000004040'::uuid,    1850.00),  -- Maintenance Contracts
  -- COGS  (total: 90,000)
  ('00000000-0000-0000-0000-000000005000'::uuid,   24000.00),  -- Cloud Infrastructure
  ('00000000-0000-0000-0000-000000005010'::uuid,   54000.00),  -- Support Staff Salaries
  ('00000000-0000-0000-0000-000000005020'::uuid,   12000.00),  -- Third-Party Licenses
  -- OPEX  (total: 80,000)
  ('00000000-0000-0000-0000-000000006000'::uuid,   38500.00),  -- Sales Salaries & Commission
  ('00000000-0000-0000-0000-000000006010'::uuid,   20000.00),  -- Marketing & Advertising
  ('00000000-0000-0000-0000-000000006020'::uuid,    5000.00),  -- Travel & Entertainment
  ('00000000-0000-0000-0000-000000006030'::uuid,    8000.00),  -- Office Rent & Utilities
  ('00000000-0000-0000-0000-000000006040'::uuid,    8500.00),  -- Software Tools & Subscriptions
  -- G&A  (total: 54,000) ← normalized; no bonuses
  ('00000000-0000-0000-0000-000000007000'::uuid,   31000.00),  -- Executive Salaries
  ('00000000-0000-0000-0000-000000007010'::uuid,   15500.00),  -- Admin Staff Salaries
  ('00000000-0000-0000-0000-000000007020'::uuid,    3500.00),  -- Legal & Professional Fees
  ('00000000-0000-0000-0000-000000007030'::uuid,    2200.00),  -- Insurance
  ('00000000-0000-0000-0000-000000007040'::uuid,    1800.00),  -- Office Supplies & Misc
  -- R&D  (total: 116,000) ← Engineering at new steady-state (signing bonuses gone)
  ('00000000-0000-0000-0000-000000008000'::uuid,   97000.00),  -- Engineering Salaries
  ('00000000-0000-0000-0000-000000008010'::uuid,   13000.00),  -- Development Tools & Services
  ('00000000-0000-0000-0000-000000008020'::uuid,    6000.00)   -- Patent & IP Costs
) AS e(account_id, amount)
ON CONFLICT ON CONSTRAINT unique_entry DO NOTHING;


-- ─────────────────────────────────────────────────────────────────────────────
-- MONTH 10 : July 2025
-- Revenue $390,000 | Costs $350,000 | Profit $40,000
-- Strong growth. Expanded sales team producing pipeline. Cloud scales.
-- ─────────────────────────────────────────────────────────────────────────────
WITH
  rep AS (
    INSERT INTO reports (id, company_id, period, summary, anomaly_count, error_count)
    VALUES (
      gen_random_uuid(),
      '7696819b-a525-4bd7-85e9-baecc635465a',
      '2025-07-01',
      'July delivered $390K in revenue — the strongest month to date — as the expanded sales team began generating new pipeline and SaaS subscriptions crossed $273K. The May engineering investment is showing early product velocity gains. Net income of $40K is the highest since January, demonstrating improving operating leverage.',
      0, 0
    )
    RETURNING id, company_id, period
  ),
  run AS (
    INSERT INTO runs (id, company_id, period, status, step, total_steps, progress_pct, opus_status, report_id)
    SELECT gen_random_uuid(), company_id, period, 'complete', 4, 4, 100, 'done', id
    FROM rep
  )
INSERT INTO monthly_entries (id, company_id, account_id, period, actual_amount, source_file)
SELECT gen_random_uuid(), '7696819b-a525-4bd7-85e9-baecc635465a', e.account_id, '2025-07-01', e.amount, 'historical_seed'
FROM (VALUES
  -- REVENUE  (total: 390,000)
  ('00000000-0000-0000-0000-000000004000'::uuid,  273000.00),  -- SaaS Subscriptions
  ('00000000-0000-0000-0000-000000004010'::uuid,   97500.00),  -- Professional Services
  ('00000000-0000-0000-0000-000000004020'::uuid,   11700.00),  -- Implementation Fees
  ('00000000-0000-0000-0000-000000004030'::uuid,    5850.00),  -- Training Revenue
  ('00000000-0000-0000-0000-000000004040'::uuid,    1950.00),  -- Maintenance Contracts
  -- COGS  (total: 92,000)
  ('00000000-0000-0000-0000-000000005000'::uuid,   25000.00),  -- Cloud Infrastructure (scaling with customers)
  ('00000000-0000-0000-0000-000000005010'::uuid,   55000.00),  -- Support Staff Salaries
  ('00000000-0000-0000-0000-000000005020'::uuid,   12000.00),  -- Third-Party Licenses
  -- OPEX  (total: 84,000)
  ('00000000-0000-0000-0000-000000006000'::uuid,   40000.00),  -- Sales Salaries & Commission (expanded team)
  ('00000000-0000-0000-0000-000000006010'::uuid,   20500.00),  -- Marketing & Advertising
  ('00000000-0000-0000-0000-000000006020'::uuid,    5500.00),  -- Travel & Entertainment
  ('00000000-0000-0000-0000-000000006030'::uuid,    8000.00),  -- Office Rent & Utilities
  ('00000000-0000-0000-0000-000000006040'::uuid,   10000.00),  -- Software Tools & Subscriptions
  -- G&A  (total: 55,000)
  ('00000000-0000-0000-0000-000000007000'::uuid,   31500.00),  -- Executive Salaries
  ('00000000-0000-0000-0000-000000007010'::uuid,   15500.00),  -- Admin Staff Salaries
  ('00000000-0000-0000-0000-000000007020'::uuid,    3500.00),  -- Legal & Professional Fees
  ('00000000-0000-0000-0000-000000007030'::uuid,    2200.00),  -- Insurance
  ('00000000-0000-0000-0000-000000007040'::uuid,    2300.00),  -- Office Supplies & Misc
  -- R&D  (total: 119,000)
  ('00000000-0000-0000-0000-000000008000'::uuid,  100000.00),  -- Engineering Salaries
  ('00000000-0000-0000-0000-000000008010'::uuid,   13000.00),  -- Development Tools & Services
  ('00000000-0000-0000-0000-000000008020'::uuid,    6000.00)   -- Patent & IP Costs
) AS e(account_id, amount)
ON CONFLICT ON CONSTRAINT unique_entry DO NOTHING;


-- ─────────────────────────────────────────────────────────────────────────────
-- MONTH 11 : August 2025
-- Revenue $410,000 | Costs $365,000 | Profit $45,000
-- Summer slowdown in professional services offset by SaaS growth.
-- Travel ticks up for summer client QBRs.
-- ─────────────────────────────────────────────────────────────────────────────
WITH
  rep AS (
    INSERT INTO reports (id, company_id, period, summary, anomaly_count, error_count)
    VALUES (
      gen_random_uuid(),
      '7696819b-a525-4bd7-85e9-baecc635465a',
      '2025-08-01',
      'August revenue reached $410K as SaaS subscriptions climbed to $287K. While professional services saw typical summer moderation, subscription growth more than compensated. Travel increased to $7K for quarterly business reviews with key enterprise accounts. Net income of $45K reflects strong operating leverage as revenue scales against a relatively fixed cost base.',
      0, 0
    )
    RETURNING id, company_id, period
  ),
  run AS (
    INSERT INTO runs (id, company_id, period, status, step, total_steps, progress_pct, opus_status, report_id)
    SELECT gen_random_uuid(), company_id, period, 'complete', 4, 4, 100, 'done', id
    FROM rep
  )
INSERT INTO monthly_entries (id, company_id, account_id, period, actual_amount, source_file)
SELECT gen_random_uuid(), '7696819b-a525-4bd7-85e9-baecc635465a', e.account_id, '2025-08-01', e.amount, 'historical_seed'
FROM (VALUES
  -- REVENUE  (total: 410,000)
  ('00000000-0000-0000-0000-000000004000'::uuid,  287000.00),  -- SaaS Subscriptions
  ('00000000-0000-0000-0000-000000004010'::uuid,  102500.00),  -- Professional Services
  ('00000000-0000-0000-0000-000000004020'::uuid,   12300.00),  -- Implementation Fees
  ('00000000-0000-0000-0000-000000004030'::uuid,    6150.00),  -- Training Revenue
  ('00000000-0000-0000-0000-000000004040'::uuid,    2050.00),  -- Maintenance Contracts
  -- COGS  (total: 95,000)
  ('00000000-0000-0000-0000-000000005000'::uuid,   26000.00),  -- Cloud Infrastructure
  ('00000000-0000-0000-0000-000000005010'::uuid,   57000.00),  -- Support Staff Salaries
  ('00000000-0000-0000-0000-000000005020'::uuid,   12000.00),  -- Third-Party Licenses
  -- OPEX  (total: 86,000)
  ('00000000-0000-0000-0000-000000006000'::uuid,   41000.00),  -- Sales Salaries & Commission
  ('00000000-0000-0000-0000-000000006010'::uuid,   20500.00),  -- Marketing & Advertising
  ('00000000-0000-0000-0000-000000006020'::uuid,    7000.00),  -- Travel & Entertainment (summer QBRs)
  ('00000000-0000-0000-0000-000000006030'::uuid,    8000.00),  -- Office Rent & Utilities
  ('00000000-0000-0000-0000-000000006040'::uuid,    9500.00),  -- Software Tools & Subscriptions
  -- G&A  (total: 56,000)
  ('00000000-0000-0000-0000-000000007000'::uuid,   32000.00),  -- Executive Salaries
  ('00000000-0000-0000-0000-000000007010'::uuid,   15500.00),  -- Admin Staff Salaries
  ('00000000-0000-0000-0000-000000007020'::uuid,    4000.00),  -- Legal & Professional Fees
  ('00000000-0000-0000-0000-000000007030'::uuid,    2200.00),  -- Insurance
  ('00000000-0000-0000-0000-000000007040'::uuid,    2300.00),  -- Office Supplies & Misc
  -- R&D  (total: 128,000)
  ('00000000-0000-0000-0000-000000008000'::uuid,  109000.00),  -- Engineering Salaries
  ('00000000-0000-0000-0000-000000008010'::uuid,   13000.00),  -- Development Tools & Services
  ('00000000-0000-0000-0000-000000008020'::uuid,    6000.00)   -- Patent & IP Costs
) AS e(account_id, amount)
ON CONFLICT ON CONSTRAINT unique_entry DO NOTHING;


-- ─────────────────────────────────────────────────────────────────────────────
-- MONTH 12 : September 2025
-- Revenue $430,000 | Costs $380,000 | Profit $50,000
-- End-of-Q3 renewal surge. Marketing ramps for Q4 push. Best profit month.
-- ─────────────────────────────────────────────────────────────────────────────
WITH
  rep AS (
    INSERT INTO reports (id, company_id, period, summary, anomaly_count, error_count)
    VALUES (
      gen_random_uuid(),
      '7696819b-a525-4bd7-85e9-baecc635465a',
      '2025-09-01',
      'September closed Q3 with $430K in revenue and a company-record $50K net income. End-of-quarter SaaS renewal activity pushed subscriptions to $301K for the first time. Marketing investment increased to $24.5K as Q4 campaign planning began. The engineering hires from May are delivering on roadmap commitments, supporting a strong renewal conversation with enterprise clients.',
      0, 0
    )
    RETURNING id, company_id, period
  ),
  run AS (
    INSERT INTO runs (id, company_id, period, status, step, total_steps, progress_pct, opus_status, report_id)
    SELECT gen_random_uuid(), company_id, period, 'complete', 4, 4, 100, 'done', id
    FROM rep
  )
INSERT INTO monthly_entries (id, company_id, account_id, period, actual_amount, source_file)
SELECT gen_random_uuid(), '7696819b-a525-4bd7-85e9-baecc635465a', e.account_id, '2025-09-01', e.amount, 'historical_seed'
FROM (VALUES
  -- REVENUE  (total: 430,000)
  ('00000000-0000-0000-0000-000000004000'::uuid,  301000.00),  -- SaaS Subscriptions
  ('00000000-0000-0000-0000-000000004010'::uuid,  107500.00),  -- Professional Services
  ('00000000-0000-0000-0000-000000004020'::uuid,   12900.00),  -- Implementation Fees
  ('00000000-0000-0000-0000-000000004030'::uuid,    6450.00),  -- Training Revenue
  ('00000000-0000-0000-0000-000000004040'::uuid,    2150.00),  -- Maintenance Contracts
  -- COGS  (total: 98,000)
  ('00000000-0000-0000-0000-000000005000'::uuid,   27000.00),  -- Cloud Infrastructure
  ('00000000-0000-0000-0000-000000005010'::uuid,   59000.00),  -- Support Staff Salaries
  ('00000000-0000-0000-0000-000000005020'::uuid,   12000.00),  -- Third-Party Licenses
  -- OPEX  (total: 92,000) ← Marketing starts Q4 ramp
  ('00000000-0000-0000-0000-000000006000'::uuid,   42000.00),  -- Sales Salaries & Commission
  ('00000000-0000-0000-0000-000000006010'::uuid,   24500.00),  -- Marketing & Advertising (Q4 prep)
  ('00000000-0000-0000-0000-000000006020'::uuid,    7000.00),  -- Travel & Entertainment
  ('00000000-0000-0000-0000-000000006030'::uuid,    8000.00),  -- Office Rent & Utilities
  ('00000000-0000-0000-0000-000000006040'::uuid,   10500.00),  -- Software Tools & Subscriptions
  -- G&A  (total: 57,000)
  ('00000000-0000-0000-0000-000000007000'::uuid,   32000.00),  -- Executive Salaries
  ('00000000-0000-0000-0000-000000007010'::uuid,   16000.00),  -- Admin Staff Salaries
  ('00000000-0000-0000-0000-000000007020'::uuid,    4000.00),  -- Legal & Professional Fees
  ('00000000-0000-0000-0000-000000007030'::uuid,    2200.00),  -- Insurance
  ('00000000-0000-0000-0000-000000007040'::uuid,    2800.00),  -- Office Supplies & Misc
  -- R&D  (total: 133,000)
  ('00000000-0000-0000-0000-000000008000'::uuid,  114000.00),  -- Engineering Salaries
  ('00000000-0000-0000-0000-000000008010'::uuid,   13000.00),  -- Development Tools & Services
  ('00000000-0000-0000-0000-000000008020'::uuid,    6000.00)   -- Patent & IP Costs
) AS e(account_id, amount)
ON CONFLICT ON CONSTRAINT unique_entry DO NOTHING;


-- ─────────────────────────────────────────────────────────────────────────────
-- MONTH 13 : October 2025
-- Revenue $450,000 | Costs $420,000 | Profit $30,000
-- Q4 marketing push: Marketing spikes +$15K vs September.
-- Office Rent steps up to $12K (expanded space for growing team).
-- NOT flagged as anomaly — Q4 marketing surge is expected seasonal behaviour.
-- ─────────────────────────────────────────────────────────────────────────────
WITH
  rep AS (
    INSERT INTO reports (id, company_id, period, summary, anomaly_count, error_count)
    VALUES (
      gen_random_uuid(),
      '7696819b-a525-4bd7-85e9-baecc635465a',
      '2025-10-01',
      'October revenue reached $450K as Q4 demand accelerated. SaaS subscriptions hit $315K — a 4.6% increase over September. Q4 marketing campaigns drove advertising spend to $39.5K (+$15K vs September trend), and the team moved into expanded office space at $12K per month. These investments compressed net income to $30K but are aligned with the Q4 pipeline plan.',
      0, 0
    )
    RETURNING id, company_id, period
  ),
  run AS (
    INSERT INTO runs (id, company_id, period, status, step, total_steps, progress_pct, opus_status, report_id)
    SELECT gen_random_uuid(), company_id, period, 'complete', 4, 4, 100, 'done', id
    FROM rep
  )
INSERT INTO monthly_entries (id, company_id, account_id, period, actual_amount, source_file)
SELECT gen_random_uuid(), '7696819b-a525-4bd7-85e9-baecc635465a', e.account_id, '2025-10-01', e.amount, 'historical_seed'
FROM (VALUES
  -- REVENUE  (total: 450,000)
  ('00000000-0000-0000-0000-000000004000'::uuid,  315000.00),  -- SaaS Subscriptions
  ('00000000-0000-0000-0000-000000004010'::uuid,  112500.00),  -- Professional Services
  ('00000000-0000-0000-0000-000000004020'::uuid,   13500.00),  -- Implementation Fees
  ('00000000-0000-0000-0000-000000004030'::uuid,    6750.00),  -- Training Revenue
  ('00000000-0000-0000-0000-000000004040'::uuid,    2250.00),  -- Maintenance Contracts
  -- COGS  (total: 103,000)
  ('00000000-0000-0000-0000-000000005000'::uuid,   29000.00),  -- Cloud Infrastructure
  ('00000000-0000-0000-0000-000000005010'::uuid,   62000.00),  -- Support Staff Salaries
  ('00000000-0000-0000-0000-000000005020'::uuid,   12000.00),  -- Third-Party Licenses
  -- OPEX  (total: 108,000) ← Marketing spike + Office Rent step-up
  ('00000000-0000-0000-0000-000000006000'::uuid,   44500.00),  -- Sales Salaries & Commission
  ('00000000-0000-0000-0000-000000006010'::uuid,   39500.00),  -- Marketing & Advertising (+$15K Q4 campaign)
  ('00000000-0000-0000-0000-000000006020'::uuid,    8000.00),  -- Travel & Entertainment
  ('00000000-0000-0000-0000-000000006030'::uuid,   12000.00),  -- Office Rent & Utilities (expanded space)
  ('00000000-0000-0000-0000-000000006040'::uuid,    4000.00),  -- Software Tools & Subscriptions
  -- G&A  (total: 60,000)
  ('00000000-0000-0000-0000-000000007000'::uuid,   33000.00),  -- Executive Salaries
  ('00000000-0000-0000-0000-000000007010'::uuid,   16500.00),  -- Admin Staff Salaries
  ('00000000-0000-0000-0000-000000007020'::uuid,    4500.00),  -- Legal & Professional Fees
  ('00000000-0000-0000-0000-000000007030'::uuid,    2200.00),  -- Insurance
  ('00000000-0000-0000-0000-000000007040'::uuid,    3800.00),  -- Office Supplies & Misc (new office setup)
  -- R&D  (total: 149,000)
  ('00000000-0000-0000-0000-000000008000'::uuid,  130000.00),  -- Engineering Salaries
  ('00000000-0000-0000-0000-000000008010'::uuid,   13000.00),  -- Development Tools & Services
  ('00000000-0000-0000-0000-000000008020'::uuid,    6000.00)   -- Patent & IP Costs
) AS e(account_id, amount)
ON CONFLICT ON CONSTRAINT unique_entry DO NOTHING;


-- ─────────────────────────────────────────────────────────────────────────────
-- PART 3 VALIDATION
-- ─────────────────────────────────────────────────────────────────────────────

-- 1. Confirm 273 monthly_entries after Parts 1+2+3 (21 × 13 months)
-- SELECT COUNT(*) FROM monthly_entries
-- WHERE company_id = '7696819b-a525-4bd7-85e9-baecc635465a'
--   AND source_file = 'historical_seed';
-- Expected: 273

-- 2. Confirm 13 runs, all complete and linked to reports
-- SELECT COUNT(*) FROM runs
-- WHERE company_id = '7696819b-a525-4bd7-85e9-baecc635465a'
--   AND status = 'complete' AND report_id IS NOT NULL;
-- Expected: 13

-- 3. Confirm Engineering salary trajectory (should show post-hiring step)
-- SELECT me.period, me.actual_amount
-- FROM monthly_entries me
-- WHERE me.company_id = '7696819b-a525-4bd7-85e9-baecc635465a'
--   AND me.account_id = '00000000-0000-0000-0000-000000008000'
-- ORDER BY me.period;
-- Expected: stable ~$85K through Apr → spike $150K in May → step down $97K Jun → gradual rise to $130K Oct

-- 4. Confirm Marketing spike in October
-- SELECT me.period, me.actual_amount
-- FROM monthly_entries me
-- WHERE me.company_id = '7696819b-a525-4bd7-85e9-baecc635465a'
--   AND me.account_id = '00000000-0000-0000-0000-000000006010'
--   AND me.period BETWEEN '2025-08-01' AND '2025-10-01'
-- ORDER BY me.period;
-- Expected: Aug→20500 | Sep→24500 | Oct→39500


-- =============================================================================
-- PART 4 OF 4  (FINAL)
-- Periods : 2025-11-01 through 2026-01-01  (3 months)
-- Entries : 21 × 3 = 63 monthly_entries rows
-- Reports : 3   |   Runs: 3
-- Anomaly in scope:
--   2025-12 : G&A year-end bonuses — Executive +$45K, Admin +$15K  anomaly_count=1
-- After this part: 16 months total, 336 monthly_entries, 3 anomalies flagged.
-- =============================================================================


-- ─────────────────────────────────────────────────────────────────────────────
-- MONTH 14 : November 2025
-- Revenue $470,000 | Costs $435,000 | Profit $35,000
-- Pre-holiday month. Marketing stays elevated ($38K). SaaS hits $329K.
-- ─────────────────────────────────────────────────────────────────────────────
WITH
  rep AS (
    INSERT INTO reports (id, company_id, period, summary, anomaly_count, error_count)
    VALUES (
      gen_random_uuid(),
      '7696819b-a525-4bd7-85e9-baecc635465a',
      '2025-11-01',
      'November closed with $470K in revenue and $35K net income. SaaS subscriptions grew to $329K as year-end renewal activity built momentum. Marketing spend held at $38K to sustain Q4 pipeline campaigns. Engineering capacity continued to scale with the roadmap, and all core cost categories remained within plan.',
      0, 0
    )
    RETURNING id, company_id, period
  ),
  run AS (
    INSERT INTO runs (id, company_id, period, status, step, total_steps, progress_pct, opus_status, report_id)
    SELECT gen_random_uuid(), company_id, period, 'complete', 4, 4, 100, 'done', id
    FROM rep
  )
INSERT INTO monthly_entries (id, company_id, account_id, period, actual_amount, source_file)
SELECT gen_random_uuid(), '7696819b-a525-4bd7-85e9-baecc635465a', e.account_id, '2025-11-01', e.amount, 'historical_seed'
FROM (VALUES
  -- REVENUE  (total: 470,000)
  ('00000000-0000-0000-0000-000000004000'::uuid,  329000.00),  -- SaaS Subscriptions
  ('00000000-0000-0000-0000-000000004010'::uuid,  117500.00),  -- Professional Services
  ('00000000-0000-0000-0000-000000004020'::uuid,   14100.00),  -- Implementation Fees
  ('00000000-0000-0000-0000-000000004030'::uuid,    7050.00),  -- Training Revenue
  ('00000000-0000-0000-0000-000000004040'::uuid,    2350.00),  -- Maintenance Contracts
  -- COGS  (total: 106,000)
  ('00000000-0000-0000-0000-000000005000'::uuid,   30000.00),  -- Cloud Infrastructure
  ('00000000-0000-0000-0000-000000005010'::uuid,   64000.00),  -- Support Staff Salaries
  ('00000000-0000-0000-0000-000000005020'::uuid,   12000.00),  -- Third-Party Licenses
  -- OPEX  (total: 109,000)
  ('00000000-0000-0000-0000-000000006000'::uuid,   45500.00),  -- Sales Salaries & Commission
  ('00000000-0000-0000-0000-000000006010'::uuid,   38000.00),  -- Marketing & Advertising (Q4 elevated)
  ('00000000-0000-0000-0000-000000006020'::uuid,    8500.00),  -- Travel & Entertainment
  ('00000000-0000-0000-0000-000000006030'::uuid,   12000.00),  -- Office Rent & Utilities
  ('00000000-0000-0000-0000-000000006040'::uuid,    5000.00),  -- Software Tools & Subscriptions
  -- G&A  (total: 62,000)
  ('00000000-0000-0000-0000-000000007000'::uuid,   33500.00),  -- Executive Salaries
  ('00000000-0000-0000-0000-000000007010'::uuid,   17000.00),  -- Admin Staff Salaries
  ('00000000-0000-0000-0000-000000007020'::uuid,    4500.00),  -- Legal & Professional Fees
  ('00000000-0000-0000-0000-000000007030'::uuid,    2200.00),  -- Insurance
  ('00000000-0000-0000-0000-000000007040'::uuid,    4800.00),  -- Office Supplies & Misc
  -- R&D  (total: 158,000)
  ('00000000-0000-0000-0000-000000008000'::uuid,  138500.00),  -- Engineering Salaries
  ('00000000-0000-0000-0000-000000008010'::uuid,   13500.00),  -- Development Tools & Services
  ('00000000-0000-0000-0000-000000008020'::uuid,    6000.00)   -- Patent & IP Costs
) AS e(account_id, amount)
ON CONFLICT ON CONSTRAINT unique_entry DO NOTHING;


-- ─────────────────────────────────────────────────────────────────────────────
-- MONTH 15 : December 2025  ⚠ ANOMALY 3
-- Revenue $500,000 | Costs $480,000 | Profit $20,000
-- First $500K revenue month. Year-end bonuses compress margin:
--   7000 Executive Salaries: $33.5K → $78.5K  (+$45K year-end bonus)
--   7010 Admin Staff Salaries: $17K → $32K    (+$15K holiday bonus)
-- Seasonal and explainable, but flagged for visibility.
-- ─────────────────────────────────────────────────────────────────────────────
WITH
  rep AS (
    INSERT INTO reports (id, company_id, period, summary, anomaly_count, error_count)
    VALUES (
      gen_random_uuid(),
      '7696819b-a525-4bd7-85e9-baecc635465a',
      '2025-12-01',
      'December achieved the company milestone of $500K in monthly revenue, driven by SaaS subscriptions crossing $350K and strong year-end professional services closings. Year-end bonus accruals elevated G&A costs significantly: executive bonuses added $45K and staff holiday bonuses added $15K above the November baseline, pushing total costs to $480K and compressing net income to $20K. These costs are seasonal and non-recurring; the underlying business is on track for a strong January.',
      1, 0
    )
    RETURNING id, company_id, period
  ),
  run AS (
    INSERT INTO runs (id, company_id, period, status, step, total_steps, progress_pct, opus_status, report_id)
    SELECT gen_random_uuid(), company_id, period, 'complete', 4, 4, 100, 'done', id
    FROM rep
  )
INSERT INTO monthly_entries (id, company_id, account_id, period, actual_amount, source_file)
SELECT gen_random_uuid(), '7696819b-a525-4bd7-85e9-baecc635465a', e.account_id, '2025-12-01', e.amount, 'historical_seed'
FROM (VALUES
  -- REVENUE  (total: 500,000)
  ('00000000-0000-0000-0000-000000004000'::uuid,  350000.00),  -- SaaS Subscriptions
  ('00000000-0000-0000-0000-000000004010'::uuid,  125000.00),  -- Professional Services
  ('00000000-0000-0000-0000-000000004020'::uuid,   15000.00),  -- Implementation Fees
  ('00000000-0000-0000-0000-000000004030'::uuid,    7500.00),  -- Training Revenue
  ('00000000-0000-0000-0000-000000004040'::uuid,    2500.00),  -- Maintenance Contracts
  -- COGS  (total: 108,000)
  ('00000000-0000-0000-0000-000000005000'::uuid,   31000.00),  -- Cloud Infrastructure
  ('00000000-0000-0000-0000-000000005010'::uuid,   65000.00),  -- Support Staff Salaries
  ('00000000-0000-0000-0000-000000005020'::uuid,   12000.00),  -- Third-Party Licenses
  -- OPEX  (total: 110,000)
  ('00000000-0000-0000-0000-000000006000'::uuid,   46000.00),  -- Sales Salaries & Commission
  ('00000000-0000-0000-0000-000000006010'::uuid,   32000.00),  -- Marketing & Advertising (winds down Dec)
  ('00000000-0000-0000-0000-000000006020'::uuid,    9500.00),  -- Travel & Entertainment (holiday events)
  ('00000000-0000-0000-0000-000000006030'::uuid,   12000.00),  -- Office Rent & Utilities
  ('00000000-0000-0000-0000-000000006040'::uuid,   10500.00),  -- Software Tools & Subscriptions (renewals)
  -- G&A  (total: 123,000) ← year-end bonus spike: +$45K exec, +$15K admin vs Nov
  ('00000000-0000-0000-0000-000000007000'::uuid,   78500.00),  -- Executive Salaries (base $33.5K + $45K bonus)
  ('00000000-0000-0000-0000-000000007010'::uuid,   32000.00),  -- Admin Staff Salaries (base $17K + $15K bonus)
  ('00000000-0000-0000-0000-000000007020'::uuid,    5000.00),  -- Legal & Professional Fees
  ('00000000-0000-0000-0000-000000007030'::uuid,    2200.00),  -- Insurance
  ('00000000-0000-0000-0000-000000007040'::uuid,    5300.00),  -- Office Supplies & Misc (gifts, parties)
  -- R&D  (total: 139,000) ← Engineering dips as team takes year-end PTO
  ('00000000-0000-0000-0000-000000008000'::uuid,  120000.00),  -- Engineering Salaries (holiday PTO reduction)
  ('00000000-0000-0000-0000-000000008010'::uuid,   13000.00),  -- Development Tools & Services
  ('00000000-0000-0000-0000-000000008020'::uuid,    6000.00)   -- Patent & IP Costs
) AS e(account_id, amount)
ON CONFLICT ON CONSTRAINT unique_entry DO NOTHING;


-- ─────────────────────────────────────────────────────────────────────────────
-- MONTH 16 : January 2026
-- Revenue $520,000 | Costs $460,000 | Profit $60,000
-- Best month in company history. December bonuses do not recur.
-- Strong new-year contract activations. Sets the baseline for live demo uploads.
-- ─────────────────────────────────────────────────────────────────────────────
WITH
  rep AS (
    INSERT INTO reports (id, company_id, period, summary, anomaly_count, error_count)
    VALUES (
      gen_random_uuid(),
      '7696819b-a525-4bd7-85e9-baecc635465a',
      '2026-01-01',
      'January 2026 delivered the strongest month in Sentinel Secure history: $520K in revenue and $60K in net income. SaaS subscriptions reached $364K as new annual contracts activated and a cohort of Q4 pipeline converted. December bonus accruals did not recur, normalising G&A to $65K and unlocking operating leverage. The engineering team returned from holiday PTO at full capacity, and the sales team is entering Q1 with a record pipeline. The business is well-positioned for continued growth through 2026.',
      0, 0
    )
    RETURNING id, company_id, period
  ),
  run AS (
    INSERT INTO runs (id, company_id, period, status, step, total_steps, progress_pct, opus_status, report_id)
    SELECT gen_random_uuid(), company_id, period, 'complete', 4, 4, 100, 'done', id
    FROM rep
  )
INSERT INTO monthly_entries (id, company_id, account_id, period, actual_amount, source_file)
SELECT gen_random_uuid(), '7696819b-a525-4bd7-85e9-baecc635465a', e.account_id, '2026-01-01', e.amount, 'historical_seed'
FROM (VALUES
  -- REVENUE  (total: 520,000)
  ('00000000-0000-0000-0000-000000004000'::uuid,  364000.00),  -- SaaS Subscriptions
  ('00000000-0000-0000-0000-000000004010'::uuid,  130000.00),  -- Professional Services
  ('00000000-0000-0000-0000-000000004020'::uuid,   15600.00),  -- Implementation Fees
  ('00000000-0000-0000-0000-000000004030'::uuid,    7800.00),  -- Training Revenue
  ('00000000-0000-0000-0000-000000004040'::uuid,    2600.00),  -- Maintenance Contracts
  -- COGS  (total: 111,000)
  ('00000000-0000-0000-0000-000000005000'::uuid,   32000.00),  -- Cloud Infrastructure
  ('00000000-0000-0000-0000-000000005010'::uuid,   67000.00),  -- Support Staff Salaries
  ('00000000-0000-0000-0000-000000005020'::uuid,   12000.00),  -- Third-Party Licenses
  -- OPEX  (total: 122,000)
  ('00000000-0000-0000-0000-000000006000'::uuid,   53000.00),  -- Sales Salaries & Commission (record month → record commission)
  ('00000000-0000-0000-0000-000000006010'::uuid,   30000.00),  -- Marketing & Advertising (Q1 demand gen)
  ('00000000-0000-0000-0000-000000006020'::uuid,    8000.00),  -- Travel & Entertainment
  ('00000000-0000-0000-0000-000000006030'::uuid,   12000.00),  -- Office Rent & Utilities
  ('00000000-0000-0000-0000-000000006040'::uuid,   19000.00),  -- Software Tools & Subscriptions (annual renewals)
  -- G&A  (total: 65,000) ← normalized post-December bonuses
  ('00000000-0000-0000-0000-000000007000'::uuid,   34000.00),  -- Executive Salaries (no bonus)
  ('00000000-0000-0000-0000-000000007010'::uuid,   17500.00),  -- Admin Staff Salaries
  ('00000000-0000-0000-0000-000000007020'::uuid,    4500.00),  -- Legal & Professional Fees
  ('00000000-0000-0000-0000-000000007030'::uuid,    2200.00),  -- Insurance
  ('00000000-0000-0000-0000-000000007040'::uuid,    6800.00),  -- Office Supplies & Misc (new year setup)
  -- R&D  (total: 162,000) ← Engineering rebounds from Dec PTO dip
  ('00000000-0000-0000-0000-000000008000'::uuid,  143000.00),  -- Engineering Salaries (full team + Jan raises)
  ('00000000-0000-0000-0000-000000008010'::uuid,   13000.00),  -- Development Tools & Services
  ('00000000-0000-0000-0000-000000008020'::uuid,    6000.00)   -- Patent & IP Costs
) AS e(account_id, amount)
ON CONFLICT ON CONSTRAINT unique_entry DO NOTHING;


-- =============================================================================
-- FINAL VALIDATION QUERIES
-- Run all of these after executing Parts 1–4.
-- =============================================================================

-- Total row counts
SELECT COUNT(*) FROM monthly_entries WHERE company_id = '7696819b-a525-4bd7-85e9-baecc635465a'; -- expect 336
SELECT COUNT(*) FROM runs    WHERE company_id = '7696819b-a525-4bd7-85e9-baecc635465a'; -- expect 16
SELECT COUNT(*) FROM reports WHERE company_id = '7696819b-a525-4bd7-85e9-baecc635465a'; -- expect 16

-- Anomaly months: 2025-04 (1), 2025-05 (2), 2025-12 (1)
SELECT period, anomaly_count
FROM reports
WHERE company_id = '7696819b-a525-4bd7-85e9-baecc635465a'
  AND anomaly_count > 0
ORDER BY period;

-- Every run must have report_id populated (expect 0 rows)
SELECT r.period, r.id AS run_id, r.report_id
FROM runs r
WHERE r.company_id = '7696819b-a525-4bd7-85e9-baecc635465a'
  AND r.report_id IS NULL;

-- All runs must be 'done' for Opus (expect only 'done')
SELECT DISTINCT opus_status FROM runs WHERE company_id = '7696819b-a525-4bd7-85e9-baecc635465a';

-- Period coverage: expect 2024-10-01 through 2026-01-01, 16 distinct periods
SELECT MIN(period), MAX(period), COUNT(DISTINCT period)
FROM monthly_entries
WHERE company_id = '7696819b-a525-4bd7-85e9-baecc635465a';

-- Every period must have exactly 21 accounts (expect 21 for all 16 rows)
SELECT period, COUNT(DISTINCT account_id) AS account_count
FROM monthly_entries
WHERE company_id = '7696819b-a525-4bd7-85e9-baecc635465a'
GROUP BY period
ORDER BY period;

-- No orphaned account_id references (expect 0)
SELECT COUNT(*) FROM monthly_entries me
WHERE me.company_id = '7696819b-a525-4bd7-85e9-baecc635465a'
  AND NOT EXISTS (SELECT 1 FROM accounts a WHERE a.id = me.account_id);

-- SaaS subscription growth arc (expect steady climb from 199.5K to 364K)
SELECT me.period, me.actual_amount AS saas_subscriptions
FROM monthly_entries me
WHERE me.company_id = '7696819b-a525-4bd7-85e9-baecc635465a'
  AND me.account_id = '00000000-0000-0000-0000-000000004000'
ORDER BY me.period;

-- December bonus spike confirmation
SELECT me.period, a.name, me.actual_amount
FROM monthly_entries me
JOIN accounts a ON a.id = me.account_id
WHERE me.company_id = '7696819b-a525-4bd7-85e9-baecc635465a'
  AND a.code IN ('7000', '7010')
  AND me.period IN ('2025-11-01', '2025-12-01', '2026-01-01')
ORDER BY me.period, a.code;
-- Expected: 7000: Nov→33500 | Dec→78500 | Jan→34000
--           7010: Nov→17000 | Dec→32000 | Jan→17500
