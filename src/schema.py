"""
Schema — el diccionario del negocio.

Define TODO lo que el sistema conoce usando "internal names" que nunca cambian.
Es el idioma propio de Closzr. Ningún código fuera de este fichero y org.py
debería conocer nombres de HubSpot, Modjo, o cualquier otro input externo.

Estructura:
  PART I   — DATA MODEL: qué existe (stages, pipelines, fields, tables, columns)
  PART II  — DERIVED SETS: agrupaciones auto-computadas (ACTIVE, WON, PBD_STAGES...)
  PART III — HELPERS: todas las funciones de acceso

Regla de oro: si cambias de CRM (HubSpot → Salesforce) o de empresa, este
fichero NO se toca. Solo se cambia org.py (input → internal name).
"""


# ══════════════════════════════════════════════════════════════════════════════
# PART I — DATA MODEL
# Qué existe en el sistema. Internal names → columnas Supabase.
# ══════════════════════════════════════════════════════════════════════════════


# ──────────────────────────────────────────────────────────────────────────────
# 1. STAGES — las fases de un deal
#
# Cada key es un internal name que el código usa siempre.
#   category — grupo funcional (prospecting/demo/evaluation/closing/won/lost...)
#   macro    — grupo visual para la UI (pipeline view agrupa por macro)
#   short    — nombre corto para tablas
#   abbr     — badge compacto (2-4 chars)
# ──────────────────────────────────────────────────────────────────────────────

STAGES = {
    # ── PROSPECTING ──
    "new":                      {"category": "prospecting", "macro": "prospecting", "short": "New",              "abbr": "NEW"},
    "new_deals":                {"category": "prospecting", "macro": "prospecting", "short": "New Deals",        "abbr": "ND"},
    "new_qualified":            {"category": "prospecting", "macro": "prospecting", "short": "New Qualified",    "abbr": "NQ"},
    "research_outreach":        {"category": "prospecting", "macro": "prospecting", "short": "Research",         "abbr": "R&O"},
    "outreach":                 {"category": "prospecting", "macro": "prospecting", "short": "Outreach",         "abbr": "OUT"},
    "pre_qualified":            {"category": "prospecting", "macro": "prospecting", "short": "Pre-qualified",    "abbr": "PQ"},
    "attempting_to_contact":    {"category": "prospecting", "macro": "prospecting", "short": "Attempting",       "abbr": "ATC"},
    "attempted_to_contact":     {"category": "prospecting", "macro": "prospecting", "short": "Attempted",        "abbr": "ATC"},
    "associating_partner":      {"category": "prospecting", "macro": "prospecting", "short": "Assoc. Partner",   "abbr": "AP"},
    "connected_not_engaged":    {"category": "prospecting", "macro": "prospecting", "short": "Connected",        "abbr": "CNE"},
    "engaged":                  {"category": "prospecting", "macro": "qualifying",  "short": "Engaged",          "abbr": "ENG"},
    "demo_request":             {"category": "prospecting", "macro": "prospecting", "short": "Demo Request",     "abbr": "DRP"},
    "opportunity_detected":     {"category": "prospecting", "macro": "prospecting", "short": "Opp. Detected",    "abbr": "OD"},

    # ── NURTURING ──
    "nurturing":                {"category": "nurturing",   "macro": "nurturing",   "short": "Nurturing",        "abbr": "NUR"},
    "sales_nurturing":          {"category": "nurturing",   "macro": "nurturing",   "short": "Sales Nurturing",  "abbr": "SN"},
    "hot_nurturing":            {"category": "nurturing",   "macro": "nurturing",   "short": "Hot Nurturing",    "abbr": "HN"},
    "long_nurturing":           {"category": "nurturing",   "macro": "nurturing",   "short": "Long Nurturing",   "abbr": "LN"},
    "on_hold":                  {"category": "nurturing",   "macro": "onhold",      "short": "On Hold",          "abbr": "Hold"},

    # ── DEMO ──
    "demo_booked":              {"category": "demo",        "macro": "demo",        "short": "Demo Booked",      "abbr": "D"},
    "meeting_booked":           {"category": "demo",        "macro": "demo",        "short": "Meeting Booked",   "abbr": "MB"},
    "meeting_scheduled":        {"category": "demo",        "macro": "demo",        "short": "Meeting Scheduled","abbr": "MS"},
    "to_reschedule":            {"category": "demo",        "macro": "demo",        "short": "To Reschedule",    "abbr": "Resch"},

    # ── EVALUATION ──
    "product_alignment":        {"category": "evaluation",  "macro": "evaluating",  "short": "Product Alignment","abbr": "PA"},
    "factorial_project_alignment": {"category": "evaluation","macro": "evaluating",  "short": "Product Alignment","abbr": "FPA"},
    "discovery":                {"category": "evaluation",  "macro": "evaluating",  "short": "Discovery",        "abbr": "DIS"},
    "meddpicc_validation":      {"category": "evaluation",  "macro": "evaluating",  "short": "MEDDPICC",         "abbr": "MCV"},

    # ── CLOSING ──
    "economical_alignment":     {"category": "closing",     "macro": "closing",     "short": "Econ. Alignment",  "abbr": "EA"},
    "pricing_packaging":        {"category": "closing",     "macro": "closing",     "short": "Pricing",          "abbr": "P&P"},
    "contract_sent":            {"category": "closing",     "macro": "closing",     "short": "Contract Sent",    "abbr": "CS"},
    "contracting":              {"category": "closing",     "macro": "closing",     "short": "Contracting",      "abbr": "CTR"},
    "contract_negotiation":     {"category": "closing",     "macro": "closing",     "short": "Contract Negot.",  "abbr": "CN"},

    # ── WON ──
    "closed_won":               {"category": "won",         "macro": "closed",      "short": "Won",              "abbr": "WON"},
    "closed_won_finance":       {"category": "won",         "macro": "closed",      "short": "Won (Finance)",    "abbr": "WON"},
    "closed_pending_payment":   {"category": "won",         "macro": "closed",      "short": "Pending Payment",  "abbr": "PP"},
    "closed_pending_validation":{"category": "won",         "macro": "closed",      "short": "Pending Valid.",   "abbr": "PFV"},

    # ── LOST ──
    "closed_lost":              {"category": "lost",        "macro": "closed",      "short": "Lost",             "abbr": "LOST"},
    "opportunity_lost":         {"category": "lost",        "macro": "closed",      "short": "Lost",             "abbr": "LOST"},

    # ── EXCLUDED ──
    "onboarding_completed":     {"category": "excluded",    "macro": "excluded",    "short": "Onboarding",       "abbr": "OB"},
    "onboarding_failed":        {"category": "excluded",    "macro": "excluded",    "short": "OB Failed",        "abbr": "OBF"},
    "churned":                  {"category": "excluded",    "macro": "excluded",    "short": "Churned",          "abbr": "CHR"},
    "retained":                 {"category": "excluded",    "macro": "excluded",    "short": "Retained",         "abbr": "RET"},
    "spam":                     {"category": "excluded",    "macro": "excluded",    "short": "Spam",             "abbr": "SPM"},
}


# ──────────────────────────────────────────────────────────────────────────────
# 2. PIPELINES — los pipelines de venta
#
#   type   — "partner" (deal via socio), "owner" (deal directo), "excluded"
#   active — si procesamos deals de este pipeline
# ──────────────────────────────────────────────────────────────────────────────

PIPELINES = {
    "partners_dist":    {"type": "partner",  "active": True},
    "sdr_partner":      {"type": "partner",  "active": True},
    "sales":            {"type": "owner",    "active": True},
    "ob_sdr":           {"type": "owner",    "active": True},
    "ib_sdr":           {"type": "owner",    "active": True},
    "xl_account":       {"type": "owner",    "active": True},
    "xl_sdr":           {"type": "owner",    "active": True},
    "it_ae":            {"type": "owner",    "active": True},
    "it_sdr":           {"type": "owner",    "active": True},
    "upselling":        {"type": "excluded", "active": False},
    "onboarding":       {"type": "excluded", "active": False},
    "churn":            {"type": "excluded", "active": False},
    "partner_acq":      {"type": "excluded", "active": False},
    "br_sdr":           {"type": "excluded", "active": False},
    "br_sales":         {"type": "excluded", "active": False},
    "consultants":      {"type": "excluded", "active": False},
    "shared":           {"type": "excluded", "active": False},
}


# ──────────────────────────────────────────────────────────────────────────────
# 3. FIELDS — columnas de la tabla deals
#
#   column  — nombre en Supabase
#   type    — text, numeric, date, datetime, boolean, json
#   persist — True si se guarda, False si solo se usa en memoria
# ──────────────────────────────────────────────────────────────────────────────

FIELDS = {
    # ── Identity ──
    "deal_uuid":            {"column": "id",                   "type": "text",     "persist": True},
    "deal_id":              {"column": "deal_id",              "type": "text",     "persist": True},
    "deal_name":            {"column": "deal_name",            "type": "text",     "persist": True},
    "stage":                {"column": "deal_stage",           "type": "text",     "persist": True},
    "pipeline":             {"column": "pipeline_name",        "type": "text",     "persist": True},
    "mrr":                  {"column": "amount",               "type": "numeric",  "persist": True},
    "close_date":           {"column": "close_date",           "type": "date",     "persist": True},
    "create_date":          {"column": "createdate",           "type": "date",     "persist": True},
    "crm_id":               {"column": "crm_id",              "type": "text",     "persist": True},

    # ── Owner / Team ──
    "pae":                  {"column": "pae",                  "type": "text",     "persist": True},
    "pbd":                  {"column": "pbd",                  "type": "text",     "persist": True},
    "team":                 {"column": "team",                 "type": "text",     "persist": True},
    "partner":              {"column": "partner",              "type": "text",     "persist": True},
    "owner_id":             {"column": "hs_owner_id",          "type": "text",     "persist": False},
    "creator_id":           {"column": "hs_created_by",        "type": "text",     "persist": False},
    "all_owner_ids":        {"column": "hs_all_owner_ids",     "type": "text",     "persist": False},
    "team_string":          {"column": "hs_team_string",       "type": "text",     "persist": False},
    "team_id":              {"column": "hs_team_id",           "type": "text",     "persist": False},

    # ── Relations ──
    "atlas_ref":            {"column": "atlas_id",             "type": "text",     "persist": True},
    "contacts_info":        {"column": "contacts_info",        "type": "json",     "persist": True},

    # ── Activity counters ──
    "contact_count":        {"column": "contact_count",        "type": "numeric",  "persist": True},
    "call_count":           {"column": "numero_de_calls",      "type": "numeric",  "persist": True},
    "email_count":          {"column": "numero_de_emails",     "type": "numeric",  "persist": True},
    "note_count":           {"column": "numero_de_notas",      "type": "numeric",  "persist": True},
    "meeting_count":        {"column": "numero_de_meetings",   "type": "numeric",  "persist": True},

    # ── Activity timestamps ──
    "last_contacted":       {"column": "last_contacted_hs",    "type": "datetime", "persist": True},
    "last_activity":        {"column": "last_activity_hs",     "type": "datetime", "persist": False},
    "last_modified":        {"column": "last_hs_modified",     "type": "datetime", "persist": True},
    "rep_next_step":        {"column": "rep_next_step",        "type": "text",     "persist": True},

    # ── Forecast ──
    "forecast_category":    {"column": "forecast_category",    "type": "text",     "persist": True},
    "rep_probability":      {"column": "rep_probability",      "type": "numeric",  "persist": True},
    "stage_probability_hs": {"column": "stage_probability_hs", "type": "numeric",  "persist": True},

    # ── Meetings ──
    "first_meeting_at":     {"column": "first_meeting_at",     "type": "datetime", "persist": True},
    "next_meeting":         {"column": "hs_next_meeting_start_time", "type": "datetime", "persist": True},

    # ── Close info ──
    "closed_lost_reason":   {"column": "closed_lost_reason",   "type": "text",     "persist": True},
    "is_closed_won":        {"column": "is_closed_won",        "type": "boolean",  "persist": False},
    "is_closed":            {"column": "is_closed",            "type": "boolean",  "persist": False},
    "closed_lost_date":     {"column": "closed_lost_date",     "type": "date",     "persist": False},
    "sqo_date":             {"column": "sqo_date",             "type": "date",     "persist": False},

    # ── Provenance ──
    "partner_name_input":   {"column": "partner_name",         "type": "text",     "persist": False},
    "campaign":             {"column": "hs_campaign",          "type": "text",     "persist": False},
    "source":               {"column": "hs_source",            "type": "text",     "persist": False},

    # ── Company size ──
    "num_employees":        {"column": "num_employees",        "type": "numeric",  "persist": False},
    "num_employees_custom": {"column": "num_employees_custom", "type": "numeric",  "persist": False},
    "champion":             {"column": "champion",             "type": "text",     "persist": False},

    # ── Activity (extended) ──
    "last_meeting":         {"column": "last_meeting_hs",      "type": "datetime", "persist": False},
    "times_contacted":      {"column": "num_times_contacted",  "type": "numeric",  "persist": False},
    "sales_activities":     {"column": "num_sales_activities", "type": "numeric",  "persist": False},

    # ── Computed ──
    "deal_age":             {"column": "deal_age_days",        "type": "numeric",  "persist": True},

    # ── Sync metadata ──
    "last_synced":          {"column": "last_synced",          "type": "datetime", "persist": True},
    "context_stale":        {"column": "context_stale",        "type": "boolean",  "persist": True},
    "stale_checked_at":     {"column": "stale_checked_at",     "type": "datetime", "persist": True},
    "deal_context":         {"column": "deal_context",         "type": "text",     "persist": True},
}


# ──────────────────────────────────────────────────────────────────────────────
# 4. TABLES — todas las tablas de Supabase
#
# upsert_key = columna(s) para on_conflict en upserts.
# ──────────────────────────────────────────────────────────────────────────────

TABLES = {
    # ── Core ──
    "deals":                {"name": "deals",                "upsert_key": "deal_id"},
    "calls":                {"name": "calls",                "upsert_key": "call_id"},
    "atlas":                {"name": "atlas",                "upsert_key": "crm_id"},

    # ── Audits ──
    "pbd_audits":           {"name": "pbd_audits",           "upsert_key": "call_ref"},
    "pae_audits":           {"name": "pae_audits",           "upsert_key": "call_ref"},

    # ── Snapshots ──
    "snapshots":            {"name": "front_deal_snapshots", "upsert_key": "hs_deal_id,snapshot_date"},
    "pbd_snapshots":        {"name": "pbd_snapshots",        "upsert_key": "hs_deal_id,snapshot_date"},

    # ── Intelligence output ──
    "deal_ui":              {"name": "deal_ui",              "upsert_key": "deal_id"},
    "product_signals":      {"name": "deal_product_signals", "upsert_key": "deal_id,snapshot_date"},
    "trajectories":         {"name": "deal_trajectories",    "upsert_key": "deal_id"},
    "analysis":             {"name": "deal_analysis",        "upsert_key": "deal_id"},
    "patterns":             {"name": "learned_patterns",     "upsert_key": "id"},
    "calibration":          {"name": "calibration_log",      "upsert_key": "id"},

    # ── Meetings ──
    "meetings":             {"name": "deal_meetings",        "upsert_key": "hs_meeting_id"},
    "calendar_meetings":    {"name": "calendar_meetings",    "upsert_key": "id"},

    # ── Communication ──
    "briefings":            {"name": "briefings",            "upsert_key": "id"},
    "email_drafts":         {"name": "email_drafts",         "upsert_key": "id"},
    "comments":             {"name": "deal_comments",        "upsert_key": "id"},

    # ── Reference ──
    "product_stats":        {"name": "product_stats",        "upsert_key": "id"},
    "slides":               {"name": "slides",               "upsert_key": "id"},
    "users":                {"name": "users",                "upsert_key": "id"},
}


# ──────────────────────────────────────────────────────────────────────────────
# 5. CALL COLS — columnas de la tabla calls
# ──────────────────────────────────────────────────────────────────────────────

CALL_COLS = {
    # ── Identity ──
    "id": "id", "call_id": "call_id", "hs_call_id": "hs_call_id",

    # ── Metadata ──
    "fecha": "fecha", "owner_email": "owner_email", "owner_nombre": "owner_nombre",
    "rol": "rol", "tags": "tags", "duracion": "duracion_segundos",
    "titulo": "titulo", "created_at": "created_at",

    # ── Content ──
    "transcript": "transcript",

    # ── Classification ──
    "team": "team", "subteam": "subteam", "source": "source",
}


# ──────────────────────────────────────────────────────────────────────────────
# 5b. GCAL EVENT COLS — output de fetch_events (consumed by meetings.py)
# ──────────────────────────────────────────────────────────────────────────────

GCAL_EVENT_COLS = {
    "gcal_event_id": "gcal_event_id",
    "title": "title",
    "meeting_start": "meeting_start",
    "meeting_end": "meeting_end",
    "attendees": "attendees",
}

GCAL_ATTENDEE_COLS = {
    "email": "email",
    "name": "name",
}


# ──────────────────────────────────────────────────────────────────────────────
# 6. AUDIT FIELDS — lo que Claude produce al auditar una call
#
# common   = todos los audits
# bant     = solo PBD
# meddic   = solo PAE
# script   = solo PBD full
# metadata = copiados de la call (no Claude)
# ──────────────────────────────────────────────────────────────────────────────

AUDIT_COMMON_COLS = [
    "win_rate_score", "forecast_flag", "partner_leverage_score",
    "lead_temperature", "discovery_level", "discovery_topics",
    "discovery_breakdown", "improvement_items_json",
    "deal_context", "deal_status", "biggest_gap",
    "next_call_objective", "tl_note", "top_coaching_flag",
    "next_action_rep", "hard_question", "objections",
    "rep_strengths", "buying_signals", "blockers", "tag_validation",
    "red_flags_fired", "slack_alert_fired",
]

AUDIT_BANT_PILLARS = ["budget", "authority", "need", "timing"]

AUDIT_MEDDIC_PILLARS = [
    "metrics", "economic_buyer", "decision_criteria",
    "decision_process", "champion", "competition",
]

AUDIT_SCRIPT_COLS = [
    "script_opener", "script_industry_pivot", "script_close", "two_slot_close",
]

AUDIT_METADATA_COLS = {
    "call_ref": "id", "call_id": "call_id", "deal_ref": "deal_id",
    "crm_id": "crm_id", "hs_deal_id": "hs_deal_id", "owner_name": "owner_nombre",
}


# ──────────────────────────────────────────────────────────────────────────────
# 7. SNAPSHOT FIELDS — lo que produce un snapshot de deal
#
# metadata   = copiados de deals (no produce Claude)
# claude_cols = producidos por Claude (MEDDIC scores, resumen, señales)
# ──────────────────────────────────────────────────────────────────────────────

SNAPSHOT_METADATA = {
    "deal_name":            "deal_name",
    "crm_id":               "crm_id",
    "deal_age":             "deal_age_days",
    "stage":                "deal_stage",
    "mrr":                  "amount",
    "hs_forecast_category": "forecast_category",
    "pbd":                  "pbd",
    "pae":                  "pae",
}

SNAPSHOT_CLAUDE_COLS = [
    "deal_summary", "deal_assessment",
    "m_accumulate", "m_score",
    "e_accumulate", "e_score",
    "dc_accumulate", "dc_score",
    "dp_accumulate", "dp_score",
    "i_accumulate", "i_score",
    "c_accumulate", "c_score",
    "comp_accumulate", "comp_score",
    "objections", "buyer_signals", "live_blockers",
    "improvements", "deal_strengths",
    "next_step", "action_signal",
    "howto_label", "howto_body",
]


# ──────────────────────────────────────────────────────────────────────────────
# 8. FORECAST FIELDS — lo que produce el forecast
#
# claude_cols     = producidos por Claude (razonamiento, momentum)
# formula_inputs  = campos raw que alimentan la fórmula Python
# computed_cols   = calculados por Python (probabilidad final)
# snapshot_inputs = qué columnas del snapshot se pasan al prompt
# trajectory_cols = qué columnas se usan para compilar trayectorias
# ──────────────────────────────────────────────────────────────────────────────

FORECAST_CLAUDE_COLS = [
    "forecast_confidence", "forecast_reasoning",
    "forecast_risks", "forecast_accelerators",
    "forecast_pushable", "push_action", "push_action_reasoning",
    "deal_momentum", "claudio_close_date", "close_date_reasoning",
]

FORECAST_FORMULA_INPUTS = ["deal_killer", "deal_killer_value", "bs", "lb"]

FORECAST_COMPUTED_COLS = ["close_probability", "claudio_forecast"]

FORECAST_SNAPSHOT_INPUTS = [
    "deal_summary", "deal_assessment",
    "m_score", "e_score", "dc_score", "dp_score",
    "i_score", "c_score", "comp_score",
    "buyer_signals", "live_blockers", "objections",
    "next_step", "action_signal",
    "forecast_confidence", "forecast_reasoning",
    "push_action", "deal_momentum",
]

TRAJECTORY_SNAPSHOT_COLS = [
    "snapshot_date", "close_probability",
    "m_score", "e_score", "dc_score", "dp_score", "i_score", "c_score", "comp_score",
    "buyer_signals", "live_blockers", "next_step", "deal_assessment", "action_signal",
]


# ──────────────────────────────────────────────────────────────────────────────
# 9. PBD SNAPSHOT FIELDS — campos BANT para snapshots PBD
# ──────────────────────────────────────────────────────────────────────────────

PBD_SNAPSHOT_COLS = [
    "bant_b_status", "bant_b_evidence",
    "bant_a_status", "bant_a_evidence",
    "bant_n_status", "bant_n_evidence",
    "bant_t_status", "bant_t_evidence",
    "pbd_summary",
]


# ──────────────────────────────────────────────────────────────────────────────
# 10. PRODUCT SIGNAL COLS — columnas de deal_product_signals
# ──────────────────────────────────────────────────────────────────────────────

PRODUCT_SIGNAL_COLS = {
    # ── Write keys ──
    "deal_id": "deal_id", "snapshot_date": "snapshot_date",

    # ── Claude output (per-call) ──
    "products_discussed": "products_discussed",
    "upsell_opportunity": "upsell_opportunity", "pitch_quality": "pitch_quality",

    # ── Claude output (cumulative, from snapshot) ──
    "product_assessment": "product_assessment",
    "product_actions": "product_actions",
    "expansion_summary": "expansion_summary",
}


# ──────────────────────────────────────────────────────────────────────────────
# 11. ATLAS COLS — columnas de la tabla atlas (company dossier)
# ──────────────────────────────────────────────────────────────────────────────

ATLAS_COLS = {
    # ── De HubSpot ──
    "company_name": "company_name", "industry": "industry",
    "company_size": "company_size", "country": "country",
    "website": "website", "description": "description",

    # ── Generados por el pipeline ──
    "company_info": "company_info", "deals_breakdown": "deals_breakdown",
    "contacts_breakdown": "contacts_breakdown", "sibling_crm_ids": "sibling_crm_ids",
    "last_generated": "last_generated",

    # ── Producidos por Claude ──
    "deal_history": "deal_history", "contacts_map": "contacts_map",
    "company_context": "company_context", "company_card": "company_card",
    "deal_insights": "deal_insights",
}


# ──────────────────────────────────────────────────────────────────────────────
# 12. TRAJECTORY COLS — columnas de deal_trajectories
#
# Writer:  daily/trajectories.py
# Readers: core/forecast.py (benchmarks), core/parser.py (deal_ui)
# ──────────────────────────────────────────────────────────────────────────────

TRAJECTORY_COLS = {
    # ── Identity ──
    "deal_id": "deal_id",

    # ── Deal metadata (copied from deals at compile time) ──
    "outcome": "outcome",
    "amount": "amount",
    "deal_age_days": "deal_age_days",
    "pae": "pae",
    "pbd": "pbd",
    "team": "team",
    "pipeline_name": "pipeline_name",
    "closed_lost_reason": "closed_lost_reason",
    "close_date": "close_date",

    # ── Compiled data ──
    "trajectory": "trajectory",
    "stage_dates": "stage_dates",
    "interactions": "interactions",

    # ── Claude output ──
    "lessons": "lessons",
    "outcome_analysis": "outcome_analysis",
    "key_turning_point": "key_turning_point",
}


# ──────────────────────────────────────────────────────────────────────────────
# 13. ANALYSIS COLS — columnas de deal_analysis
#
# Writer:  daily/deal_analysis.py
# Readers: core/parser.py (deal_ui)
# ──────────────────────────────────────────────────────────────────────────────

ANALYSIS_COLS = {
    # ── Identity ──
    "deal_id": "deal_id",
    "outcome": "outcome",

    # ── Claude output ──
    "full_narrative": "full_narrative",
    "outcome_summary": "outcome_summary",
    "deal_timeline": "deal_timeline",
    "what_worked": "what_worked",
    "what_failed": "what_failed",
    "what_could_have_changed": "what_could_have_changed",
    "rep_assessment": "rep_assessment",
    "key_people": "key_people",
    "products_pitched": "products_pitched",
    "products_missed": "products_missed",
    "product_assessment": "product_assessment",
}


# ══════════════════════════════════════════════════════════════════════════════
# PART II — DERIVED SETS
# Auto-computados de STAGES y PIPELINES. Si añades un stage nuevo con
# category="demo", entra automáticamente en DEMO sin tocar nada más.
# ══════════════════════════════════════════════════════════════════════════════


# ── Stage categories ──

_ACTIVE_CATEGORIES = frozenset({"prospecting", "nurturing", "demo", "evaluation", "closing"})

ACTIVE      = frozenset(k for k, v in STAGES.items() if v["category"] in _ACTIVE_CATEGORIES)
WON         = frozenset(k for k, v in STAGES.items() if v["category"] == "won")
LOST        = frozenset(k for k, v in STAGES.items() if v["category"] == "lost")
CLOSED      = WON | LOST
PROSPECTING = frozenset(k for k, v in STAGES.items() if v["category"] == "prospecting")
NURTURING   = frozenset(k for k, v in STAGES.items() if v["category"] == "nurturing")
DEMO        = frozenset(k for k, v in STAGES.items() if v["category"] == "demo")
EVALUATION  = frozenset(k for k, v in STAGES.items() if v["category"] == "evaluation")
CLOSING     = frozenset(k for k, v in STAGES.items() if v["category"] == "closing")
EXCLUDED    = frozenset(k for k, v in STAGES.items() if v["category"] == "excluded")

# ── Combinaciones usadas en el código ──

PBD_STAGES  = PROSPECTING | DEMO | NURTURING
ADVANCED    = EVALUATION | CLOSING
FIRST_DEMO  = DEMO
FOLLOWUP    = EVALUATION
STALLED     = frozenset({"on_hold", "to_reschedule"})
NO_SHOW     = frozenset({"to_reschedule", "on_hold", "nurturing"})

# ── Pipeline filters (para separar deals SDR vs Account en vistas) ──

ACCOUNT     = DEMO | EVALUATION | CLOSING
SDR         = PROSPECTING | NURTURING

# ── Pipeline categories ──

ACTIVE_PIPELINES   = frozenset(k for k, v in PIPELINES.items() if v["active"])
EXCLUDED_PIPELINES = frozenset(k for k, v in PIPELINES.items() if not v["active"])
PARTNER_PIPELINES  = frozenset(k for k, v in PIPELINES.items() if v["type"] == "partner")
OWNER_PIPELINES    = frozenset(k for k, v in PIPELINES.items() if v["type"] == "owner")


# ══════════════════════════════════════════════════════════════════════════════
# PART III — HELPERS
# Todas las funciones de acceso al schema. Importar desde aquí.
# ══════════════════════════════════════════════════════════════════════════════


def col(field: str) -> str:
    """Internal name → Supabase column.  col("mrr") → "amount" """
    return FIELDS[field]["column"]


def tbl(name: str) -> str:
    """Table internal name → Supabase table.  tbl("deals") → "deals" """
    return TABLES[name]["name"]


def upsert_key(name: str) -> str:
    """Table internal name → upsert conflict key."""
    return TABLES[name]["upsert_key"]


def stages_for(category: str) -> frozenset[str]:
    """Category → set of internal stage names."""
    return frozenset(k for k, v in STAGES.items() if v["category"] == category)


def is_active_stage(stage: str) -> bool:
    return stage in ACTIVE


def is_closed_stage(stage: str) -> bool:
    return stage in CLOSED


def stage_short(stage: str) -> str:
    """Internal name → display name corto.  stage_short("closed_won") → "Won" """
    return STAGES.get(stage, {}).get("short", stage)


def stage_abbr(stage: str) -> str:
    """Internal name → badge compacto.  stage_abbr("demo_booked") → "D" """
    return STAGES.get(stage, {}).get("abbr", "?")


def macro_stage(stage: str) -> str:
    """Internal name → macro stage.  macro_stage("engaged") → "qualifying" """
    return STAGES.get(stage, {}).get("macro", "unknown")


def stage_category(stage: str) -> str | None:
    """Internal name → category.  stage_category("demo_booked") → "demo" """
    return STAGES.get(stage, {}).get("category")


def field_type(field: str) -> str:
    return FIELDS[field]["type"]


def is_date_field(field: str) -> bool:
    return FIELDS.get(field, {}).get("type") in ("date", "datetime")


def persisted_fields() -> dict[str, dict]:
    """Solo los fields que se guardan en Supabase (persist=True)."""
    return {k: v for k, v in FIELDS.items() if v.get("persist", True)}
