-- 018_team_summary.sql
-- One row per team per period. Aggregated from rep_summary.
-- Writer: stats_run() orchestrated job (team_stats pass).
-- Key: (team, period_type, period_start) — UPSERT within a period.

CREATE TABLE IF NOT EXISTS team_summary (
  id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  run_id            UUID NOT NULL,

  -- ── Identity ──
  team              TEXT NOT NULL,
  tl_email          TEXT NOT NULL,
  tl_name           TEXT,
  rep_count         INT NOT NULL DEFAULT 0,

  -- ── Period ──
  period_type       TEXT NOT NULL CHECK (period_type IN ('weekly', 'monthly', 'quarterly')),
  period_start      DATE NOT NULL,
  period_end        DATE NOT NULL,
  computed_at       TIMESTAMPTZ NOT NULL DEFAULT now(),

  -- ═══════════════════════════════════════════════════════════
  -- POOLED METRICS (leadership numbers)
  -- Computed by summing raw counts from rep_summary, NOT by averaging rates.
  -- Example: win_rate_pooled = SUM(deals_won_count) / SUM(deals_closed_count) x 100
  -- This gives a rep with 30 closed deals more weight than one with 2.
  -- ═══════════════════════════════════════════════════════════
  win_rate_pooled          NUMERIC,          -- total_won / (total_won + total_lost) x 100
  avg_cycle_won_pooled     NUMERIC,          -- mean cycle across ALL team won deals
  avg_deal_size_won_pooled NUMERIC,          -- mean MRR across ALL team won deals
  total_deals_closed       INT,
  total_deals_won          INT,
  total_deals_lost         INT,
  -- Pipeline: POPULATED ONLY IN weekly ROWS (Segment B rule). NULL in monthly/quarterly.
  total_pipeline_value     NUMERIC,          -- sum of all reps' pipeline_value

  -- ═══════════════════════════════════════════════════════════
  -- DISTRIBUTION METRICS (TL coaching: spread across reps)
  -- Unweighted: each rep counts equally regardless of deal volume.
  -- Purpose: TLs see variance within their team for coaching conversations.
  -- ═══════════════════════════════════════════════════════════
  win_rate_avg             NUMERIC,          -- mean of per-rep win rates
  win_rate_median          NUMERIC,
  win_rate_p25             NUMERIC,
  win_rate_p75             NUMERIC,
  avg_cycle_won_avg        NUMERIC,
  avg_cycle_won_median     NUMERIC,
  calls_per_week_avg       NUMERIC,
  calls_per_week_median    NUMERIC,
  -- MEDDIC: computed as mean of per-rep MEDDIC totals.
  -- Each rep's total = sum of pillar values from avg_meddic_per_pillar JSONB.
  avg_meddic_avg           NUMERIC,
  avg_meddic_p25           NUMERIC,
  avg_meddic_p75           NUMERIC,
  demo_rate_avg            NUMERIC,
  post_demo_win_rate_avg   NUMERIC,
  multi_thread_rate_avg    NUMERIC,

  -- ═══════════════════════════════════════════════════════════
  -- TARGET & CONSECUTION
  -- POPULATED ONLY IN monthly ROWS. Targets are monthly; other period_types
  -- produce meaningless ratios. NULL in weekly/quarterly rows.
  -- Source: ae_targets (PR #43), summed for reps in this team.
  -- ═══════════════════════════════════════════════════════════
  team_target              NUMERIC,          -- sum of ae_targets for reps in team
  mrr_closed_month         NUMERIC,          -- total MRR won in the complete previous month
  consecution_pct          NUMERIC,          -- mrr_closed_month / team_target x 100
  reps_with_target         INT,              -- reps matched in ae_targets
  reps_without_target      INT,              -- if > 0, team_target understated — surface in UI

  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

  CONSTRAINT team_summary_unique UNIQUE (team, period_type, period_start)
);

-- ── Index ──
CREATE INDEX IF NOT EXISTS idx_team_summary_tl_period
  ON team_summary (tl_email, period_type, period_start);

-- ── Trigger ──
DROP TRIGGER IF EXISTS trg_team_summary_updated_at ON team_summary;
CREATE TRIGGER trg_team_summary_updated_at BEFORE UPDATE ON team_summary
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ── RLS ──
ALTER TABLE team_summary ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon_read"          ON team_summary FOR SELECT TO anon          USING (true);
CREATE POLICY "authenticated_read" ON team_summary FOR SELECT TO authenticated USING (true);
CREATE POLICY "service_all"        ON team_summary FOR ALL    TO service_role   USING (true);

-- ── Views ──

-- Latest row per team per period type (dedup view)
CREATE OR REPLACE VIEW team_summary_latest WITH (security_invoker = on) AS
SELECT DISTINCT ON (team, period_type) *
FROM team_summary
ORDER BY team, period_type, period_start DESC;

-- Routing views (Model A interface)
CREATE OR REPLACE VIEW tl_weekly WITH (security_invoker = on) AS
  SELECT * FROM team_summary_latest WHERE period_type = 'weekly';

CREATE OR REPLACE VIEW tl_monthly WITH (security_invoker = on) AS
  SELECT * FROM team_summary_latest WHERE period_type = 'monthly';

CREATE OR REPLACE VIEW tl_quarterly WITH (security_invoker = on) AS
  SELECT * FROM team_summary_latest WHERE period_type = 'quarterly';

CREATE OR REPLACE VIEW tl_historico WITH (security_invoker = on) AS
  SELECT * FROM team_summary;
