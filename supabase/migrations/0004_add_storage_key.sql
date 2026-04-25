-- Day 4 retrofit: Retry Analysis needs the stored file path.
-- POST /upload persists the storage key at run creation.
-- POST /runs/{run_id}/retry reads it to reschedule the pipeline
-- against the existing upload without forcing a re-upload.

ALTER TABLE runs
  ADD COLUMN IF NOT EXISTS storage_key TEXT;
