-- Dil 3: period lock. A user signs off a finished monthly report ("I closed
-- this period"); the month is then read-only until someone reopens it.
--
-- period_closes keeps one row per close. Reopening never deletes it: the row
-- gets reopened_at / reopened_by. At most one row per (company, period) can be
-- open (reopened_at IS NULL) at a time, so a closed month has exactly one
-- active lock. period_close_log is an append-only trail of closed / reopened.
--
-- company_id is always resolved by the backend from the signed-in user. RLS
-- mirrors accounts/runs: only the company owner can see or write these rows.
-- RunStatus is untouched; a closed period is not a run state.

CREATE TABLE IF NOT EXISTS period_closes (
  id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id         UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  period             DATE NOT NULL,
  closed_by          UUID NOT NULL REFERENCES auth.users(id),
  closed_by_email    TEXT,
  closed_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  reopened_by        UUID REFERENCES auth.users(id),
  reopened_by_email  TEXT,
  reopened_at        TIMESTAMPTZ,
  CONSTRAINT period_closes_month_start_chk
    CHECK (period = date_trunc('month', period)::date),
  CONSTRAINT period_closes_reopen_pair_chk
    CHECK ((reopened_at IS NULL) = (reopened_by IS NULL))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_period_closes_active
  ON period_closes (company_id, period)
  WHERE reopened_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_period_closes_company_period
  ON period_closes (company_id, period);

CREATE TABLE IF NOT EXISTS period_close_log (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id   UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  period       DATE NOT NULL,
  close_id     UUID NOT NULL REFERENCES period_closes(id),
  event        TEXT NOT NULL,
  actor_id     UUID NOT NULL REFERENCES auth.users(id),
  actor_email  TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT period_close_log_event_chk
    CHECK (event IN ('closed', 'reopened'))
);

CREATE INDEX IF NOT EXISTS idx_period_close_log_company_period
  ON period_close_log (company_id, period, created_at);

ALTER TABLE period_closes ENABLE ROW LEVEL SECURITY;
ALTER TABLE period_close_log ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS period_closes_select ON period_closes;
CREATE POLICY period_closes_select ON period_closes
  FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM companies c
      WHERE c.id = period_closes.company_id AND c.owner_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS period_closes_insert ON period_closes;
CREATE POLICY period_closes_insert ON period_closes
  FOR INSERT
  WITH CHECK (
    closed_by = auth.uid()
    AND EXISTS (
      SELECT 1 FROM companies c
      WHERE c.id = period_closes.company_id AND c.owner_id = auth.uid()
    )
  );

-- Update exists only to stamp reopened_*; there is no DELETE policy, so a
-- close can never be removed through the API.
DROP POLICY IF EXISTS period_closes_reopen ON period_closes;
CREATE POLICY period_closes_reopen ON period_closes
  FOR UPDATE
  USING (
    EXISTS (
      SELECT 1 FROM companies c
      WHERE c.id = period_closes.company_id AND c.owner_id = auth.uid()
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM companies c
      WHERE c.id = period_closes.company_id AND c.owner_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS period_close_log_select ON period_close_log;
CREATE POLICY period_close_log_select ON period_close_log
  FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM companies c
      WHERE c.id = period_close_log.company_id AND c.owner_id = auth.uid()
    )
  );

-- Append-only: insert and select only.
DROP POLICY IF EXISTS period_close_log_insert ON period_close_log;
CREATE POLICY period_close_log_insert ON period_close_log
  FOR INSERT
  WITH CHECK (
    actor_id = auth.uid()
    AND EXISTS (
      SELECT 1 FROM companies c
      WHERE c.id = period_close_log.company_id AND c.owner_id = auth.uid()
    )
  );
