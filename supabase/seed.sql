-- IronLedger — Demo Seed Data
-- Run AFTER 0001_initial_schema.sql and AFTER the demo user is created
-- in Supabase Auth (demo@dronedemo.com).
--
-- This file is safe to re-run: ON CONFLICT DO NOTHING guards every insert.

INSERT INTO companies (owner_id, name, currency)
SELECT
  id,
  'DRONE Inc.',
  'USD'
FROM auth.users
WHERE email = 'demo@dronedemo.com'
ON CONFLICT DO NOTHING;
