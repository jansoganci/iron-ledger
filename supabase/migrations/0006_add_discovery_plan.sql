-- Phase 3 Step 8: Discovery plan persistence for the new Discovery & Mapping Layer.
-- Both columns nullable. Pre-Discovery runs stay NULL forever (frontend treats
-- NULL as "legacy run, no modal"). Populated by Phase 3 parser rewire (Step 9).
--
-- discovery_approval_mode is nullable even on new runs while the plan is still
-- awaiting user review — it flips to 'auto' on high-confidence auto-advance or
-- 'manual' when POST /runs/{id}/confirm-discovery fires.

ALTER TABLE runs
  ADD COLUMN IF NOT EXISTS discovery_plan JSONB;

ALTER TABLE runs
  ADD COLUMN IF NOT EXISTS discovery_approval_mode TEXT
    CHECK (discovery_approval_mode IN ('auto', 'manual'));
