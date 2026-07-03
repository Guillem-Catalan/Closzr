CREATE TABLE IF NOT EXISTS oneone_sessions (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tl_email      TEXT NOT NULL,
  rep_name      TEXT NOT NULL,
  team          TEXT,
  week_type     INTEGER NOT NULL CHECK (week_type BETWEEN 0 AND 3),
  session_date  DATE NOT NULL,
  checks        JSONB DEFAULT '{}'::jsonb,
  entries       JSONB DEFAULT '[]'::jsonb,
  created_at    TIMESTAMPTZ DEFAULT now(),
  updated_at    TIMESTAMPTZ DEFAULT now(),
  UNIQUE(tl_email, rep_name, session_date)
);

CREATE INDEX IF NOT EXISTS idx_oo_rep ON oneone_sessions(rep_name, session_date DESC);
CREATE INDEX IF NOT EXISTS idx_oo_tl ON oneone_sessions(tl_email, session_date DESC);

ALTER TABLE oneone_sessions ENABLE ROW LEVEL SECURITY;
CREATE POLICY "authenticated_all" ON oneone_sessions FOR ALL TO authenticated USING (true);
CREATE POLICY "anon_read" ON oneone_sessions FOR SELECT TO anon USING (true);
CREATE POLICY "service_all" ON oneone_sessions FOR ALL TO service_role USING (true);

CREATE TRIGGER trg_oneone_updated_at BEFORE UPDATE ON oneone_sessions
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();
