-- 010_orgchart.sql
-- Orgchart table: mirrors org.py hierarchy, editable from UI

CREATE TABLE orgchart (
  email           TEXT PRIMARY KEY,
  full_name       TEXT NOT NULL,
  hs_owner_id     TEXT,
  role            TEXT NOT NULL,
  channel         TEXT NOT NULL,
  team_name       TEXT NOT NULL,
  reports_to      TEXT,
  hierarchy_level INTEGER DEFAULT 0,
  is_active       BOOLEAN DEFAULT TRUE,
  target_mrr      NUMERIC DEFAULT 0,
  additional_teams JSONB DEFAULT '[]'::jsonb,
  created_at      TIMESTAMPTZ DEFAULT now(),
  updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_orgchart_team ON orgchart(team_name);
CREATE INDEX idx_orgchart_reports_to ON orgchart(reports_to);
CREATE INDEX idx_orgchart_active ON orgchart(is_active) WHERE is_active = TRUE;

CREATE TRIGGER set_updated_at BEFORE UPDATE ON orgchart
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

ALTER TABLE orgchart ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon_read"          ON orgchart FOR SELECT TO anon          USING (true);
CREATE POLICY "authenticated_read" ON orgchart FOR SELECT TO authenticated USING (true);
CREATE POLICY "authenticated_write" ON orgchart FOR ALL   TO authenticated USING (true);
CREATE POLICY "service_all"        ON orgchart FOR ALL   TO service_role   USING (true);
