-- 017_rep_summary.sql
-- One row per rep per period. All 45+ metrics as typed columns.
-- Writer: stats_run() orchestrated job.
-- Key: (email, period_type, period_start) — UPSERT within a period.

CREATE TABLE IF NOT EXISTS rep_summary (
  id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  run_id            UUID NOT NULL,               -- unique per pipeline execution

  -- ── Identity (snapshot of orgchart at compute time) ──
  email             TEXT NOT NULL,
  full_name         TEXT,
  team              TEXT,
  role              TEXT,
  tl_email          TEXT,

  -- ── Period ──
  period_type       TEXT NOT NULL CHECK (period_type IN ('weekly', 'monthly', 'quarterly')),
  period_start      DATE NOT NULL,
  period_end        DATE NOT NULL,
  computed_at       TIMESTAMPTZ NOT NULL DEFAULT now(),

  -- ═══════════════════════════════════════════════════════════
  -- SEGMENT A: Closing Effectiveness
  -- Deals closed within [period_start, period_end) (half-open).
  -- NULL = zero closed deals in period (no sample to compute).
  -- ═══════════════════════════════════════════════════════════
  win_rate                  NUMERIC,          -- won / (won + lost) x 100
  avg_cycle_won             NUMERIC,          -- mean days create->close (won)
  avg_cycle_lost            NUMERIC,          -- mean days create->close (lost)
  cycle_waste_ratio         NUMERIC,          -- avg_cycle_lost / avg_cycle_won
  death_stage_distribution  JSONB,            -- {"demo_booked": 5, "contracting": 2}
  slow_deaths               NUMERIC,          -- % of losses with cycle > 2x avg_cycle_won
  weakest_meddic_at_loss    JSONB,            -- {"pillar": "DP", "avg_score": 1.2}
  loss_reason_concentration JSONB,            -- {"Timing": 40, "Competitor": 30}
  high_conf_losses          NUMERIC,          -- count of losses with prob > 50%
  comeback_wins             NUMERIC,          -- wins previously at-risk
  prob_climb_rate_won       NUMERIC,          -- mean prob increase on won deals
  stage_conversion_funnel   JSONB,            -- {"demo_booked->evaluating": 0.65}
  avg_calls_to_win          NUMERIC,
  avg_calls_to_loss         NUMERIC,
  avg_deal_size_won         NUMERIC,          -- mean MRR of won deals
  win_rate_rolling_6m       NUMERIC,          -- trailing 6m, from deals directly

  -- ═══════════════════════════════════════════════════════════
  -- SEGMENT B: Pipeline Health
  -- Live snapshot at compute time.
  -- POPULATED ONLY IN weekly ROWS. NULL in monthly/quarterly = not applicable.
  -- ═══════════════════════════════════════════════════════════
  pipeline_snapshot_at      TIMESTAMPTZ,
  active_deals_count        INT,
  pipeline_value            NUMERIC,
  avg_deal_age              NUMERIC,
  stale_deals               INT,
  stage_distribution        JSONB,            -- {"demo_booked": 5, "evaluating": 3}

  -- ═══════════════════════════════════════════════════════════
  -- SEGMENT C: Process Quality
  -- From audits within [period_start, period_end].
  -- NULL = no audits in period.
  -- ═══════════════════════════════════════════════════════════
  win_rate_score_avg             NUMERIC,
  discovery_level_avg            NUMERIC,
  lead_temperature_distribution  JSONB,       -- {"Hot": 3, "Warm": 5, "Cold": 2}
  avg_meddic_per_pillar          JSONB,       -- {"M": 4.2, "E": 3.1, "DC": 2.8, ...}
  strongest_pillar               TEXT,
  weakest_pillar                 TEXT,
  bant_completion_rate           NUMERIC,

  -- ═══════════════════════════════════════════════════════════
  -- SEGMENT D: Coaching & Gaps
  -- From audits within [period_start, period_end].
  -- NULL = no audits in period.
  -- ═══════════════════════════════════════════════════════════
  top_strengths            JSONB,             -- ["Champion access", "Discovery depth"] max 5
  top_improvement_items    JSONB,             -- ["Multi-threading", "EB identification"] max 5
  recurring_biggest_gaps   JSONB,             -- ["No next step defined"] max 5
  red_flags_frequency      NUMERIC,           -- % of audits with red flags
  dm_access_rate           NUMERIC,

  -- ═══════════════════════════════════════════════════════════
  -- SEGMENT E: Activity & Cadence
  -- From calls within [period_start, period_end].
  -- NULL = no calls in period.
  -- ═══════════════════════════════════════════════════════════
  calls_per_week           NUMERIC,
  calls_per_deal           NUMERIC,
  avg_call_duration        NUMERIC,           -- minutes

  -- ═══════════════════════════════════════════════════════════
  -- SEGMENT F: Demo Funnel
  -- From deals within [period_start, period_end].
  -- NULL = no deals in period.
  -- ═══════════════════════════════════════════════════════════
  demo_rate                NUMERIC,
  avg_days_to_demo         NUMERIC,
  post_demo_win_rate       NUMERIC,
  demo_to_close_days       NUMERIC,
  no_demo_loss_rate        NUMERIC,

  -- ═══════════════════════════════════════════════════════════
  -- SEGMENT G: Contact & Multi-threading
  -- From deals within [period_start, period_end].
  -- NULL = no deals in period.
  -- ═══════════════════════════════════════════════════════════
  avg_contacts_per_deal     NUMERIC,
  multi_thread_rate         NUMERIC,
  multi_thread_demo_rate    NUMERIC,
  contact_role_distribution JSONB,            -- {"C-Level": 2, "Manager": 5}

  -- ═══════════════════════════════════════════════════════════
  -- SEGMENT H: Segment Performance
  -- From deals within [period_start, period_end].
  -- NULL = insufficient sample for analysis.
  -- ═══════════════════════════════════════════════════════════
  sweet_spot_segment       TEXT,
  wr_by_employee_size      JSONB,             -- {"XS": 15, "S": 22, "M": 18, ...}

  -- ═══════════════════════════════════════════════════════════
  -- TARGET & CONSECUTION (rep-level)
  -- POPULATED ONLY IN monthly ROWS. Source: ae_targets (PR #43).
  -- NULL in weekly/quarterly rows = not applicable.
  -- ═══════════════════════════════════════════════════════════
  rep_target                NUMERIC,          -- from ae_targets for this rep/month
  mrr_closed_month          NUMERIC,          -- MRR won by this rep in the period
  consecution_pct           NUMERIC,          -- mrr_closed_month / rep_target x 100

  -- ═══════════════════════════════════════════════════════════
  -- SEGMENT I: Coaching Alerts
  -- Written by the alerts pass of the SAME orchestrated run.
  -- '[]'::jsonb = computed, no alerts triggered.
  -- NULL = not yet computed (alerts pass hasn't run).
  -- ═══════════════════════════════════════════════════════════
  alerts                   JSONB,

  -- ═══════════════════════════════════════════════════════════
  -- SAMPLE SIZES (for confidence and reconciliation)
  -- ═══════════════════════════════════════════════════════════
  deals_closed_count       INT NOT NULL DEFAULT 0,
  deals_won_count          INT NOT NULL DEFAULT 0,
  deals_lost_count         INT NOT NULL DEFAULT 0,
  audits_count             INT NOT NULL DEFAULT 0,
  calls_count              INT NOT NULL DEFAULT 0,

  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

  CONSTRAINT rep_summary_unique UNIQUE (email, period_type, period_start)
);

-- ── Index ──
CREATE INDEX IF NOT EXISTS idx_rep_summary_team_period
  ON rep_summary (team, period_type, period_start);

-- ── Trigger ──
DROP TRIGGER IF EXISTS trg_rep_summary_updated_at ON rep_summary;
CREATE TRIGGER trg_rep_summary_updated_at BEFORE UPDATE ON rep_summary
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ── RLS ──
ALTER TABLE rep_summary ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon_read"          ON rep_summary FOR SELECT TO anon          USING (true);
CREATE POLICY "authenticated_read" ON rep_summary FOR SELECT TO authenticated USING (true);
CREATE POLICY "service_all"        ON rep_summary FOR ALL    TO service_role   USING (true);

-- ── Views ──

-- Latest row per rep per period type (dedup view)
CREATE OR REPLACE VIEW rep_summary_latest WITH (security_invoker = on) AS
SELECT DISTINCT ON (email, period_type) *
FROM rep_summary
ORDER BY email, period_type, period_start DESC;

-- Routing views (Model A interface)
CREATE OR REPLACE VIEW rep_weekly WITH (security_invoker = on) AS
  SELECT * FROM rep_summary_latest WHERE period_type = 'weekly';

CREATE OR REPLACE VIEW rep_monthly WITH (security_invoker = on) AS
  SELECT * FROM rep_summary_latest WHERE period_type = 'monthly';

CREATE OR REPLACE VIEW rep_quarterly WITH (security_invoker = on) AS
  SELECT * FROM rep_summary_latest WHERE period_type = 'quarterly';

CREATE OR REPLACE VIEW rep_historico WITH (security_invoker = on) AS
  SELECT * FROM rep_summary;
