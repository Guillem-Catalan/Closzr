-- Add lost-deal red flag columns to team_snapshots (Friday briefs)
ALTER TABLE team_snapshots
  ADD COLUMN IF NOT EXISTS lost_red_flag_deal      TEXT,
  ADD COLUMN IF NOT EXISTS lost_red_flag_amount    NUMERIC,
  ADD COLUMN IF NOT EXISTS lost_red_flag_reason    TEXT,
  ADD COLUMN IF NOT EXISTS lost_red_flag_pae       TEXT,
  ADD COLUMN IF NOT EXISTS lost_red_flag_narrative TEXT;
