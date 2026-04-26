-- Opus upgrade feature: track async upgrade status on runs, flag when report is upgraded
ALTER TABLE runs ADD COLUMN IF NOT EXISTS opus_status TEXT DEFAULT 'pending';
-- Values: 'pending' | 'running' | 'done' | 'failed'

ALTER TABLE reports ADD COLUMN IF NOT EXISTS opus_upgraded BOOLEAN DEFAULT FALSE;
