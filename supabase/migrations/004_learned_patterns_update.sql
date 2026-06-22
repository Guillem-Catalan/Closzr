-- ============================================================================
-- Update learned_patterns for accumulative learning
-- Adds pattern_key (unique identifier), value, history, updated_at
-- ============================================================================

ALTER TABLE learned_patterns ADD COLUMN IF NOT EXISTS pattern_key TEXT;
ALTER TABLE learned_patterns ADD COLUMN IF NOT EXISTS value NUMERIC;
ALTER TABLE learned_patterns ADD COLUMN IF NOT EXISTS history JSONB DEFAULT '[]'::jsonb;
ALTER TABLE learned_patterns ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();

-- Unique index on pattern_key for upsert
CREATE UNIQUE INDEX IF NOT EXISTS idx_learned_patterns_key
  ON learned_patterns(pattern_key) WHERE pattern_key IS NOT NULL;
