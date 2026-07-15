"""
Core Parser v2 — translates pipeline outputs into UI-ready data.

Writes to deal_ui table. Each entry point updates ONLY its columns.
Pure Python — zero API calls. Called by each CORE phase after it finishes.

Entry points:
  update_from_sync(deal_uuid)         — 18 cols: stage, mrr, last_contact, outcome
  update_from_atlas(deal_uuid)        — 18 cols: company, contacts, warnings, signals
  update_from_intelligence(deal_uuid) — ~49 cols: MEDDIC, blockers, signals, actions, BANT, product
  update_from_forecast(deal_uuid)     — 17 cols + conditional action override
  update_from_daily(deal_uuid)        — 18 cols: analysis + trajectory (closed deals)

Conventions:
  - Internal names everywhere: schema.tbl(), schema.col(), config2.*
  - TODAY = date.today() inside functions, NEVER at module level (stale in long-running processes)
  - Accept deal dict as parameter when available (avoids re-fetching)
  - Each entry point does partial upsert — other columns stay untouched

Moved to frontend (NOT written by parser):
  - last_contact_label   — computed from last_contact timestamp at render time
  - is_stale             — computed from last_contact + macro_stage + STALE_THRESHOLDS
  - stale_days           — computed from last_contact
  - action_due_label     — computed from action_due_date at render time
  - deal_age_days (active) — computed from createdate at render time

Removed vs v1:
  - action_headline_short — not used in UI; frontend can truncate action_headline
  - score from intelligence — only written in forecast (avoids stale value before forecast runs)

Coaching system (v2 — prompts must generate these):
  - howto_body            — REDEFINED as sales coaching (impact + leverage, deal-specific data, coach tone)
  - push_action_reasoning — REDEFINED as coaching why for push_action
  - next_steps[].why      — NEW field inside JSON. Why this action, why now, cost of inaction
  - forecast_accelerators  — v2 JSON [{text, why}] — no more _parse_bullets()
  - forecast_risks         — v2 JSON [{text, why}] — no more _parse_bullets()

Possibly unused in UI (kept, documented for future cleanup):
  - action_source
  - atlas_deals_active
  - atlas_deals_lost
"""

import json
import re
from datetime import date, timedelta

from src import schema
from src import config2
from src.db.client import supabase


# ═══════════════════════════════════════════════════════════════════════════
# RESOLVED CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════

_TBL_DEALS    = schema.tbl("deals")
_TBL_DEAL_UI  = schema.tbl("deal_ui")
_TBL_ATLAS    = schema.tbl("atlas")
_TBL_SNAPS    = schema.tbl("snapshots")
_TBL_PBD_SNAP = schema.tbl("pbd_snapshots")
_TBL_PRODUCT  = schema.tbl("product_signals")
_TBL_ANALYSIS = schema.tbl("analysis")
_TBL_TRAJECT  = schema.tbl("trajectories")

_D_UUID       = schema.col("deal_uuid")       # "id"
_D_ID         = schema.col("deal_id")          # "deal_id"
_D_NAME       = schema.col("deal_name")        # "deal_name"
_D_STAGE      = schema.col("stage")            # "deal_stage"
_D_MRR        = schema.col("mrr")              # "amount"
_D_CLOSE      = schema.col("close_date")       # "close_date"
_D_CREATE     = schema.col("create_date")      # "createdate"
_D_TEAM       = schema.col("team")             # "team"
_D_PAE        = schema.col("pae")              # "pae"
_D_PBD        = schema.col("pbd")              # "pbd"
_D_PARTNER    = schema.col("partner")          # "partner"
_D_FCAT       = schema.col("forecast_category")# "forecast_category"
_D_LAST_CONT  = schema.col("last_contacted")   # "last_contacted_hs"
_D_CRM_ID     = schema.col("crm_id")           # "crm_id"
_D_EMPLOYEES  = schema.col("num_employees")    # "num_employees"
_D_EMP_CUSTOM = schema.col("num_employees_custom")  # "num_employees_custom"
_D_PIPELINE   = schema.col("pipeline")         # "pipeline_name"

_UPSERT_KEY = schema.upsert_key("deal_ui")     # "deal_id"

# ── Atlas table columns (schema.ATLAS_COLS) ──
_A_FK_CRM         = schema.upsert_key("atlas")                     # "crm_id" — atlas upsert key
_A_COMPANY_NAME   = schema.ATLAS_COLS["company_name"]               # "company_name"
_A_INDUSTRY       = schema.ATLAS_COLS["industry"]                   # "industry"
_A_COMPANY_SIZE   = schema.ATLAS_COLS["company_size"]               # "company_size"
_A_COUNTRY        = schema.ATLAS_COLS["country"]                    # "country"
_A_WEBSITE        = schema.ATLAS_COLS["website"]                    # "website"
_A_COMPANY_CTX    = schema.ATLAS_COLS["company_context"]            # "company_context"
_A_CONTACTS_MAP   = schema.ATLAS_COLS["contacts_map"]               # "contacts_map"
_A_CONTACTS_BK    = schema.ATLAS_COLS["contacts_breakdown"]         # "contacts_breakdown"
_A_COMPANY_CARD   = schema.ATLAS_COLS["company_card"]               # "company_card"
_A_DEAL_INSIGHTS  = schema.ATLAS_COLS["deal_insights"]              # "deal_insights"
_A_DEALS_BK       = schema.ATLAS_COLS["deals_breakdown"]            # "deals_breakdown"

# ── Snapshot table columns (schema.SNAPSHOT_IDENTITY_COLS) ──
_SNAP_ID      = schema.SNAPSHOT_IDENTITY_COLS
_S_HS_DEAL_ID = _SNAP_ID["hs_deal_id"]             # "hs_deal_id"
_S_DEAL_ID    = _SNAP_ID["deal_id"]                 # "deal_id"
_S_DATE       = _SNAP_ID["snapshot_date"]            # "snapshot_date"
_S_PROB       = "close_probability"

# ── PBD snapshot columns (schema.PBD_SNAPSHOT_COLS) ──
_PBD_HS_DEAL  = _SNAP_ID["hs_deal_id"]
_PBD_B_STATUS = "bant_b_status"
_PBD_B_EVID   = "bant_b_evidence"
_PBD_A_STATUS = "bant_a_status"
_PBD_A_EVID   = "bant_a_evidence"
_PBD_N_STATUS = "bant_n_status"
_PBD_N_EVID   = "bant_n_evidence"
_PBD_T_STATUS = "bant_t_status"
_PBD_T_EVID   = "bant_t_evidence"

# ── Product signals columns (schema.PRODUCT_SIGNAL_COLS) ──
_PS_DEAL_ID   = schema.PRODUCT_SIGNAL_COLS["deal_id"]           # "deal_id"
_PS_DATE      = schema.PRODUCT_SIGNAL_COLS["snapshot_date"]     # "snapshot_date"
_PS_ASSESS    = schema.PRODUCT_SIGNAL_COLS["product_assessment"]# "product_assessment"
_PS_ACTIONS   = schema.PRODUCT_SIGNAL_COLS["product_actions"]   # "product_actions"
_PS_EXPANSION = schema.PRODUCT_SIGNAL_COLS["expansion_summary"] # "expansion_summary"

# ── Trajectory columns (schema.TRAJECTORY_COLS) ──
_TR_DEAL_ID       = schema.TRAJECTORY_COLS["deal_id"]               # "deal_id"
_TR_TRAJECTORY    = schema.TRAJECTORY_COLS["trajectory"]            # "trajectory"
_TR_INTERACTIONS  = schema.TRAJECTORY_COLS["interactions"]          # "interactions"
_TR_LESSONS       = schema.TRAJECTORY_COLS["lessons"]               # "lessons"
_TR_CLOSED_REASON = schema.TRAJECTORY_COLS["closed_lost_reason"]    # "closed_lost_reason"
_TR_TURNING_PT    = schema.TRAJECTORY_COLS["key_turning_point"]     # "key_turning_point"
_TR_AGE_DAYS      = schema.TRAJECTORY_COLS["deal_age_days"]         # "deal_age_days"
_TR_OUTCOME       = schema.TRAJECTORY_COLS["outcome"]               # "outcome"

# ── Analysis columns (schema.ANALYSIS_COLS) ──
_AN_DEAL_ID       = schema.ANALYSIS_COLS["deal_id"]                 # "deal_id"
_AN_OUTCOME       = schema.ANALYSIS_COLS["outcome"]                 # "outcome"
_AN_NARRATIVE     = schema.ANALYSIS_COLS["full_narrative"]           # "full_narrative"
_AN_SUMMARY       = schema.ANALYSIS_COLS["outcome_summary"]         # "outcome_summary"
_AN_TIMELINE      = schema.ANALYSIS_COLS["deal_timeline"]           # "deal_timeline"
_AN_WORKED        = schema.ANALYSIS_COLS["what_worked"]             # "what_worked"
_AN_FAILED        = schema.ANALYSIS_COLS["what_failed"]             # "what_failed"
_AN_COULD_CHANGE  = schema.ANALYSIS_COLS["what_could_have_changed"] # "what_could_have_changed"
_AN_REP           = schema.ANALYSIS_COLS["rep_assessment"]          # "rep_assessment"
_AN_KEY_PEOPLE    = schema.ANALYSIS_COLS["key_people"]              # "key_people"
_AN_PROD_PITCHED  = schema.ANALYSIS_COLS["products_pitched"]        # "products_pitched"
_AN_PROD_MISSED   = schema.ANALYSIS_COLS["products_missed"]         # "products_missed"
_AN_PROD_ASSESS   = schema.ANALYSIS_COLS["product_assessment"]      # "product_assessment"

# ── Snapshot column names (for select / get on fetched rows) ──
# These are the actual Supabase column names in front_deal_snapshots.
# Intelligence reads (from SNAPSHOT_CLAUDE_COLS)
_SC_SUMMARY      = "deal_summary"
_SC_ASSESSMENT   = "deal_assessment"
_SC_OBJECTIONS   = "objections"
_SC_SIGNALS      = "buyer_signals"
_SC_BLOCKERS     = "live_blockers"
_SC_NEXT_STEP    = "next_step"
_SC_ACTION_SIG   = "action_signal"
_SC_HOWTO_LABEL  = "howto_label"
_SC_HOWTO_BODY   = "howto_body"

# MEDDIC score/accumulate pattern: f"{dim}_score", f"{dim}_accumulate"
_SC_MEDDIC_DIMS  = ["m", "e", "dc", "dp", "i", "c", "comp"]

# Forecast reads
_SC_CLOSE_DATE   = "claudio_close_date"
_SC_CONFIDENCE   = "forecast_confidence"
_SC_MOMENTUM     = "deal_momentum"
_SC_PUSH_ACTION  = "push_action"
_SC_PUSH_REASON  = "push_action_reasoning"
_SC_REASONING_V1 = "forecast_reasoning"
_SC_ACCEL_V1     = "forecast_accelerators"
_SC_RISKS_V1     = "forecast_risks"
_SC_ACCEL_V2     = "accelerators"
_SC_RISKS_V2     = "risk_factors"
_SC_REASONING_V2 = "reasoning"

# Stage date column pairs for roadmap — (display_label, entered_col, exited_col)
# Ordered by pipeline and progression. Only stages with entered date are shown.
_STAGE_DATE_PAIRS = [
    # SDR Partner Opportunities Pipeline
    ("Pre-qualified",          "sdr_prequalified_entered",          "sdr_prequalified_exited"),
    ("Attempting to contact",  "sdr_attempting_to_contact_entered", "sdr_attempting_to_contact_exited"),
    ("Engaged",                "sdr_engaged_entered",               "sdr_engaged_exited"),
    ("Demo Booked",            "sdr_demo_booked_entered",           "sdr_demo_booked_exited"),
    # Partners Distribution Pipeline
    ("New Deals",              "dist_new_deals_entered",            "dist_new_deals_exited"),
    ("Demo Booked",            "dist_demo_booked_entered",          "dist_demo_booked_exited"),
    ("Product Alignment",      "dist_product_alignment_entered",    "dist_product_alignment_exited"),
    ("MEDDPICC",               "dist_meddpicc_validation_entered",  "dist_meddpicc_validation_exited"),
    ("Pricing & Packaging",    "dist_pricing_and_packaging_entered", "dist_pricing_and_packaging_exited"),
    ("Contracting",            "dist_contracting_entered",          "dist_contracting_exited"),
    # Sales Pipeline
    ("Meeting Booked",         "sales_meeting_booked_entered",      "sales_meeting_booked_exited"),
    ("Discovery",              "sales_discovery_entered",           "sales_discovery_exited"),
    ("Product Alignment",      "sales_product_alignment_entered",   "sales_product_alignment_exited"),
    ("Pricing & Packaging",    "sales_pricing_and_packaging_entered", "sales_pricing_and_packaging_exited"),
    ("Contracting",            "sales_contracting_entered",         "sales_contracting_exited"),
    # OB SDR Pipeline
    ("New",                    "ob_new_entered",                    "ob_new_exited"),
    ("Research & Outreach",    "ob_research_outreach_entered",      "ob_research_outreach_exited"),
    ("Engaged",                "ob_engaged_entered",                "ob_engaged_exited"),
    ("Meeting Booked",         "ob_meeting_booked_entered",         "ob_meeting_booked_exited"),
    # IB SDR Pipeline
    ("New Qualified",          "ib_new_qualified_entered",          "ib_new_qualified_exited"),
    ("Attempted to contact",   "ib_attempted_contact_entered",      "ib_attempted_contact_exited"),
    ("Engaged",                "ib_engaged_entered",                "ib_engaged_exited"),
    ("Meeting Booked",         "ib_meeting_booked_entered",         "ib_meeting_booked_exited"),
    # XL Account Pipeline
    ("New",                    "xl_new_entered",                    "xl_new_exited"),
    ("Outreach",               "xl_outreach_entered",               "xl_outreach_exited"),
    ("Engaged",                "xl_engaged_entered",                "xl_engaged_exited"),
    ("Meeting Booked",         "xl_meeting_booked_entered",         "xl_meeting_booked_exited"),
    ("Discovery",              "xl_discovery_entered",              "xl_discovery_exited"),
    ("Product Alignment",      "xl_product_alignment_entered",      "xl_product_alignment_exited"),
    ("Pricing & Packaging",    "xl_pricing_packaging_entered",      "xl_pricing_packaging_exited"),
    ("Contracting",            "xl_contracting_entered",            "xl_contracting_exited"),
    # XL SDR Pipeline
    ("New",                    "xlsdr_new_entered",                 "xlsdr_new_exited"),
    ("Research & Outreach",    "xlsdr_research_outreach_entered",   "xlsdr_research_outreach_exited"),
    ("Engaged",                "xlsdr_engaged_entered",             "xlsdr_engaged_exited"),
    ("Meeting Booked",         "xlsdr_meeting_booked_entered",      "xlsdr_meeting_booked_exited"),
    # IT AE Pipeline
    ("New",                    "itae_new_entered",                  "itae_new_exited"),
    ("Outreach",               "itae_outreach_entered",             "itae_outreach_exited"),
    ("Engaged",                "itae_engaged_entered",              "itae_engaged_exited"),
    ("Meeting Booked",         "itae_meeting_booked_entered",       "itae_meeting_booked_exited"),
    ("Discovery",              "itae_discovery_entered",            "itae_discovery_exited"),
    ("Product Alignment",      "itae_product_alignment_entered",    "itae_product_alignment_exited"),
    ("Pricing & Packaging",    "itae_pricing_packaging_entered",    "itae_pricing_packaging_exited"),
    ("Contracting",            "itae_contracting_entered",          "itae_contracting_exited"),
    # IT SDR Pipeline
    ("New",                    "itsdr_new_entered",                 "itsdr_new_exited"),
    ("Research & Outreach",    "itsdr_research_outreach_entered",   "itsdr_research_outreach_exited"),
    ("Engaged",                "itsdr_engaged_entered",             "itsdr_engaged_exited"),
    ("Meeting Booked",         "itsdr_meeting_booked_entered",      "itsdr_meeting_booked_exited"),
]


# ═══════════════════════════════════════════════════════════════════════════
# TEXT HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _safe_int(v):
    """Convert to int safely. None → None."""
    if v is None:
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


def _parse_action_type(text: str) -> str:
    """Detect action type from text tags/keywords.

    IN:  "[CALL] María → Llamar al CFO para cerrar presupuesto"
    OUT: "CALL"

    IN:  "Enviar propuesta de pricing al director de RRHH"
    OUT: "EMAIL"

    IN:  "Preparar business case con ROI estimado"
    OUT: "ROI"

    Fallback: "PREP" (generic preparation task)
    """
    upper = text.upper()
    lower = text.lower()
    for action_type, keywords in config2.ACTION_TAGS.items():
        for kw in keywords:
            if kw.startswith("[") and kw in upper:
                return action_type
            elif not kw.startswith("[") and kw in lower:
                return action_type
    return config2.ACTION_DEFAULT_TYPE


def _parse_who_and_text(raw: str) -> tuple[str, str]:
    """Extract who + action text from raw action string.

    IN:  "[CALL] María → Llamar al CFO para cerrar presupuesto — viernes 18/07"
    OUT: ("María", "Llamar al CFO para cerrar presupuesto — viernes 18/07")

    IN:  "Enviar propuesta de pricing al director de RRHH"
    OUT: ("", "Enviar propuesta de pricing al director de RRHH")
    """
    clean = re.sub(r"\[(?:CALL|EMAIL|ROI|SLIDES|BATTLECARD)\]\s*", "", raw).strip()
    clean = re.sub(r"^[•\-\d.]\s*", "", clean).strip()
    arrow = clean.find("→")
    if 0 < arrow < 30:
        who = clean[:arrow].strip()
        text = clean[arrow + 1:].strip()
        if text:
            text = text[0].upper() + text[1:]
        return who, text
    return "", clean[0].upper() + clean[1:] if clean else ""


def _resolve_due_date(text: str, ref: date) -> date:
    """Parse due date from action text. Multilingual (ES/EN/IT/DE).

    IN:  "Llamar al CFO — viernes 18/07", ref=2026-07-14
    OUT: date(2026, 7, 18)

    IN:  "Enviar email mañana", ref=2026-07-14
    OUT: date(2026, 7, 15)

    IN:  "Follow up next week", ref=2026-07-14
    OUT: date(2026, 7, 20)  — next Monday

    Fallback: ref + DEFAULT_FOLLOWUP_DAYS (3 days)
    """
    t = text.lower()

    # Explicit date: "18/07" or "18/07/2026" or "18-07"
    explicit = re.search(r"(\d{1,2})[/\-](\d{1,2})(?:[/\-](\d{2,4}))?", t)
    if explicit:
        day, month = int(explicit.group(1)), int(explicit.group(2))
        year = int(explicit.group(3)) if explicit.group(3) else ref.year
        if year < 100:
            year += 2000
        try:
            return date(year, month, day)
        except ValueError:
            pass

    # "15 de julio"
    month_match = re.search(r"(\d{1,2}) de (\w+)", t)
    if month_match:
        day = int(month_match.group(1))
        month_num = config2.MONTH_NAMES.get(month_match.group(2).lower())
        if month_num:
            try:
                return date(ref.year, month_num, day)
            except ValueError:
                pass

    # Relative keywords
    if "hoy" in t or "ahora" in t or "inmediatamente" in t or "today" in t:
        return ref
    if "mañana" in t or "tomorrow" in t:
        return ref + timedelta(days=1)

    # Named day: "lunes", "viernes"
    for name, weekday in config2.DAY_NAMES.items():
        if name in t:
            days_ahead = weekday - ref.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            return ref + timedelta(days=days_ahead)

    # "esta semana" → Friday
    if "esta semana" in t or "this week" in t:
        d = 4 - ref.weekday()
        return ref + timedelta(days=d if d >= 0 else d + 7)

    # "próxima semana" → next Monday
    if "próxima semana" in t or "semana que viene" in t or "next week" in t:
        return ref + timedelta(days=7 - ref.weekday())

    return ref + timedelta(days=config2.DEFAULT_FOLLOWUP_DAYS)


def _absolutize_text(text: str, ref: date) -> str:
    """Replace relative dates in text with absolute dates.

    IN:  "Llamar hoy para cerrar", ref=2026-07-14
    OUT: "Llamar lunes 14/07 para cerrar"

    IN:  "Enviar propuesta mañana", ref=2026-07-14
    OUT: "Enviar propuesta martes 15/07"
    """
    result = text

    def _fmt(d: date) -> str:
        names = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
        return f"{names[d.weekday()]} {d.day:02d}/{d.month:02d}"

    result = re.sub(r'\bhoy\b', _fmt(ref), result, flags=re.IGNORECASE)
    result = re.sub(r'\bmañana\b', _fmt(ref + timedelta(days=1)), result, flags=re.IGNORECASE)

    d2f = 4 - ref.weekday()
    if d2f < 0:
        d2f += 7
    fri = ref + timedelta(days=d2f)
    result = re.sub(r'\besta semana\b', f"antes del viernes {fri.day:02d}/{fri.month:02d}", result, flags=re.IGNORECASE)

    nm = ref + timedelta(days=7 - ref.weekday())
    result = re.sub(r'\bpróxima semana\b', f"semana del lunes {nm.day:02d}/{nm.month:02d}", result, flags=re.IGNORECASE)
    result = re.sub(r'\bsemana que viene\b', f"semana del lunes {nm.day:02d}/{nm.month:02d}", result, flags=re.IGNORECASE)

    for name, weekday in config2.DAY_NAMES.items():
        pattern = rf'\b{name}\b(?!\s+\d)'
        da = weekday - ref.weekday()
        if da <= 0:
            da += 7
        target = ref + timedelta(days=da)
        result = re.sub(pattern, f"{name} {target.day:02d}/{target.month:02d}", result, flags=re.IGNORECASE)

    return result


def _parse_bullets(text) -> list[str]:
    """Parse bullet-point text into clean string list.

    IN:  "• Champion no responde desde hace 2 semanas\n• Presupuesto bloqueado por CFO"
    OUT: ["Champion no responde desde hace 2 semanas", "Presupuesto bloqueado por CFO"]

    IN:  ["risk one", "risk two"]  (already a list)
    OUT: ["risk one", "risk two"]

    IN:  '["a","b"]'  (JSON string)
    OUT: ["a", "b"]
    """
    if not text:
        return []
    if isinstance(text, list):
        return [re.sub(r"^[•\-\d.]\s*", "", str(s)).strip() for s in text if str(s).strip() and len(str(s).strip()) > 3]
    text = str(text)
    if text.strip().startswith("["):
        try:
            items = json.loads(text)
            if isinstance(items, list):
                return [re.sub(r"^[•\-\d.]\s*", "", str(s)).strip() for s in items if str(s).strip() and len(str(s).strip()) > 3]
        except (json.JSONDecodeError, TypeError):
            pass
    return [s.strip() for s in re.split(r"[\n•\-*]", text) if s.strip() and len(s.strip()) > 3]


def _parse_next_steps(next_step, ref: date) -> list[dict]:
    """Parse next_step text into structured array.

    v1 IN (text): "• [CALL] María → Llamar al CFO para cerrar presupuesto — viernes 18/07\n• [EMAIL] Rep → Enviar case study de sector retail"
    v1 OUT: [
        {"order": 1, "type": "CALL", "who": "María", "text": "Llamar al CFO...", "due_date": "2026-07-18"},
        {"order": 2, "type": "EMAIL", "who": "Rep", "text": "Enviar case study...", "due_date": "2026-07-17"}
    ]

    v2 IN (JSON array from prompt): [{"tag": "CALL", "who": "María", "action": "...", "when": "...", "why": "..."}]
    v2 OUT: same structure with why field included

    Max: MAX_NEXT_STEPS (5)
    """
    if not next_step:
        return []

    # v2: if intelligence generates JSON array, parse directly
    if isinstance(next_step, list):
        result = []
        for i, ns in enumerate(next_step[:config2.MAX_NEXT_STEPS]):
            if isinstance(ns, dict):
                text = ns.get("action") or ns.get("text") or ""
                text = _absolutize_text(text, ref)
                due_raw = ns.get("when") or ""
                due = _resolve_due_date(due_raw or text, ref)
                result.append({
                    "order": i + 1,
                    "type": ns.get("tag") or _parse_action_type(text),
                    "who": ns.get("who") or "",
                    "text": text,
                    "why": ns.get("why") or "",
                    "due_date": due.isoformat(),
                })
            else:
                line = str(ns).strip()
                if len(line) < 5:
                    continue
                action_type = _parse_action_type(line)
                who, text = _parse_who_and_text(line)
                due = _resolve_due_date(line, ref)
                text = _absolutize_text(text, ref)
                result.append({
                    "order": len(result) + 1,
                    "type": action_type,
                    "who": who,
                    "text": text,
                    "why": "",
                    "due_date": due.isoformat(),
                })
        return result

    # v2: JSON string
    if isinstance(next_step, str) and next_step.strip().startswith("["):
        try:
            parsed = json.loads(next_step)
            if isinstance(parsed, list):
                return _parse_next_steps(parsed, ref)
        except (json.JSONDecodeError, TypeError):
            pass

    # v1: newline-separated bullet text
    result = []
    for line in str(next_step).split("\n"):
        line = re.sub(r"^[•\-]\s*", "", line.strip())
        if not line or len(line) < 5:
            continue
        action_type = _parse_action_type(line)
        who, text = _parse_who_and_text(line)
        due = _resolve_due_date(line, ref)
        text = _absolutize_text(text, ref)
        result.append({
            "order": len(result) + 1,
            "type": action_type,
            "who": who,
            "text": text,
            "why": "",
            "due_date": due.isoformat(),
        })
    return result[:config2.MAX_NEXT_STEPS]


def _parse_json_safe(raw, default=None):
    """Parse JSON from string or passthrough if already parsed.

    IN:  '{"fit": {"score": "alto"}}'   → {"fit": {"score": "alto"}}
    IN:  {"fit": {"score": "alto"}}     → {"fit": {"score": "alto"}} (passthrough)
    IN:  None                           → default
    """
    if raw is None:
        return default
    if isinstance(raw, (dict, list)):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return default
    return default


def _ensure_json_string(raw, default="[]"):
    """Ensure value is a JSON string, serializing if needed.

    IN:  [{"text": "a"}]           → '[{"text": "a"}]'
    IN:  '{"key": "val"}'         → '{"key": "val"}' (passthrough)
    IN:  None                      → default
    """
    if raw is None:
        return default
    if isinstance(raw, str):
        return raw
    return json.dumps(raw, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════════════════
# DB HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _fetch_deal(deal_uuid: str) -> dict | None:
    """Fetch deal from deals table by UUID."""
    resp = supabase.table(_TBL_DEALS).select("*").eq(_D_UUID, deal_uuid).limit(1).execute()
    return resp.data[0] if resp.data else None


def _upsert(deal_uuid: str, row: dict):
    """Partial upsert to deal_ui. Only writes non-None fields."""
    row["deal_id"] = deal_uuid
    row = {k: v for k, v in row.items() if v is not None}
    supabase.table(_TBL_DEAL_UI).upsert(row, on_conflict=_UPSERT_KEY).execute()


# ═══════════════════════════════════════════════════════════════════════════
# ENTRY POINT 1: SYNC — metadata from deals table
#
# Source: deals table (synced from HubSpot)
# Trigger: after sync phase in core/run.py, daily/run.py, backfill/run.py
# Writes: 18 columns
# ═══════════════════════════════════════════════════════════════════════════

def _build_sync_row(deal: dict) -> dict | None:
    """Build deal_ui row from a deals-table record. Pure logic, no DB calls."""
    deal_uuid = deal.get(_D_UUID)
    if not deal_uuid:
        return None

    deal_name  = deal.get(_D_NAME) or ""
    stage      = deal.get(_D_STAGE) or ""
    team       = deal.get(_D_TEAM) or ""
    hs_deal_id = deal.get(_D_ID) or ""
    mrr        = float(deal.get(_D_MRR) or 0)

    macro = schema.macro_stage(stage)

    row = {
        "deal_id": deal_uuid,
        "hs_deal_id": hs_deal_id,
        "company_name": deal_name,
        "partner_label": deal.get(_D_PARTNER) or "",
        "deal_name_full": deal_name,
        "stage": stage,
        "pae": deal.get(_D_PAE) or "",
        "pbd": deal.get(_D_PBD) or "",
        "team": team,
        "last_contact": deal.get(_D_LAST_CONT),
        "hs_link": f"{config2.HUBSPOT_APP_URL}/contacts/{hs_deal_id}" if hs_deal_id else None,
        "mrr": deal.get(_D_MRR),
        "close_date_hs": deal.get(_D_CLOSE),
        "forecast_category": deal.get(_D_FCAT) or "",
        "macro_stage": macro,
        "employees": str(deal.get(_D_EMPLOYEES) or deal.get(_D_EMP_CUSTOM) or ""),
        "atlas_revenue": str(int(mrr * 12)) if mrr else "0",
        "createdate": deal.get(_D_CREATE),
        "pipeline_name": deal.get(_D_PIPELINE) or "",
    }

    if stage in schema.WON:
        row["outcome"] = "won"
    elif stage in schema.LOST:
        row["outcome"] = "lost"

    return row


def update_from_sync(deal_uuid: str, deal: dict | None = None):
    """Write deal metadata from deals table to deal_ui."""
    if deal is None:
        deal = _fetch_deal(deal_uuid)
    if not deal:
        return
    row = _build_sync_row(deal)
    if row:
        _upsert(deal_uuid, row)


def update_batch_from_sync(deal_uuids: list[str] | None = None) -> int:
    """Batch update deal_ui from deals table.
    If deal_uuids is None, processes ALL deals.
    Returns number of rows written."""
    if deal_uuids is not None:
        all_deals = []
        for i in range(0, len(deal_uuids), 200):
            batch = deal_uuids[i:i + 200]
            resp = supabase.table(_TBL_DEALS).select("*").in_(_D_UUID, batch).execute()
            all_deals.extend(resp.data or [])
    else:
        all_deals = []
        offset = 0
        while True:
            resp = (
                supabase.table(_TBL_DEALS)
                .select("*")
                .range(offset, offset + 999)
                .execute()
            )
            batch = resp.data or []
            all_deals.extend(batch)
            if len(batch) < 1000:
                break
            offset += 1000

    rows = []
    for deal in all_deals:
        row = _build_sync_row(deal)
        if row:
            rows.append(row)

    for i in range(0, len(rows), 500):
        batch = rows[i:i + 500]
        supabase.table(_TBL_DEAL_UI).upsert(batch, on_conflict=_UPSERT_KEY).execute()

    return len(rows)


# ═══════════════════════════════════════════════════════════════════════════
# ENTRY POINT 2: ATLAS — company intelligence
#
# Source: atlas table (company dossier generated by atlas pipeline)
# Trigger: after atlas phase in core/run.py, backfill/run.py
# Writes: 18 columns
# ═══════════════════════════════════════════════════════════════════════════

def update_from_atlas(deal_uuid: str, deal: dict | None = None):
    """Write company intelligence from atlas table to deal_ui.

    Columns written (18):
      atlas_company_name, atlas_industry, atlas_country, atlas_employees,
      atlas_website, atlas_description, atlas_contacts, atlas_contacts_count,
      employees, atlas_fit_level, atlas_fit_text, atlas_history_summary,
      atlas_warnings, atlas_signals, atlas_blockers, atlas_patterns,
      atlas_deals_active, atlas_deals_lost
    """
    if deal is None:
        deal = _fetch_deal(deal_uuid)
    if not deal:
        return
    crm_id = deal.get(_D_CRM_ID)
    if not crm_id:
        return

    atlas = (
        supabase.table(_TBL_ATLAS)
        .select("*")
        .eq(_A_FK_CRM, crm_id)
        .maybe_single()
        .execute()
    )
    if not atlas.data:
        return
    a = atlas.data

    # ── Contacts parsing ──
    # Try contacts_map (JSON array), fallback to contacts_breakdown (text)
    # IN:  contacts_map = [{"name": "Ana García", "role": "CFO", "in_deal": true, "email": "ana@acme.com"}, ...]
    # OUT: [{"name": "Ana García", "role": "CFO", "initials": "AG", "in_deal": true, "email": "ana@acme.com"}, ...]
    contacts = []
    contacts_raw = _parse_json_safe(a.get(_A_CONTACTS_MAP))
    if isinstance(contacts_raw, list):
        for c in contacts_raw[:20]:
            name = c.get("name") or "—"
            initials = "".join(w[0] for w in name.split()[:2]).upper() if name != "—" else "?"
            contacts.append({
                "name": name,
                "role": c.get("role") or c.get("title") or "—",
                "initials": initials,
                "in_deal": c.get("in_deal", False),
                "email": c.get("email") or "",
            })

    # Fallback: parse contacts_breakdown text
    # IN:  "- Ana García\n  Cargo: CFO\n  Email: ana@acme.com\n- Pedro López\n  Cargo: CTO"
    # OUT: [{"name": "Ana García", "role": "CFO", "initials": "AG", "email": "ana@acme.com"}, ...]
    if not contacts:
        breakdown = a.get(_A_CONTACTS_BK) or ""
        if breakdown:
            for block in re.split(r'\n\s*-\s+', breakdown):
                if not block.strip():
                    continue
                lines = block.strip().split('\n')
                name = lines[0].strip().rstrip(' -')
                role = ""
                email = ""
                for line in lines[1:]:
                    if 'cargo:' in line.lower() or 'role:' in line.lower():
                        role = line.split(':', 1)[-1].strip()
                    elif 'email:' in line.lower():
                        email = line.split(':', 1)[-1].strip()
                if name:
                    initials = "".join(w[0] for w in name.split()[:2]).upper()
                    contacts.append({"name": name, "role": role, "initials": initials, "email": email})

    row = {
        # #A1 atlas_company_name — real company name (frontend prefers this over company_name)
        # IN: atlas.company_name = "Acme Corporation S.L."  →  OUT: "Acme Corporation S.L."
        "atlas_company_name": a.get(_A_COMPANY_NAME) or "",

        # #A2 atlas_industry
        # IN: atlas.industry = "Technology"  →  OUT: "Technology"
        "atlas_industry": a.get(_A_INDUSTRY) or "",

        # #A3 atlas_country
        # IN: atlas.country = "Spain"  →  OUT: "Spain"
        "atlas_country": a.get(_A_COUNTRY) or "",

        # #A4 atlas_employees — company size from atlas (more reliable than HubSpot)
        # IN: atlas.company_size = 250  →  OUT: "250"
        "atlas_employees": str(a.get(_A_COMPANY_SIZE) or ""),

        # #A5 atlas_website
        # IN: atlas.website = "https://acme.com"  →  OUT: "https://acme.com"
        "atlas_website": a.get(_A_WEBSITE) or "",

        # #A6 atlas_description — executive synthesis generated by Claude in atlas pipeline
        # IN: atlas.company_context = "Empresa de 250 empleados en sector retail..."
        # OUT: "Empresa de 250 empleados en sector retail..."
        "atlas_description": a.get(_A_COMPANY_CTX) or "",

        # #A7 atlas_contacts — contact cards array
        # OUT: '[{"name":"Ana García","role":"CFO","initials":"AG","in_deal":true,"email":"ana@acme.com"}]'
        "atlas_contacts": json.dumps(contacts, ensure_ascii=False),

        # #A8 atlas_contacts_count — ALL contacts (in_deal true + false)
        # Frontend filters in_deal for deal-specific count
        "atlas_contacts_count": _safe_int(len(contacts)),

        # #A9 employees — overwrites sync provisional value with atlas data
        "employees": str(a.get(_A_COMPANY_SIZE) or ""),
    }

    # ── company_card: fit, history_summary, warnings ──
    # IN: atlas.company_card = {"fit": {"score": "alto", "reason": "Encaja por tamaño..."}, "history_summary": "3 deals en 2 años", "warnings": ["CRM duplicado"]}
    company_card = _parse_json_safe(a.get(_A_COMPANY_CARD), {})
    if isinstance(company_card, dict):
        fit = company_card.get("fit") or {}

        # #A10 atlas_fit_level
        # IN: fit.score = "alto"  →  OUT: "alto"
        row["atlas_fit_level"] = fit.get("score") or "Fit por validar"

        # #A11 atlas_fit_text
        # IN: fit.reason = "Empresa de 250 empleados, sector retail, pain claro en nóminas"
        # OUT: "Empresa de 250 empleados, sector retail, pain claro en nóminas"
        row["atlas_fit_text"] = fit.get("reason") or ""

        # #A12 atlas_history_summary
        # IN: "3 deals en 2 años, 1 ganado (€800/mes), 1 perdido por precio, 1 activo"
        # OUT: same
        row["atlas_history_summary"] = company_card.get("history_summary") or ""

        # #A13 atlas_warnings — CRM anomalies, naming issues. Max 5.
        # IN: ["CRM duplicado (crm_123, crm_456)", "Deal name mismatch"]
        # OUT: '["CRM duplicado (crm_123, crm_456)", "Deal name mismatch"]'
        row["atlas_warnings"] = json.dumps(company_card.get("warnings") or [], ensure_ascii=False)

    # ── deal_insights: buying_signals, blockers, patterns ──
    # IN: atlas.deal_insights = {"buying_signals": [{"signal": "Piloto aprobado", "source": "deal_456"}], "blockers": [...], "patterns": [...]}
    deal_insights = _parse_json_safe(a.get(_A_DEAL_INSIGHTS), {})
    if isinstance(deal_insights, dict):
        # #A14 atlas_signals — cross-deal buying signals
        # IN: [{"signal": "Piloto aprobado", "source": "deal_456", "strength": "Fuerte"}]
        # OUT: same as JSON string
        row["atlas_signals"] = json.dumps(deal_insights.get("buying_signals") or [], ensure_ascii=False)

        # #A15 atlas_blockers — cross-deal historical blockers
        # IN: [{"blocker": "Legal siempre bloquea en contracting", "source": "deal_123", "severity": "high"}]
        # OUT: same as JSON string
        row["atlas_blockers"] = json.dumps(deal_insights.get("blockers") or [], ensure_ascii=False)

        # #A16 atlas_patterns — cross-deal recurring patterns
        # IN: ["Siempre piden piloto antes de firmar", "Decisión final en comité trimestral"]
        # OUT: same as JSON string
        row["atlas_patterns"] = json.dumps(deal_insights.get("patterns") or [], ensure_ascii=False)

    # #A17-A18 atlas_deals_active / atlas_deals_lost — from deals_breakdown text
    # IN: "Deal A - activo - €500/mes\nDeal B - closedlost - precio\nDeal C - activo - €300/mes"
    # OUT: atlas_deals_active=2, atlas_deals_lost=1
    # NOTE: possibly unused in UI. Fragile text counting.
    deals_text = a.get(_A_DEALS_BK) or ""
    if deals_text:
        lower_text = deals_text.lower()
        active_count = lower_text.count("activo") + lower_text.count("open")
        lost_count = lower_text.count("perdido") + lower_text.count("closedlost") + lower_text.count("closed lost")
        row["atlas_deals_active"] = _safe_int(active_count)
        row["atlas_deals_lost"] = _safe_int(lost_count)

    _upsert(deal_uuid, row)


# ═══════════════════════════════════════════════════════════════════════════
# ENTRY POINT 3: INTELLIGENCE — snapshot + BANT + product
#
# Source: front_deal_snapshots, pbd_snapshots, deal_product_signals
# Trigger: after intelligence phase in core/run.py, daily/run.py, backfill/run.py
# Writes: ~49 columns
# ═══════════════════════════════════════════════════════════════════════════

def update_from_intelligence(deal_uuid: str, deal: dict | None = None):
    """Write intelligence snapshot data to deal_ui.

    Columns written (~49):
      snapshot_date, deal_summary, deal_assessment,
      meddic_total, m/e/dc/dp/i/c/comp _score + _text (14),
      blockers_count, blockers, signals_count, signals, objections,
      howto_label, howto_body,
      action_source, action_type, action_headline, action_signal,
      action_due_date, action_who,
      next_steps, next_steps_total, next_steps_done,
      probability_timeline, trend, stage_roadmap,
      bant_summary_line + 4× (status + text) (9),
      product_assessment, product_actions, expansion_summary
    """
    today = date.today()

    if deal is None:
        deal = _fetch_deal(deal_uuid)
    if not deal:
        return
    hs_deal_id = deal.get(_D_ID) or ""

    # Fetch latest snapshot
    snap = (
        supabase.table(_TBL_SNAPS)
        .select("*")
        .eq(_S_HS_DEAL_ID, hs_deal_id)
        .order(_S_DATE, desc=True)
        .limit(1)
        .execute()
    )
    if not snap.data:
        return
    s = snap.data[0]

    snap_date_str = s.get(_S_DATE) or today.isoformat()
    try:
        snap_dt = date.fromisoformat(str(snap_date_str))
    except ValueError:
        snap_dt = today

    # ── MEDDIC scores ──
    # IN: s.m_score=8, s.e_score=6, s.dc_score=7, s.dp_score=5, s.i_score=4, s.c_score=9, s.comp_score=3
    # OUT: meddic_total = 42 (rounded sum of all 7 scores, each 0-10)
    scores = {k: float(s.get(f"{k}_score") or 0) for k in ["m", "e", "dc", "dp", "i", "c", "comp"]}
    meddic_total = round(sum(scores.values()))

    # ── Blockers ──
    # IN: s.live_blockers = "• Champion no responde\n• Presupuesto congelado por CFO"
    # OUT: blockers_list = ["Champion no responde", "Presupuesto congelado por CFO"]
    blockers_list = _parse_bullets(s.get(_SC_BLOCKERS))

    # ── Signals ──
    # IN: s.buyer_signals = "• CEO mencionó pain en nóminas\n• Pidieron piloto para julio"
    # OUT: signals_list = ["CEO mencionó pain en nóminas", "Pidieron piloto para julio"]
    signals_list = _parse_bullets(s.get(_SC_SIGNALS))

    # ── Next steps ──
    # IN: s.next_step = "• [CALL] María → Llamar CFO — viernes 18/07\n• [EMAIL] Rep → Enviar ROI"
    # OUT: [{order:1, type:"CALL", who:"María", text:"Llamar CFO...", due_date:"2026-07-18"}, ...]
    next_steps = _parse_next_steps(s.get(_SC_NEXT_STEP), snap_dt)

    # ── Action cascade: push_action > action_signal > first next_step ──
    # Determines which action is the primary "to-do" for the rep.
    # push_action comes from forecast (highest priority) but is evaluated in update_from_forecast.
    # Here we only use snapshot's action_signal or next_steps.
    action_signal_raw = _absolutize_text((s.get(_SC_ACTION_SIG) or "").strip(), snap_dt)

    if action_signal_raw:
        # Source: intelligence snapshot's action_signal
        # IN: "Llamar al CFO mañana para desbloquear presupuesto"
        # OUT: action_source="snapshot", action_headline="Llamar al CFO martes 15/07 para desbloquear presupuesto"
        action_source = "snapshot"
        action_raw = action_signal_raw
    elif next_steps:
        # Source: first next_step
        # IN: next_steps[0] = {type: "CALL", who: "María", text: "Llamar CFO..."}
        # OUT: action_source="next_step", action_headline="Llamar CFO..."
        action_source = "next_step"
        ns = next_steps[0]
        action_raw = f"[{ns['type']}] {ns['who']} → {ns['text']}" if ns['who'] else ns['text']
    else:
        action_source = ""
        action_raw = ""

    if action_raw:
        action_type = _parse_action_type(action_raw)
        who, headline = _parse_who_and_text(action_raw)
        headline = _absolutize_text(headline, snap_dt)
        due = _resolve_due_date(action_raw, snap_dt)
        if not who:
            who = deal.get(_D_PAE) or deal.get(_D_PBD) or "Rep"
    else:
        action_type = ""
        who = ""
        headline = ""
        due = today

    # Dedup: remove first next_step if it duplicates the action headline
    if next_steps and action_source != "next_step":
        first_text = next_steps[0].get("text", "").lower()[:50]
        if first_text and first_text in headline.lower():
            next_steps = next_steps[1:]
            for i, ns in enumerate(next_steps):
                ns["order"] = i + 1

    # ── Probability timeline (all snapshots for this deal) ──
    # IN: all snapshots for deal_uuid with close_probability
    # OUT: [{"date": "2026-06-01", "prob": 45}, {"date": "2026-07-01", "prob": 62}]
    hist_resp = (
        supabase.table(_TBL_SNAPS)
        .select(f"{_S_DATE}, {_S_PROB}")
        .eq(_S_DEAL_ID, deal_uuid)
        .order(_S_DATE)
        .execute()
    )
    timeline = [
        {"date": h[_S_DATE], "prob": h.get(_S_PROB) or 0}
        for h in (hist_resp.data or [])
        if h.get(_S_PROB) is not None
    ]

    # ── Trend: delta between last 2 probabilities ──
    # IN: timeline = [..., {prob: 45}, {prob: 62}]  →  OUT: trend = 17
    # IN: timeline = [{prob: 62}]                    →  OUT: trend = None
    prev_prob = timeline[-2]["prob"] if len(timeline) >= 2 else None
    curr_prob = s.get(_S_PROB)
    trend = (curr_prob - prev_prob) if curr_prob is not None and prev_prob is not None else None

    # ── Stage roadmap ──
    stage_roadmap = _build_stage_roadmap(deal, today)

    row = {
        # #I1 snapshot_date
        # IN: "2026-07-14"  →  OUT: "2026-07-14"
        "snapshot_date": snap_date_str,

        # #I2 deal_summary
        # IN: "Deal en fase de pricing con 3 productos. MRR €1500. Champion activo."
        "deal_summary": s.get(_SC_SUMMARY) or "",

        # #I3 deal_assessment — 3 sentences: situation → blocker/accelerator → next action
        # IN: "Deal avanza bien en pricing. Principal riesgo: CFO no ha validado presupuesto. Siguiente: cerrar reunión con CFO esta semana."
        "deal_assessment": s.get(_SC_ASSESSMENT) or "",

        # #I4 meddic_total — sum of 7 MEDDIC scores (0-70)
        "meddic_total": _safe_int(meddic_total),

        # #I5-I18 MEDDIC scores + evidence text
        # IN: m_score=8, m_accumulate="Pain claro en nóminas, 3 conversaciones lo confirman"
        # OUT: m_score=8, m_text="Pain claro en nóminas, 3 conversaciones lo confirman"
        **{f"{d}_score": _safe_int(scores[d]) for d in _SC_MEDDIC_DIMS},
        **{f"{d}_text": s.get(f"{d}_accumulate") or "" for d in _SC_MEDDIC_DIMS},

        # #I19 blockers_count
        "blockers_count": len(blockers_list),

        # #I20 blockers — JSON array of {text}
        # IN: ["Champion no responde", "Presupuesto congelado"]
        # OUT: '[{"text":"Champion no responde"},{"text":"Presupuesto congelado"}]'
        "blockers": json.dumps([{"text": b} for b in blockers_list], ensure_ascii=False),

        # #I21 signals_count
        "signals_count": _safe_int(len(signals_list)),

        # #I22 signals — JSON array of {text, strength}
        # NOTE: strength heuristic is useless (always "Moderada"). TODO: intelligence should generate it or remove.
        # IN: ["CEO mencionó pain en nóminas"]
        # OUT: '[{"text":"CEO mencionó pain en nóminas","strength":"Moderada"}]'
        "signals": json.dumps(
            [{"text": si, "strength": "Fuerte" if "fuerte" in si.lower() else "Moderada"} for si in signals_list],
            ensure_ascii=False
        ),

        # #I23 objections
        # IN: "Precio alto vs competencia, dudan del soporte en italiano"
        "objections": s.get(_SC_OBJECTIONS) or "",

        # #I24 howto_label — situation headline, 5-6 words
        # IN: "Desbloquear acceso al decisor"
        "howto_label": s.get(_SC_HOWTO_LABEL) or "",

        # #I25 howto_body — v2: sales coaching (impact + leverage, deal-specific data)
        # IN: "El CFO de Acme (María López) no ha validado el presupuesto de €18K ARR. Contactar vía el champion (Pedro) que tiene reunión interna el jueves 17/07. Sin validación antes del 25/07, el deal se enfría y perdemos el ciclo de compra Q3."
        "howto_body": s.get(_SC_HOWTO_BODY) or "",

        # #I26 action_source — origin of main action. Possibly unused in UI.
        # OUT: "snapshot" or "next_step" or "" (or "forecast" — set by update_from_forecast)
        "action_source": action_source,

        # #I27 action_type — category for icons/badges
        # OUT: "CALL" or "EMAIL" or "ROI" or "SLIDES" or "BATTLECARD" or "PREP"
        "action_type": action_type,

        # #I28 action_headline — main action display (tags removed, who extracted, dates absolutized)
        # IN: "[CALL] María → Llamar al CFO mañana"
        # OUT: "Llamar al CFO martes 15/07"
        "action_headline": headline,

        # #I29 action_signal — raw action from intelligence (may differ from headline if forecast wins cascade)
        # IN: "Llamar al CFO para desbloquear presupuesto — esta semana"
        # OUT: "Llamar al CFO para desbloquear presupuesto — antes del viernes 18/07"
        "action_signal": action_signal_raw,

        # #I30 action_due_date — action deadline (ISO date). Used for overdue tracking in future hourly system.
        # IN: "Llamar al CFO — viernes 18/07"  →  OUT: "2026-07-18"
        "action_due_date": due.isoformat(),

        # #I31 action_who — who should execute. Extracted from "Name →" or fallback to PAE/PBD.
        # IN: "[CALL] María → Llamar CFO"  →  OUT: "María"
        # IN: "Enviar email al CFO" (no →)  →  OUT: "maria.garcia@factorial.co" (PAE fallback)
        "action_who": who,

        # #I32 next_steps — structured next actions
        # v1 OUT: '[{"order":1,"type":"CALL","who":"María","text":"Llamar CFO","due_date":"2026-07-18"}]'
        # v2 OUT: '[{"order":1,"type":"CALL","who":"María","text":"Llamar CFO","why":"CFO es el decisor final y no ha visto la propuesta","due_date":"2026-07-18"}]'
        "next_steps": json.dumps(next_steps, ensure_ascii=False),

        # #I33 next_steps_total
        "next_steps_total": _safe_int(len(next_steps)),

        # #I34 next_steps_done — PENDING: always 0. Needs completion tracking for hourly alerts.
        "next_steps_done": 0,

        # #I35 probability_timeline — probability evolution chart
        # OUT: '[{"date":"2026-06-01","prob":45},{"date":"2026-07-01","prob":62}]'
        "probability_timeline": json.dumps(timeline, ensure_ascii=False),

        # #I36 trend — probability delta between last 2 snapshots
        # IN: prev=45, curr=62  →  OUT: 17
        "trend": _safe_int(trend),

        # #I37 stage_roadmap — visual stage progression bar
        # OUT: '[{"stage":"Demo Booked","entered":"2026-05-01","exited":"2026-05-15","duration_days":14,"done":true,"current":false}]'
        "stage_roadmap": json.dumps(stage_roadmap, ensure_ascii=False),
    }

    # ── BANT (from pbd_snapshots) — 9 columns ──
    # IN: pbd_snapshots row with bant_b_status="confirmed", bant_b_evidence="Presupuesto de €50K aprobado"
    # OUT: bant_summary_line="B: confirmed · A: partially_confirmed · N: confirmed · T: not_discussed"
    pbd_snap = (
        supabase.table(_TBL_PBD_SNAP)
        .select("*")
        .eq(_S_HS_DEAL_ID, hs_deal_id)
        .order(_S_DATE, desc=True)
        .limit(1)
        .execute()
    )
    if pbd_snap.data:
        b = pbd_snap.data[0]
        statuses = {
            "B": b.get(_PBD_B_STATUS) or "Missing",
            "A": b.get(_PBD_A_STATUS) or "Missing",
            "N": b.get(_PBD_N_STATUS) or "Missing",
            "T": b.get(_PBD_T_STATUS) or "Missing",
        }
        row["bant_summary_line"] = " · ".join(f"{k}: {v}" for k, v in statuses.items())
        row["bant_b_status"] = statuses["B"]
        row["bant_b_text"] = b.get(_PBD_B_EVID) or ""
        row["bant_a_status"] = statuses["A"]
        row["bant_a_text"] = b.get(_PBD_A_EVID) or ""
        row["bant_n_status"] = statuses["N"]
        row["bant_n_text"] = b.get(_PBD_N_EVID) or ""
        row["bant_t_status"] = statuses["T"]
        row["bant_t_text"] = b.get(_PBD_T_EVID) or ""

    # ── Product intel (from deal_product_signals) ──
    pi = (
        supabase.table(_TBL_PRODUCT)
        .select(f"{_PS_ASSESS}, {_PS_ACTIONS}, {_PS_EXPANSION}")
        .eq(_PS_DEAL_ID, deal_uuid)
        .order(_PS_DATE, desc=True)
        .limit(1)
        .execute()
    )
    if pi.data:
        p = pi.data[0]
        # #I47 product_assessment — product strategy analysis
        # IN: "Cliente usa nóminas y tiempo. Oportunidad clara en gastos (€200/mes adicional). Factorial Expenses encaja con su pain de control de gastos."
        if p.get(_PS_ASSESS):
            row["product_assessment"] = p[_PS_ASSESS]

        # #I48 product_actions — actionable product recommendations
        # IN: [{"type": "upsell", "text": "Presentar Expenses", "how": "Usar caso de éxito retail"}]
        # or string
        if p.get(_PS_ACTIONS):
            row["product_actions"] = _ensure_json_string(p[_PS_ACTIONS])

        # #I49 expansion_summary
        # IN: "2 productos, €200/mes. Benchmark: 3.7 productos, €604/mes. Gap: +1.7, +€404"
        if p.get(_PS_EXPANSION):
            row["expansion_summary"] = p[_PS_EXPANSION]

    _upsert(deal_uuid, row)


# ═══════════════════════════════════════════════════════════════════════════
# ENTRY POINT 4: FORECAST — probability, timing, push_action
#
# Source: front_deal_snapshots (latest, after forecast2 writes to it)
# Trigger: after forecast phase in core/run.py, daily/run.py, backfill/run.py
# Writes: 17 columns + conditional action override (5 more when push_action exists)
# ═══════════════════════════════════════════════════════════════════════════

def update_from_forecast(deal_uuid: str, deal: dict | None = None):
    """Write forecast data to deal_ui.

    Columns written (17):
      close_probability, close_date, forecast_amount, forecast_confidence,
      deal_momentum, momentum_arrow, estimated_close_date, forecast_reasoning,
      push_action, push_action_reasoning, forecast_accelerators, forecast_risks,
      forecast_risks_count, forecast_accelerators_count, bucket,
      action_priority, score

    Conditional override (when push_action exists, 5 cols):
      action_source, action_type, action_headline, action_due_date, action_who
    """
    today = date.today()

    if deal is None:
        deal = _fetch_deal(deal_uuid)
    if not deal:
        return
    hs_deal_id = deal.get(_D_ID) or ""
    mrr = float(deal.get(_D_MRR) or 0)

    # Select v1 columns (always present). v2 columns (reasoning, accelerators, risk_factors)
    # may not exist yet — we try them separately and fall back to v1.
    snap = (
        supabase.table(_TBL_SNAPS)
        .select(
            f"{_S_PROB}, {_SC_CLOSE_DATE}, "
            f"{_SC_CONFIDENCE}, {_SC_MOMENTUM}, "
            f"{_SC_PUSH_ACTION}, {_SC_PUSH_REASON}, "
            f"{_SC_REASONING_V1}, {_SC_ACCEL_V1}, {_SC_RISKS_V1}"
        )
        .eq(_S_HS_DEAL_ID, hs_deal_id)
        .order(_S_DATE, desc=True)
        .limit(1)
        .execute()
    )
    if not snap.data:
        return
    s = snap.data[0]

    prob = s.get(_S_PROB) or 0
    momentum = s.get(_SC_MOMENTUM) or ""
    claudio_close = s.get(_SC_CLOSE_DATE) or ""

    # ── Bucket computation from claudio_close_date ──
    # Determines TodoView grouping and priority color badges
    # IN: claudio_close = "2026-07-25", prob = 65  →  OUT: bucket = "forecast" (closes this month)
    # IN: claudio_close = "2026-08-15"              →  OUT: bucket = "next_month"
    # IN: claudio_close = "", push_action exists     →  OUT: bucket = "pushable"
    closes_this_month = False
    closes_next_month = False
    if claudio_close:
        try:
            close_d = date.fromisoformat(str(claudio_close)[:10])
            eom = (today.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
            closes_this_month = close_d <= eom
            if not closes_this_month:
                next_eom = (eom + timedelta(days=1)).replace(day=28) + timedelta(days=4)
                next_eom = next_eom.replace(day=1) - timedelta(days=1)
                closes_next_month = close_d <= next_eom
        except (ValueError, TypeError):
            pass

    # ── Accelerators and risks ──
    # v2: columns "accelerators"/"risk_factors" are JSON arrays [{text, why}]
    # v1: columns "forecast_accelerators"/"forecast_risks" are text bullets
    # Try v2 first, fall back to v1 parsing
    accel_v2 = _parse_json_safe(s.get(_SC_ACCEL_V2))
    accel_v1 = _parse_json_safe(s.get(_SC_ACCEL_V1))
    if isinstance(accel_v2, list) and accel_v2:
        accel_items = accel_v2[:3]
    elif isinstance(accel_v1, list) and accel_v1:
        accel_items = accel_v1[:3]
    else:
        accel_raw = _parse_bullets(s.get(_SC_ACCEL_V1))[:3]
        accel_items = [{"text": a} for a in accel_raw]

    risks_v2 = _parse_json_safe(s.get(_SC_RISKS_V2))
    risks_v1 = _parse_json_safe(s.get(_SC_RISKS_V1))
    if isinstance(risks_v2, list) and risks_v2:
        risk_items = risks_v2[:3]
    elif isinstance(risks_v1, list) and risks_v1:
        risk_items = risks_v1[:3]
    else:
        risks_raw = _parse_bullets(s.get(_SC_RISKS_V1))[:3]
        risk_items = [{"text": r} for r in risks_raw]

    pushable = bool(s.get(_SC_PUSH_ACTION))

    if closes_this_month:
        bucket = "forecast"
    elif pushable:
        bucket = "pushable"
    elif closes_next_month:
        bucket = "next_month"
    elif risk_items:
        bucket = "blocker"
    else:
        bucket = "pipeline"

    # Priority for TodoView sort order
    # forecast=1 (highest urgency) → pushable=2 → next_month=3 → blocker=4 → pipeline=5
    priority_map = {"forecast": 1, "pushable": 2, "next_month": 3, "blocker": 4, "pipeline": 5}
    priority = priority_map.get(bucket, 5)

    # ── Reasoning: v2 will have single "reasoning" column, v1 has "forecast_reasoning" ──
    # When v2 column exists: s.get("reasoning") or s.get("forecast_reasoning")
    reasoning = s.get(_SC_REASONING_V1) or ""

    row = {
        # #F1 close_probability — deal probability (0-100)
        # IN: 65  →  OUT: 65
        "close_probability": _safe_int(prob),

        # #F2 close_date — Claudio predicted close date
        # IN: "2026-08-15"  →  OUT: "2026-08-15"
        "close_date": claudio_close or None,

        # #F3 forecast_amount — weighted MRR = (probability/100) × MRR
        # IN: prob=65, mrr=1500  →  OUT: 975.0
        "forecast_amount": round((prob / 100) * mrr, 2) if mrr else None,

        # #F4 forecast_confidence
        # IN: "high"  →  OUT: "high"
        "forecast_confidence": s.get(_SC_CONFIDENCE) or "",

        # #F5 deal_momentum
        # IN: "accelerating"  →  OUT: "accelerating"
        "deal_momentum": momentum,

        # #F6 momentum_arrow — visual indicator
        # IN: "accelerating"  →  OUT: "▲"
        # IN: "stalled"       →  OUT: "▼"
        "momentum_arrow": config2.MOMENTUM_ARROWS.get(momentum, ""),

        # #F7 estimated_close_date — DUPLICATE of close_date (F2). Kept for backwards compat.
        # Both columns contain claudio_close_date from forecast2.
        "estimated_close_date": s.get(_SC_CLOSE_DATE),

        # #F8 forecast_reasoning — v2: single merged reasoning field
        # IN: "Deal avanza bien. MEDDIC 42/70, champion activo. Riesgo: CFO de vacaciones en agosto. Close date ajustado a septiembre."
        "forecast_reasoning": reasoning,

        # #F9 push_action — most impactful action from forecast. If present, WINS action cascade.
        # IN: "María → Llamar al CFO antes del viernes para cerrar presupuesto Q3"
        "push_action": s.get(_SC_PUSH_ACTION) or "",

        # #F10 push_action_reasoning — v2: coaching why for push_action
        # IN: "El CFO tiene presupuesto Q3 aprobado (€50K) pero no ha visto la propuesta. Si no lo contactas antes del viernes 18/07, pierde prioridad frente a la renovación de SAP que revisan el lunes 21/07."
        "push_action_reasoning": s.get(_SC_PUSH_REASON) or "",

        # #F11 forecast_accelerators — v2: JSON array [{text, why}], max 3
        # IN: [{"text":"Cerrar reunión con CFO","why":"Es el decisor final y tiene presupuesto Q3"}]
        # OUT: '[{"text":"Cerrar reunión con CFO","why":"Es el decisor final y tiene presupuesto Q3"}]'
        "forecast_accelerators": json.dumps(accel_items, ensure_ascii=False),

        # #F12 forecast_risks — v2: JSON array [{text, why}], max 3
        # IN: [{"text":"CFO de vacaciones en agosto","why":"Sin firma antes del 25/07, deal se para 3 semanas"}]
        "forecast_risks": json.dumps(risk_items, ensure_ascii=False),

        # #F13-F14 counts
        "forecast_risks_count": _safe_int(len(risk_items)),
        "forecast_accelerators_count": _safe_int(len(accel_items)),

        # #F15 bucket — TodoView grouping
        # OUT: "forecast" | "pushable" | "next_month" | "blocker" | "pipeline"
        "bucket": bucket,

        # #F16 action_priority — sort order (1=highest urgency)
        "action_priority": _safe_int(priority),

        # #F17 score — deal score for display (0.0-5.0)
        # IN: prob=65  →  OUT: round((65/20)*10)/10 = 3.2
        # Only written here, NOT in intelligence (avoids stale value before forecast runs)
        "score": round((prob / config2.SCORE_DIVISOR) * 10) / 10 if prob else None,
    }

    # ── Conditional action override: when push_action exists, it wins the cascade ──
    # Forecast's push_action overwrites intelligence's action_signal/next_step as primary action
    push_raw = (s.get(_SC_PUSH_ACTION) or "").strip()
    if push_raw:
        action_type = _parse_action_type(push_raw)
        who, headline = _parse_who_and_text(push_raw)
        headline = _absolutize_text(headline, today)
        due = _resolve_due_date(push_raw, today)
        if not who:
            who = deal.get(_D_PAE) or deal.get(_D_PBD) or "Rep"

        row["action_source"] = "forecast"
        row["action_type"] = action_type
        row["action_headline"] = headline
        row["action_due_date"] = due.isoformat()
        row["action_who"] = who

    _upsert(deal_uuid, row)


# ═══════════════════════════════════════════════════════════════════════════
# ENTRY POINT 5: DAILY — deal analysis + trajectory (closed deals)
#
# Source: deal_analysis, deal_trajectories
# Trigger: after closed deal detection in daily/run.py
# Writes: 18 columns
# ═══════════════════════════════════════════════════════════════════════════

def update_from_daily(deal_uuid: str):
    """Write deal analysis + trajectory data to deal_ui. For closed deals.

    Columns written (18):
      outcome, full_narrative, outcome_summary,
      analysis_timeline, analysis_what_worked, analysis_what_failed,
      analysis_could_have_changed, analysis_rep_assessment,
      analysis_key_people, analysis_products_pitched, analysis_products_missed,
      analysis_product_assessment,
      trajectory, interactions, lessons, closed_lost_reason,
      key_turning_point, deal_age_days
    """
    row = {}

    # ── Deal analysis ──
    analysis_resp = (
        supabase.table(_TBL_ANALYSIS)
        .select("*")
        .eq(_AN_DEAL_ID, deal_uuid)
        .maybe_single()
        .execute()
    )
    if analysis_resp and analysis_resp.data:
        a = analysis_resp.data
        row.update({
            # #D1 outcome — "won" or "lost" (confirms sync value)
            "outcome": a.get(_AN_OUTCOME) or "",

            # #D2 full_narrative — full deal narrative post-mortem
            # IN: "Acme Corp contactó vía Santander en mayo 2026. El PBD (Carlos) cualificó rápido: pain claro en nóminas..."
            "full_narrative": a.get(_AN_NARRATIVE) or "",

            # #D3 outcome_summary — short summary of why won/lost
            # IN: "Ganado por fit perfecto en nóminas y champion fuerte. CFO convenció al comité tras ver ROI de 3.2x."
            "outcome_summary": a.get(_AN_SUMMARY) or "",

            # #D4 analysis_timeline — array of deal events
            # IN: [{"date":"2026-05-01","event":"Primer contacto via Santander"},{"date":"2026-06-15","event":"Demo con CEO"}]
            "analysis_timeline": _ensure_json_string(a.get(_AN_TIMELINE), "[]"),

            # #D5 analysis_what_worked
            # IN: ["Champion fuerte que facilitó acceso al CEO", "ROI presentado con datos del sector"]
            "analysis_what_worked": _ensure_json_string(a.get(_AN_WORKED), "[]"),

            # #D6 analysis_what_failed
            # IN: ["Pricing tardó 2 semanas en prepararse", "No se contactó al CFO hasta semana 6"]
            "analysis_what_failed": _ensure_json_string(a.get(_AN_FAILED), "[]"),

            # #D7 analysis_could_have_changed
            # IN: "Contactar al CFO en semana 3 habría acortado el ciclo 2 semanas"
            "analysis_could_have_changed": a.get(_AN_COULD_CHANGE) or "",

            # #D8 analysis_rep_assessment
            # IN: "Buen discovery, excelente relationship building. Mejorable: tardó en escalar a EB."
            "analysis_rep_assessment": a.get(_AN_REP) or "",

            # #D9 analysis_key_people
            # IN: [{"name":"Ana García","role":"CFO","impact":"Decisor final, aprobó presupuesto"}]
            "analysis_key_people": _ensure_json_string(a.get(_AN_KEY_PEOPLE), "[]"),

            # #D10 analysis_products_pitched
            # IN: ["Nóminas","Tiempo","Gastos"]
            "analysis_products_pitched": _ensure_json_string(a.get(_AN_PROD_PITCHED), "[]"),

            # #D11 analysis_products_missed
            # IN: ["Documentos","Recruiting"]
            "analysis_products_missed": _ensure_json_string(a.get(_AN_PROD_MISSED), "[]"),

            # #D12 analysis_product_assessment
            # IN: "Vendió 3 de 5 productos posibles. Gastos fue clave para cerrar. Recruiting no se mencionó."
            "analysis_product_assessment": a.get(_AN_PROD_ASSESS) or "",
        })

    # ── Trajectory ──
    traj_resp = (
        supabase.table(_TBL_TRAJECT)
        .select("*")
        .eq(_TR_DEAL_ID, deal_uuid)
        .maybe_single()
        .execute()
    )
    if traj_resp and traj_resp.data:
        t = traj_resp.data
        row.update({
            # #D13 trajectory — snapshot evolution over time
            # IN: [{"date":"2026-06-01","prob":30,"stage":"demo_booked"},{"date":"2026-07-01","prob":65,"stage":"pricing"}]
            "trajectory": _ensure_json_string(t.get(_TR_TRAJECTORY), "[]"),

            # #D14 interactions — interaction summary object
            # IN: {"calls":12,"emails":8,"meetings":4,"total_duration_min":340}
            "interactions": _ensure_json_string(t.get(_TR_INTERACTIONS), "{}"),

            # #D15 lessons — lessons learned
            # IN: ["Champion temprano acelera el deal","ROI con datos del sector convence al CFO"]
            "lessons": _ensure_json_string(t.get(_TR_LESSONS), "[]"),

            # #D16 closed_lost_reason
            # IN: "Precio demasiado alto vs competidor local"
            "closed_lost_reason": t.get(_TR_CLOSED_REASON) or "",

            # #D17 key_turning_point
            # IN: "Reunión con CEO el 15/06 donde se presentó el ROI de 3.2x"
            "key_turning_point": t.get(_TR_TURNING_PT) or "",

            # #D18 deal_age_days — days from creation to close
            # IN: 67  →  OUT: 67
            "deal_age_days": _safe_int(t.get(_TR_AGE_DAYS)),
        })
        if not row.get("outcome"):
            row["outcome"] = t.get(_TR_OUTCOME) or ""

    if row:
        _upsert(deal_uuid, row)


# ═══════════════════════════════════════════════════════════════════════════
# STAGE ROADMAP BUILDER
# ═══════════════════════════════════════════════════════════════════════════

def _build_stage_roadmap(deal: dict, today: date) -> list[dict]:
    """Build visual stage progression from deal's stage date columns.

    Reads entered/exited timestamps for each stage, computes duration,
    marks current stage. Only stages with an entered date are included.

    OUT: [
        {"stage": "Demo Booked",      "entered": "2026-05-01", "exited": "2026-05-15", "duration_days": 14, "done": true,  "current": false},
        {"stage": "Product Alignment", "entered": "2026-05-15", "exited": null,         "duration_days": null, "done": false, "current": true},
    ]
    """
    current_stage = deal.get(_D_STAGE) or ""
    roadmap = []
    seen_stages = set()

    for stage_label, entered_col, exited_col in _STAGE_DATE_PAIRS:
        entered = deal.get(entered_col)
        if not entered:
            continue
        if stage_label in seen_stages:
            continue
        seen_stages.add(stage_label)

        exited = deal.get(exited_col)
        entered_str = str(entered)[:10]
        exited_str = str(exited)[:10] if exited else None

        duration = None
        if exited:
            try:
                d1 = date.fromisoformat(entered_str)
                d2 = date.fromisoformat(exited_str)
                duration = (d2 - d1).days
            except (ValueError, TypeError):
                pass

        is_current = stage_label == current_stage or (not exited and stage_label in current_stage)

        roadmap.append({
            "stage": stage_label,
            "entered": entered_str,
            "exited": exited_str,
            "duration_days": duration,
            "done": exited is not None,
            "current": is_current,
        })

    # If current stage has no date data, add it as a placeholder
    if current_stage and current_stage not in seen_stages:
        roadmap.append({
            "stage": current_stage,
            "entered": today.isoformat(),
            "exited": None,
            "duration_days": None,
            "done": False,
            "current": True,
        })

    return roadmap
