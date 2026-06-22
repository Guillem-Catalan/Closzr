-- ============================================================================
-- Ensure deal_trajectories has UNIQUE on deal_id for upsert (on_hold → closed redo)
-- ============================================================================

-- Add unique constraint if not exists (idempotent via IF NOT EXISTS on index)
CREATE UNIQUE INDEX IF NOT EXISTS idx_deal_trajectories_deal_id_unique
  ON deal_trajectories(deal_id);
