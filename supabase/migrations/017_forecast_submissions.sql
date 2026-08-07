-- Safe against existing prod table
CREATE TABLE IF NOT EXISTS forecast_submissions (
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
  synced_at       TIMESTAMPTZ DEFAULT now(),
  created_at      TIMESTAMPTZ DEFAULT now(),
  updated_at      TIMESTAMPTZ DEFAULT now(),
  CONSTRAINT forecast_submissions_unique
    UNIQUE (owner_id, month, pipeline_id, submission_type)
);

CREATE INDEX IF NOT EXISTS idx_fs_month ON forecast_submissions (month);
CREATE INDEX IF NOT EXISTS idx_fs_owner ON forecast_submissions (owner_email);
CREATE INDEX IF NOT EXISTS idx_fs_team ON forecast_submissions (team_name);
CREATE INDEX IF NOT EXISTS idx_fs_type ON forecast_submissions (submission_type);

ALTER TABLE forecast_submissions ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'forecast_submissions' AND policyname = 'fs_read') THEN
    CREATE POLICY "fs_read" ON forecast_submissions FOR SELECT USING (true);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'forecast_submissions' AND policyname = 'fs_write') THEN
    CREATE POLICY "fs_write" ON forecast_submissions FOR ALL
      USING (
        EXISTS (
          SELECT 1 FROM orgchart
          WHERE orgchart.email = auth.jwt() ->> 'email'
            AND orgchart.role IN ('admin','director','head')
        )
      );
  END IF;
END $$;
