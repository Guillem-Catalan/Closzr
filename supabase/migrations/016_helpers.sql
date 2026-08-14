-- 016_helpers.sql
-- Idempotent: CREATE OR REPLACE is safe to re-run.
-- This function may already exist from team_snapshots (014), but
-- using OR REPLACE ensures it exists without failing if already present.

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;
