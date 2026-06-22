-- ============================================================================
-- deal_ui — single source of truth for the UI
-- One row per deal. Every field the UI displays comes from here.
-- Updated by parser.py after each CORE phase (sync, atlas, intelligence, forecast).
-- ============================================================================

CREATE TABLE IF NOT EXISTS deal_ui (
  -- Identifiers
  deal_id              UUID PRIMARY KEY REFERENCES deals(id) ON DELETE CASCADE,
  hs_deal_id           TEXT,

  -- Header
  company_name         TEXT,
  partner_label        TEXT,
  deal_name_full       TEXT,
  stage                TEXT,
  pae                  TEXT,
  pbd                  TEXT,
  team                 TEXT,
  last_contact         DATE,
  last_contact_label   TEXT,
  hs_link              TEXT,
  mrr                  NUMERIC,
  close_probability    INTEGER,
  close_date           DATE,
  close_date_hs        DATE,
  forecast_amount      NUMERIC,
  employees            TEXT,

  -- Action card (ACCIÓN AHORA)
  action_source        TEXT,
  action_type          TEXT,
  action_headline      TEXT,
  action_headline_short TEXT,
  action_due_label     TEXT,
  action_due_date      DATE,
  action_who           TEXT,

  -- Howto (CÓMO ENFOCARLO)
  howto_label          TEXT,
  howto_body           TEXT,

  -- Deal summary
  deal_summary         TEXT,
  deal_assessment      TEXT,

  -- MEDDIC
  meddic_total         INTEGER,
  m_score              NUMERIC,
  m_text               TEXT,
  e_score              NUMERIC,
  e_text               TEXT,
  dc_score             NUMERIC,
  dc_text              TEXT,
  dp_score             NUMERIC,
  dp_text              TEXT,
  i_score              NUMERIC,
  i_text               TEXT,
  c_score              NUMERIC,
  c_text               TEXT,
  comp_score           NUMERIC,
  comp_text            TEXT,

  -- Probability
  probability_timeline JSONB DEFAULT '[]'::jsonb,
  trend                INTEGER,

  -- Blockers (snapshot — deal level)
  blockers_count       INTEGER DEFAULT 0,
  blockers             JSONB DEFAULT '[]'::jsonb,

  -- Buyer signals (snapshot — deal level)
  signals_count        INTEGER DEFAULT 0,
  signals              JSONB DEFAULT '[]'::jsonb,

  -- Stage roadmap
  stage_roadmap        JSONB DEFAULT '[]'::jsonb,

  -- Next steps (dedup vs action principal)
  next_steps           JSONB DEFAULT '[]'::jsonb,
  next_steps_total     INTEGER DEFAULT 0,
  next_steps_done      INTEGER DEFAULT 0,

  -- BANT
  bant_summary_line    TEXT,
  bant_b_status        TEXT,
  bant_b_text          TEXT,
  bant_a_status        TEXT,
  bant_a_text          TEXT,
  bant_n_status        TEXT,
  bant_n_text          TEXT,
  bant_t_status        TEXT,
  bant_t_text          TEXT,

  -- Atlas — Empresa
  atlas_company_name   TEXT,
  atlas_industry       TEXT,
  atlas_country        TEXT,
  atlas_employees      TEXT,
  atlas_revenue        TEXT,
  atlas_website        TEXT,
  atlas_description    TEXT,
  atlas_fit_level      TEXT,
  atlas_fit_text       TEXT,
  atlas_history_summary TEXT,
  atlas_warnings       JSONB DEFAULT '[]'::jsonb,

  -- Atlas — Señales, Blockers & Patrones
  atlas_signals        JSONB DEFAULT '[]'::jsonb,
  atlas_blockers       JSONB DEFAULT '[]'::jsonb,
  atlas_patterns       JSONB DEFAULT '[]'::jsonb,

  -- Atlas — Deals & Contactos
  atlas_deals          JSONB DEFAULT '[]'::jsonb,
  atlas_deals_active   INTEGER DEFAULT 0,
  atlas_deals_lost     INTEGER DEFAULT 0,
  atlas_contacts       JSONB DEFAULT '[]'::jsonb,
  atlas_contacts_count INTEGER DEFAULT 0,

  -- Forecast
  closes_this_month    BOOLEAN,
  closes_next_month    BOOLEAN,
  forecast_confidence  TEXT,
  deal_momentum        TEXT,
  momentum_arrow       TEXT,
  estimated_close_date DATE,
  forecast_reasoning   TEXT,
  push_action          TEXT,
  push_action_reasoning TEXT,
  forecast_accelerators JSONB DEFAULT '[]'::jsonb,
  forecast_risks       JSONB DEFAULT '[]'::jsonb,
  forecast_risks_count INTEGER DEFAULT 0,
  forecast_accelerators_count INTEGER DEFAULT 0,

  -- Pipeline view
  macro_stage          TEXT,
  is_stale             BOOLEAN DEFAULT FALSE,
  stale_days           INTEGER,
  score                NUMERIC,
  bucket               TEXT,
  action_priority      INTEGER DEFAULT 5,

  -- Objections
  objections           TEXT,

  -- Deal Analysis (post-mortem — solo deals cerrados)
  outcome              TEXT,
  full_narrative        TEXT,
  outcome_summary       TEXT,
  analysis_timeline     JSONB DEFAULT '[]'::jsonb,
  analysis_what_worked  JSONB DEFAULT '[]'::jsonb,
  analysis_what_failed  JSONB DEFAULT '[]'::jsonb,
  analysis_could_have_changed TEXT,
  analysis_rep_assessment TEXT,
  analysis_key_people   JSONB DEFAULT '[]'::jsonb,
  analysis_products_pitched JSONB DEFAULT '[]'::jsonb,
  analysis_products_missed JSONB DEFAULT '[]'::jsonb,
  analysis_product_assessment TEXT,

  -- Meta
  snapshot_date        DATE,
  updated_at           TIMESTAMPTZ DEFAULT now()
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_deal_ui_team ON deal_ui(team);
CREATE INDEX IF NOT EXISTS idx_deal_ui_stage ON deal_ui(macro_stage);
CREATE INDEX IF NOT EXISTS idx_deal_ui_bucket ON deal_ui(bucket);
CREATE INDEX IF NOT EXISTS idx_deal_ui_priority ON deal_ui(action_priority);
CREATE INDEX IF NOT EXISTS idx_deal_ui_stale ON deal_ui(is_stale) WHERE is_stale = TRUE;
CREATE INDEX IF NOT EXISTS idx_deal_ui_closes ON deal_ui(closes_this_month) WHERE closes_this_month = TRUE;

-- RLS
ALTER TABLE deal_ui ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon_read" ON deal_ui FOR SELECT TO anon USING (true);
CREATE POLICY "authenticated_read" ON deal_ui FOR SELECT TO authenticated USING (true);
CREATE POLICY "service_all" ON deal_ui FOR ALL TO service_role USING (true);

-- Auto-update updated_at
CREATE TRIGGER trg_deal_ui_updated_at BEFORE UPDATE ON deal_ui
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();
