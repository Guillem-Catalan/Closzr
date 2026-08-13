-- Add target_mrr and demos_held_mrr to team_snapshots
ALTER TABLE team_snapshots
  ADD COLUMN IF NOT EXISTS target_mrr      NUMERIC,
  ADD COLUMN IF NOT EXISTS demos_held_mrr  NUMERIC;
