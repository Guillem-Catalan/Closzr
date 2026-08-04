CREATE TABLE IF NOT EXISTS ae_targets (
  id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  email          TEXT NOT NULL,
  month          TEXT NOT NULL,
  monthly_target NUMERIC NOT NULL DEFAULT 0,
  source         TEXT NOT NULL DEFAULT 'data_lake',
  synced_at      TIMESTAMPTZ DEFAULT now(),
  created_at     TIMESTAMPTZ DEFAULT now(),
  updated_at     TIMESTAMPTZ DEFAULT now(),

  CONSTRAINT ae_targets_unique UNIQUE (email, month)
);

CREATE INDEX idx_ae_targets_month ON ae_targets (month);
CREATE INDEX idx_ae_targets_email ON ae_targets (email);

ALTER TABLE ae_targets ENABLE ROW LEVEL SECURITY;

CREATE POLICY "ae_targets_read"
  ON ae_targets FOR SELECT
  USING (true);

CREATE POLICY "ae_targets_write"
  ON ae_targets FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM orgchart
      WHERE orgchart.email = auth.jwt() ->> 'email'
        AND orgchart.role IN ('admin','director','head')
    )
  );
