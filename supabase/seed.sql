-- Month Proof — Demo Seed Data
--
-- Seeds the demo COMPANY ROW only. It does not load financial data — the four
-- Redhawk workbooks in docs/demo_data/redhawk/ are uploaded through the normal
-- parse pipeline during manual testing, not inserted here.
--
-- PRECONDITION: the demo user must already exist in Supabase Auth with the
-- email below. This file matches on that email; if the user does not exist it
-- inserts nothing (silently, by design — it is a SELECT ... WHERE).
--
--   Demo user: demo@redhawkdemo.com
--
-- Keep DEMO_USER_EMAIL in .env in sync with the address above.
--
-- Demo company: Redhawk Alarm & Security LLC — a small owner-operated alarm
-- dealer, matching the ICP (field service, 5 employees, ~$38,090/month
-- revenue). That revenue puts it in the `under_100k` band, which drives Item
-- 5's scaled flux gates to $1,250 / $250 instead of the $50k / $10k fail-safe.
--
-- Safe to re-run: the NOT EXISTS guard below is a real guard. Note that
-- `companies` has NO unique constraint on owner_id, so a bare
-- `ON CONFLICT DO NOTHING` would NOT prevent a duplicate — and a second
-- company for one owner is actively harmful, because
-- SupabaseCompaniesRepo.get_by_owner does `.limit(1)` with no ordering and
-- would resolve the user to an arbitrary one of them.

INSERT INTO companies (owner_id, name, currency, sector, monthly_revenue_band)
SELECT
  u.id,
  'Redhawk Alarm & Security LLC',
  'USD',
  'Field Service — Alarm & Security',
  'under_100k'
FROM auth.users u
WHERE u.email = 'demo@redhawkdemo.com'
  AND NOT EXISTS (
    SELECT 1 FROM companies c WHERE c.owner_id = u.id
  );
