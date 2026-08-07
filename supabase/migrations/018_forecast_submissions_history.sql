CREATE TABLE IF NOT EXISTS forecast_submissions_history (
  id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  owner_id        TEXT NOT NULL,
  owner_email     TEXT,
  team_id         TEXT,
  team_name       TEXT,
  month           TEXT NOT NULL,
  pipeline_id     TEXT NOT NULL DEFAULT 'default',
  forecast_amount NUMERIC NOT NULL DEFAULT 0,
  submission_type TEXT NOT NULL DEFAULT 'rep',
  submission_notes TEXT,
  last_modified   TIMESTAMPTZ,
  synced_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_fsh_month ON forecast_submissions_history (month);
CREATE INDEX IF NOT EXISTS idx_fsh_synced ON forecast_submissions_history (synced_at);
CREATE INDEX IF NOT EXISTS idx_fsh_owner ON forecast_submissions_history (owner_id, month);

ALTER TABLE forecast_submissions_history ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'forecast_submissions_history' AND policyname = 'fsh_read') THEN
    CREATE POLICY "fsh_read" ON forecast_submissions_history FOR SELECT USING (true);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'forecast_submissions_history' AND policyname = 'fsh_write') THEN
    CREATE POLICY "fsh_write" ON forecast_submissions_history FOR ALL
      USING (
        EXISTS (
          SELECT 1 FROM orgchart
          WHERE orgchart.email = auth.jwt() ->> 'email'
            AND orgchart.role IN ('admin','director','head')
        )
      );
  END IF;
END $$;
