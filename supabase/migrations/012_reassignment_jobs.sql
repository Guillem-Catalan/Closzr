-- 012_reassignment_jobs.sql
-- Stores deal reassignment requests from the UI wizard.
-- The Python pipeline (orgchart/reassign_deals.py) picks up pending jobs,
-- applies changes to deals + deal_ui + HubSpot, and marks them completed.

CREATE TABLE IF NOT EXISTS reassignment_jobs (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Who requested and when
  requested_by    TEXT NOT NULL,
  requested_at    TIMESTAMPTZ NOT NULL DEFAULT now(),

  -- The batch: all deals being reassigned together
  job_data        JSONB NOT NULL DEFAULT '[]'::jsonb,
  -- Each element: {deal_id, new_email, role, company_name, mrr}

  -- Source person (whose deals are being redistributed)
  source_email    TEXT NOT NULL,
  source_name     TEXT,

  -- Processing
  status          TEXT NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending', 'processing', 'done', 'failed')),
  started_at      TIMESTAMPTZ,
  completed_at    TIMESTAMPTZ,

  -- Results (filled by the pipeline)
  results         JSONB DEFAULT '[]'::jsonb,
  -- Each element: {deal_id, ok, error?}

  error_message   TEXT
);

CREATE INDEX IF NOT EXISTS idx_reassignment_jobs_status
  ON reassignment_jobs(status) WHERE status = 'pending';

-- RLS
ALTER TABLE reassignment_jobs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "authenticated_read" ON reassignment_jobs
  FOR SELECT TO authenticated USING (true);
CREATE POLICY "authenticated_insert" ON reassignment_jobs
  FOR INSERT TO authenticated WITH CHECK (true);
CREATE POLICY "service_all" ON reassignment_jobs
  FOR ALL TO service_role USING (true);
