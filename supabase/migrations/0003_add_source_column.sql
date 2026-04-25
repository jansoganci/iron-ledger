-- Day 4 retrofit: provenance for AnomalyCard hover.
-- Parser writes the original column header per row; /anomalies and /report
-- read it back via the list_for_period entry JOIN in the serializer.

ALTER TABLE monthly_entries
  ADD COLUMN IF NOT EXISTS source_column TEXT;
