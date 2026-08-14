-- 019_team_snapshots_red_flag.sql
-- Extends team_snapshots (PR #35) with Lost Red Flag columns.
-- Writer remains snapshot/run.py only.

ALTER TABLE team_snapshots
  ADD COLUMN IF NOT EXISTS lost_red_flag_deal      TEXT,
  ADD COLUMN IF NOT EXISTS lost_red_flag_amount    NUMERIC,
  ADD COLUMN IF NOT EXISTS lost_red_flag_reason    TEXT,
  ADD COLUMN IF NOT EXISTS lost_red_flag_pae       TEXT,
  ADD COLUMN IF NOT EXISTS lost_red_flag_narrative TEXT;
