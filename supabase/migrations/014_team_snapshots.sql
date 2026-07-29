-- 014_team_snapshots.sql
-- Weekly team snapshots: Monday (preview) and Friday (review).
-- Populated by the snapshot pipeline (Mon/Fri 7:50 CEST).

CREATE TABLE team_snapshots (
  id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  team            TEXT NOT NULL,
  tl_email        TEXT,
  iso_week        TEXT NOT NULL,           -- "2026-W30"
  snapshot_day    SMALLINT NOT NULL CHECK (snapshot_day IN (1, 2)),  -- 1=Mon, 2=Fri
  snapshot_date   DATE NOT NULL,

  -- Metrics
  demos_booked    INTEGER DEFAULT 0,
  demos_held      INTEGER DEFAULT 0,
  mr_closed       NUMERIC DEFAULT 0,
  mr_expected     NUMERIC DEFAULT 0,
  wons_week       INTEGER DEFAULT 0,
  wons_month      INTEGER DEFAULT 0,
  mr_closed_month NUMERIC DEFAULT 0,
  consecucion_pct NUMERIC DEFAULT 0,

  -- Variable content (Mon: closing_expected, whales / Fri: lost_deals, learnings, coaching_flags)
  data            JSONB DEFAULT '{}',

  created_at      TIMESTAMPTZ DEFAULT now(),
  updated_at      TIMESTAMPTZ DEFAULT now(),
  UNIQUE(tl_email, iso_week, snapshot_day)
);

CREATE INDEX idx_team_snapshots_team ON team_snapshots(team);
CREATE INDEX idx_team_snapshots_date ON team_snapshots(snapshot_date);
CREATE INDEX idx_team_snapshots_week ON team_snapshots(iso_week);

CREATE TRIGGER set_updated_at BEFORE UPDATE ON team_snapshots
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

ALTER TABLE team_snapshots ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon_read"          ON team_snapshots FOR SELECT TO anon          USING (true);
CREATE POLICY "authenticated_read" ON team_snapshots FOR SELECT TO authenticated USING (true);
CREATE POLICY "service_all"        ON team_snapshots FOR ALL    TO service_role   USING (true);
