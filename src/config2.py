"""
config2.py — Behavior, thresholds, and operational rules.

This file answers HOW the system processes, not WHAT exists (schema.py)
or WHERE data comes from (org.py).

Structure:
  PART I   — MODELS & PATHS (Claude model IDs, prompt directories)
  PART II  — THRESHOLDS (limits, batch sizes, timeouts, retries, max_tokens)
  PART III — PROMPT ROUTING (which prompt file for each pipeline stage)
  PART IV  — SCORING RULES (MEDDIC weights, stale thresholds, score math)
  PART V   — EB ALERTS (trigger rules, classifications)
  PART VI  — CONTEXT RULES (regex patterns, cooldowns, exclusions)
  PART VII — CADENCE CONFIG (hourly/daily/weekly/monthly run parameters)
  PART VIII— DERIVED SETS (computed from org at import time)
  PART IX  — HELPERS (resolve email → team/role/channel/lang)
"""

from pathlib import Path
from zoneinfo import ZoneInfo

from src import org


# ══════════════════════════════════════════════════════════════════════════════
# PART I — MODELS & PATHS
# ══════════════════════════════════════════════════════════════════════════════

ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"
PROMPTS_DIR = ROOT_DIR / "prompts"

MODEL_SONNET = "claudio-claude-sonnet-4-6"
MODEL_OPUS = "claudio-claude-opus-4-6"
MODEL_DEFAULT = MODEL_SONNET

MODEL_GPT_55 = "claudio-gpt-5.5"
MODEL_GPT_54_MINI = "claudio-gpt-5.4-mini"


# ══════════════════════════════════════════════════════════════════════════════
# PART II — THRESHOLDS
# ══════════════════════════════════════════════════════════════════════════════

# ── Pipeline limits ──
MAX_DEALS_PER_CYCLE = 100
CORE_TIMEOUT_MINUTES = 55
CORE_WORKERS = 3
UPSERT_BATCH_SIZE = 500

# ── Transcript ──
MIN_TRANSCRIPT_LENGTH = 100
MIN_TRANSCRIPT_FOR_AUDIT = 200
TRANSCRIPT_TIMEOUT_HOURS = 48

# ── Domain / meeting ──
MAX_DEALS_PER_DOMAIN = 5
CALENDAR_CLEANUP_DAYS = 7
DEMO_EXIT_DATE_TOLERANCE_DAYS = 3

# ── Pipeline review ──
MIN_PIPELINE_REVIEW_PROBABILITY = 46
MRR_TOP_DEAL_THRESHOLD = 3000

# ── HubSpot API ──
HUBSPOT_APP_URL = "https://app.hubspot.com"
HUBSPOT_MIN_REQUEST_INTERVAL = 0.2
HUBSPOT_MAX_RETRIES = 5
HUBSPOT_RETRYABLE_CODES = {401, 429, 500, 502, 503}
HUBSPOT_REQUEST_TIMEOUT = 30

# ── Claude API ──
CLAUDE_MAX_RETRIES = 3
CLAUDE_DEFAULT_MAX_TOKENS = 16000
CLAUDE_RETRY_BACKOFF_BASE = 10

# ── Modjo API ──
MAX_MODJO_WORKERS = 2
MODJO_RATE_LIMIT_WAIT = 310
MODJO_LOOKBACK_HOURS = 2
MODJO_MAX_RETRIES = 5
MODJO_REQUEST_TIMEOUT = 60

# ── Google Calendar ──
GCAL_MAX_RESULTS = 50

# ── Intelligence ──
MIN_TRAJECTORIES_FOR_PATTERNS = 10

# ── Max tokens per task ──
MAX_TOKENS = {
    "audit":              16000,
    "snapshot":           16000,
    "forecast_v1":        2000,
    "forecast_v2":        2000,
    "pbd_bant":           16000,
    "atlas":              16000,
    "briefing":           4000,
    "email_draft":        4000,
    "eb_analyze":         1000,
    "eb_classify":        400,
    "eb_coaching":        200,
    "followup":           12000,
    "followup_classify":  500,
    "trajectory_lessons": 1000,
    "patterns":           16000,
}


# ══════════════════════════════════════════════════════════════════════════════
# PART III — PROMPT ROUTING
#
# Paths relative to PROMPTS_DIR. The code does PROMPTS_DIR / path.
# ══════════════════════════════════════════════════════════════════════════════

PROMPTS = {
    # ── Core intelligence ──
    "intelligence_system":     "core/intelligence/system.txt",
    "product_catalog":         "core/intelligence/product_catalog.txt",
    "base":                    "company/base.txt",

    # ── Channel-specific context ──
    "channel_partners":        "company/channels/partners.txt",
    "channel_direct_sales":    "company/channels/direct_sales.txt",
    "channel_xl":              "company/channels/xl.txt",

    # ── Role-specific ──
    "role_pbd":                "company/roles/pbd.txt",
    "role_pae":                "company/roles/pae.txt",
    "role_sdr":                "company/roles/sdr.txt",
    "role_ae":                 "company/roles/ae.txt",
    "role_pdm":                "company/roles/pdm.txt",

    # ── Atlas ──
    "atlas_base":              "company/base.txt",
    "atlas_system":            "core/atlas/system.txt",

    # ── Forecast ──
    "forecast_system":         "core/forecast/system.txt",

    # ── Briefing ──
    "briefing_base":           "hourly/briefing/base.txt",
    "briefing_first_demo":     "hourly/briefing/first_demo.txt",
    "briefing_followup":       "hourly/briefing/followup_meddic.txt",
    "briefing_closing":        "hourly/briefing/pricing_closing.txt",

    # ── Email draft ──
    "email_draft":             "hourly/email_draft.txt",

    # ── Daily ──
    "trajectory":              "daily/trajectory.txt",
    "deal_analysis":           "daily/deal_analysis.txt",

    # ── Weekly ──
    "patterns":                "weekly/patterns.txt",
}

CHANNEL_PROMPT_MAP = {
    "partners":        PROMPTS["channel_partners"],
    "direct_sales_es": PROMPTS["channel_direct_sales"],
    "xl_sales":        PROMPTS["channel_xl"],
}

ROLE_PROMPT_MAP = {
    "PBD": PROMPTS["role_pbd"],
    "PAE": PROMPTS["role_pae"],
    "SDR": PROMPTS["role_sdr"],
    "AE":  PROMPTS["role_ae"],
    "PDM": PROMPTS["role_pdm"],
}

BRIEFING_PROMPT_MAP = {
    "demo":       "briefing_first_demo",
    "evaluation": "briefing_followup",
    "closing":    "briefing_closing",
}


# ══════════════════════════════════════════════════════════════════════════════
# PART IV — SCORING RULES
# ══════════════════════════════════════════════════════════════════════════════

MEDDIC_WEIGHTS = {
    "C": 0.12, "E": 0.22, "DP": 0.18, "DC": 0.18,
    "I": 0.13, "M": 0.05, "Comp": 0.12,
}

SCORE_DIVISOR = 20

STALE_THRESHOLDS = {
    "prospecting": 21,
    "qualifying":  14,
    "demo":        10,
    "evaluating":  14,
    "closing":     7,
    "nurturing":   30,
    "onhold":      45,
}
STALE_DEFAULT = 14

LOST_REASONS = [
    "Budget / Pricing", "Lost to competitor", "No decision / No response",
    "Timing not right", "Product fit", "Internal change", "Other",
]

MOMENTUM_ARROWS = {
    "accelerating": "▲",
    "stable":       "→",
    "decelerating": "▼",
    "stalled":      "▼",
}

ACTION_TAGS = {
    "CALL":       ["[CALL]", "llamar", "call", "chiamare", "anrufen"],
    "EMAIL":      ["[EMAIL]", "email", "enviar", "escribir", "scrivere", "send"],
    "ROI":        ["[ROI]", "roi", "business case"],
    "SLIDES":     ["[SLIDES]", "slides", "presentación", "deck"],
    "BATTLECARD": ["[BATTLECARD]", "battlecard", "comparativa"],
}
ACTION_DEFAULT_TYPE = "PREP"

DEFAULT_FOLLOWUP_DAYS = 3
MAX_NEXT_STEPS = 5
SIGNAL_MAX_CHARS = 80

# ── Date parsing (multilingual) ──
DAY_NAMES = {
    "lunes": 0, "martes": 1, "miércoles": 2, "jueves": 3,
    "viernes": 4, "sábado": 5, "domingo": 6,
}
MONTH_NAMES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}

MRR_RANGES = [
    {"label": "<500€",     "min": 0,    "max": 500},
    {"label": "500-1000€", "min": 500,  "max": 1000},
    {"label": "1000-3000€","min": 1000, "max": 3000},
    {"label": ">3000€",    "min": 3000, "max": 999999},
]

STAT_PATTERN_TYPES = {
    "temporal_month_end":   "Porcentaje de deals que cierran en los últimos 5 días del mes",
    "temporal_quarter_end": "Porcentaje de deals que cierran en el último mes del quarter",
    "stage_velocity":       "Media de días por stage antes de cerrar",
    "size_close_time":      "Tiempo medio de cierre por rango de MRR",
    "win_rate_by_team":     "Win rate por equipo",
    "loss_reasons":         "Top razones de pérdida con frecuencia",
}


# ══════════════════════════════════════════════════════════════════════════════
# PART V — EB ALERTS
#
# Economic Buyer alert rules. Channels/emoji are in org.py.
# ══════════════════════════════════════════════════════════════════════════════

EB_TRIGGER_STAGE = "economical_alignment"

EB_CLASSIFICATIONS = {
    "IDENTIFIED_INVOLVED": {
        "color":  "#2eb886",
        "header": "Deal sent to P&P with EB IDENTIFIED & INVOLVED",
    },
    "IDENTIFIED_NOT_INVOLVED": {
        "color":  "#daa038",
        "header": "Deal sent to P&P with EB IDENTIFIED BUT NOT INVOLVED",
    },
    "NOT_IDENTIFIED": {
        "color":  "#e01e5a",
        "header": "Deal sent to P&P with EB NOT IDENTIFIED",
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# PART VI — CONTEXT RULES
# ══════════════════════════════════════════════════════════════════════════════

CONTEXT_CALL_PATTERN = r"\[call:(\S+)\]"
CONTEXT_HS_PATTERN = r"\[hs:(\S+)\]"
MODJO_LINK_PATTERN = r"app\.modjo\.ai/call-details/(\d+)"
CONTEXT_RPC = "append_deal_context"
CONTEXT_RPC_PARAMS = {"deal_id": "p_deal_id", "text": "p_text"}

STALE_COOLDOWN_HOURS = 2
MAX_COMMS_PER_BATCH = 15
CONTEXT_RECENT_LINES = 30
TRANSCRIPT_PENDING_HOURS = 24

DEAL_NAME_EXCLUDE_PATTERNS = ["session"]

RED_FLAGS = frozenset({
    "BANT_3_MISSING", "NO_ECONOMIC_BUYER", "FORECAST_RED", "PARTNER_LEVERAGE_1",
})

NO_TAG_STRATEGY = "infer_from_context"

ATLAS_LABELS = {
    "es": {
        "company": {
            "company_name": "Nombre", "industry": "Industria", "company_size": "Empleados",
            "annual_revenue": "Revenue anual", "country": "País", "city": "Ciudad",
            "website": "Web", "description": "Descripción",
        },
        "deal_status": {"won": "GANADO", "lost": "PERDIDO/CERRADO", "active": "ACTIVO"},
        "deal_fields": {"stage": "Stage", "status": "Estado", "amount": "Amount",
                        "created": "Creado", "close": "Cierre", "forecast": "Forecast", "owner": "Owner",
                        "lost_reason": "Motivo de pérdida"},
        "contact_fields": {"title": "Cargo", "email": "Email", "phone": "Teléfono", "deals": "Deals"},
        "empty": {"company": "(sin información de empresa)", "deals": "(sin deals asociados)",
                  "contacts": "(sin contactos asociados)", "name": "(sin nombre)"},
        "headers": {"company": "Empresa", "deals": "Deals", "contacts": "Contactos"},
    },
    "it": {
        "company": {
            "company_name": "Nome", "industry": "Settore", "company_size": "Dipendenti",
            "annual_revenue": "Fatturato annuo", "country": "Paese", "city": "Città",
            "website": "Sito web", "description": "Descrizione",
        },
        "deal_status": {"won": "VINTO", "lost": "PERSO/CHIUSO", "active": "ATTIVO"},
        "deal_fields": {"stage": "Stage", "status": "Stato", "amount": "Amount",
                        "created": "Creato", "close": "Chiusura", "forecast": "Forecast", "owner": "Owner",
                        "lost_reason": "Motivo della perdita"},
        "contact_fields": {"title": "Ruolo", "email": "Email", "phone": "Telefono", "deals": "Deals"},
        "empty": {"company": "(nessuna informazione sull'azienda)", "deals": "(nessun deal associato)",
                  "contacts": "(nessun contatto associato)", "name": "(senza nome)"},
        "headers": {"company": "Azienda", "deals": "Deal", "contacts": "Contatti"},
    },
    "de": {
        "company": {
            "company_name": "Name", "industry": "Branche", "company_size": "Mitarbeiter",
            "annual_revenue": "Jahresumsatz", "country": "Land", "city": "Stadt",
            "website": "Webseite", "description": "Beschreibung",
        },
        "deal_status": {"won": "GEWONNEN", "lost": "VERLOREN/GESCHLOSSEN", "active": "AKTIV"},
        "deal_fields": {"stage": "Stage", "status": "Status", "amount": "Amount",
                        "created": "Erstellt", "close": "Abschluss", "forecast": "Forecast", "owner": "Owner",
                        "lost_reason": "Verlustgrund"},
        "contact_fields": {"title": "Position", "email": "E-Mail", "phone": "Telefon", "deals": "Deals"},
        "empty": {"company": "(keine Unternehmensinformationen)", "deals": "(keine zugeordneten Deals)",
                  "contacts": "(keine zugeordneten Kontakte)", "name": "(kein Name)"},
        "headers": {"company": "Unternehmen", "deals": "Deals", "contacts": "Kontakte"},
    },
    "pt": {
        "company": {
            "company_name": "Nome", "industry": "Setor", "company_size": "Funcionários",
            "annual_revenue": "Receita anual", "country": "País", "city": "Cidade",
            "website": "Site", "description": "Descrição",
        },
        "deal_status": {"won": "GANHO", "lost": "PERDIDO/FECHADO", "active": "ATIVO"},
        "deal_fields": {"stage": "Stage", "status": "Estado", "amount": "Amount",
                        "created": "Criado", "close": "Fecho", "forecast": "Forecast", "owner": "Owner",
                        "lost_reason": "Motivo da perda"},
        "contact_fields": {"title": "Cargo", "email": "Email", "phone": "Telefone", "deals": "Deals"},
        "empty": {"company": "(sem informação da empresa)", "deals": "(sem deals associados)",
                  "contacts": "(sem contactos associados)", "name": "(sem nome)"},
        "headers": {"company": "Empresa", "deals": "Deals", "contacts": "Contactos"},
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# PART VII — CADENCE CONFIG
#
# Parameters specific to each run cadence.
# Table/column references should use schema.tbl() / schema.col() in code.
# These are the BEHAVIORAL parameters only.
# ══════════════════════════════════════════════════════════════════════════════

HOURLY = {
    "briefing_prompt_base": PROMPTS["briefing_base"],
    "briefing_prompts": {
        "pae_brief_first_demo_multisector":       PROMPTS["briefing_first_demo"],
        "pae_brief_followup_meddic_multisector":  PROMPTS["briefing_followup"],
        "pae_brief_pricing_closing_multisector":  PROMPTS["briefing_closing"],
    },
    "email_draft_prompt": PROMPTS["email_draft"],
}

DAILY = {
    "trajectories_prompt":  PROMPTS["trajectory"],
    "trajectories_max":     500,
    "analysis_prompt":      PROMPTS["deal_analysis"],
    "analysis_max":         500,
    "forecast_refresh_days": 5,
    "forecast_refresh_cooldown": 3,
}

WEEKLY = {
    "patterns_prompt": PROMPTS["patterns"],
    "min_trajectories": MIN_TRAJECTORIES_FOR_PATTERNS,
}

MONTHLY = {}

FORECAST = {
    "prompt":              PROMPTS["forecast_system"],
    "meddic_weights":      MEDDIC_WEIGHTS,
    "max_similar_won":     5,
    "max_similar_lost":    5,
    "max_trajectory_snapshots": 15,
    "max_patterns_team":     5,
    "max_patterns_pipeline": 5,
    "max_patterns_global":   5,
    "max_calibration":     5,
    "max_deal_context_chars": 5000,
    "activity_decay": {
        3: 1.0, 7: 0.95, 14: 0.8, 30: 0.6, 999: 0.4,
    },
    "momentum_multiplier": {
        "accelerating": 1.0,
        "stable": 1.0,
        "decelerating": 0.85,
        "stalled": 0.7,
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# PART VIII — DERIVED SETS
#
# Computed from org.py at import time. Pipeline code reads these,
# never iterates org.ORGCHART directly.
# ══════════════════════════════════════════════════════════════════════════════

ALL_PBD_EMAILS: set[str] = set()
ALL_PAE_EMAILS: set[str] = set()
ALL_REP_EMAILS: set[str] = set()
ALL_PARTNER_NAMES: set[str] = set()
ALL_PARTNER_DOMAINS: set[str] = set()
ALL_DS_EMAILS: set[str] = set()
_EMAIL_TO_TEAM: dict[str, str] = {}
_EMAIL_TO_TEAMS: dict[str, list[str]] = {}


def _collect_ae_emails(team_dict: dict) -> set[str]:
    emails = set()
    emails |= team_dict.get("ae", set())
    if "tl" in team_dict:
        emails.add(team_dict["tl"])
    for sub in team_dict.get("subteams", {}).values():
        emails |= _collect_ae_emails(sub)
    return emails


def _flatten_ds_teams(teams: dict) -> list[tuple[str, dict]]:
    result = []
    for name, team in teams.items():
        result.append((name, team))
        result.extend(_flatten_ds_teams(team.get("subteams", {})))
    return result


def _collect_partner_emails(node: dict) -> set[str]:
    """Collect all emails from a partner team (supports both old pbd/pae and DS-style tl/ae formats)."""
    emails: set[str] = set()
    emails |= node.get("pbd", set())
    emails |= node.get("pae", set())
    emails |= node.get("ae", set())
    if "tl" in node and isinstance(node["tl"], str):
        emails.add(node["tl"])
    for role in node.get("leadership", {}).values():
        if isinstance(role, dict) and role.get("email"):
            emails.add(role["email"])
    for sub in node.get("subteams", {}).values():
        emails |= _collect_partner_emails(sub)
    return emails


for _name, _team in org.PARTNERS_ORGCHART.items():
    ALL_PBD_EMAILS |= _team.get("pbd", set())
    ALL_PAE_EMAILS |= _team.get("pae", set())
    _all_partner = _collect_partner_emails(_team)
    ALL_REP_EMAILS |= _all_partner
    pi = org.PARTNER_IDENTITY.get(_name, {})
    ALL_PARTNER_NAMES |= pi.get("partner_names", set())
    ALL_PARTNER_DOMAINS |= pi.get("partner_domains", set())
    for email in _team.get("pbd", set()) | _team.get("pae", set()):
        _EMAIL_TO_TEAM[email] = _name
        _EMAIL_TO_TEAMS.setdefault(email, []).append(_name)
    for email in _all_partner - _team.get("pbd", set()) - _team.get("pae", set()):
        if email not in _EMAIL_TO_TEAM:
            _EMAIL_TO_TEAM[email] = _name
        _EMAIL_TO_TEAMS.setdefault(email, []).append(_name)

for _name, _ds_team in _flatten_ds_teams(org.DIRECT_SALES.get("teams", {})):
    direct_emails = set(_ds_team.get("ae", set()))
    if "tl" in _ds_team:
        direct_emails.add(_ds_team["tl"])
    ALL_DS_EMAILS |= direct_emails
    ALL_REP_EMAILS |= direct_emails
    for email in direct_emails:
        _EMAIL_TO_TEAM[email] = _name
        _EMAIL_TO_TEAMS.setdefault(email, []).append(_name)

ALL_XL_EMAILS = org.XL_SALES.get("ae", set()) | org.XL_SALES.get("sdr", set())
ALL_REP_EMAILS |= ALL_XL_EMAILS
for _email in ALL_XL_EMAILS:
    _EMAIL_TO_TEAM[_email] = "XL"
    _EMAIL_TO_TEAMS.setdefault(_email, []).append("XL")

ALL_TARGET_EMAILS = ALL_REP_EMAILS | org.MANAGER_EMAILS

ACTIVE_TEAMS: set[str] = set()
for _name, _team in org.PARTNERS_ORGCHART.items():
    if _team.get("active", False):
        ACTIVE_TEAMS.add(_name)
for _name, _ds_team in _flatten_ds_teams(org.DIRECT_SALES.get("teams", {})):
    if _ds_team.get("active", False):
        ACTIVE_TEAMS.add(_name)
if org.XL_SALES.get("active", False):
    ACTIVE_TEAMS.add("XL")

IGNORE_DOMAINS_ATLAS = (
    org.GENERIC_EMAIL_DOMAINS | org.ISP_DOMAINS
    | org.INTERNAL_DOMAINS | ALL_PARTNER_DOMAINS
    | org.MISC_IGNORE_DOMAINS
)
IGNORE_DOMAINS_CALENDAR = (
    org.INTERNAL_DOMAINS | ALL_PARTNER_DOMAINS | org.GENERIC_EMAIL_DOMAINS
)

_OWNER_ID_TO_EMAIL = {v["id"]: email for email, v in org.CRM_OWNER_MAP.items()}
_EMAIL_TO_NAME = {email: v["name"] for email, v in org.CRM_OWNER_MAP.items()}


# ══════════════════════════════════════════════════════════════════════════════
# PART IX — HELPERS
#
# Resolve emails/IDs to teams, roles, channels, languages.
# Pipeline code calls these instead of navigating org dicts directly.
# ══════════════════════════════════════════════════════════════════════════════


def get_subteam(email: str) -> str | None:
    return _EMAIL_TO_TEAM.get(email)


def get_role(email: str, tags: list[str] | None = None) -> str | None:
    in_pbd = email in ALL_PBD_EMAILS
    in_pae = email in ALL_PAE_EMAILS
    if in_pbd and not in_pae:
        return "PBD"
    if in_pae and not in_pbd:
        return "PAE"
    if in_pbd and in_pae:
        return "PAE" if tags and any(t in org.CALL_TAGS_PAE for t in tags) else "PBD"
    if email in ALL_DS_EMAILS or email in ALL_XL_EMAILS:
        return "AE"
    return None


def get_org(email: str) -> str | None:
    team_name = get_subteam(email)
    if team_name:
        if team_name in org.PARTNERS_ORGCHART:
            return "Partners"
        if _find_ds_team(team_name):
            return "Direct Sales España"
        if team_name == "XL":
            return "XL"
    return None


def get_partner_label(email: str) -> str:
    team_name = get_subteam(email)
    if team_name:
        pi = org.PARTNER_IDENTITY.get(team_name, {})
        return pi.get("prompt_partner_label", "Unknown Partner")
    return "Unknown Partner"


def get_output_lang(team_name: str) -> str:
    pi = org.PARTNER_IDENTITY.get(team_name, {})
    lang = pi.get("lang", org.OUTPUT_LANG_DEFAULT)
    return org.OUTPUT_LANGUAGES.get(lang, org.OUTPUT_LANGUAGES[org.OUTPUT_LANG_DEFAULT])


def get_tz(team_name: str) -> ZoneInfo:
    pi = org.PARTNER_IDENTITY.get(team_name, {})
    tz_key = pi.get("tz")
    if tz_key:
        return org.TIMEZONES.get(tz_key, org.TZ_DEFAULT)
    return org.TZ_DEFAULT


def get_lang_file(email: str) -> str:
    team_name = get_subteam(email)
    if team_name:
        pi = org.PARTNER_IDENTITY.get(team_name, {})
        return pi.get("lang_file", "lang_en.txt")
    return "lang_en.txt"


def get_lang_prompt(team: str, owner_email: str | None = None) -> str:
    lang = None
    if owner_email:
        lang = org.PERSON_LANG_OVERRIDE.get(owner_email)
    if not lang and owner_email:
        owner_team = get_subteam(owner_email)
        if owner_team:
            pi = org.PARTNER_IDENTITY.get(owner_team, {})
            if pi:
                lang = pi.get("lang")
    if not lang:
        pi = org.PARTNER_IDENTITY.get(team, {})
        if pi:
            lang = pi.get("lang")
    if not lang:
        for ti in org.TEAM_IDENTITY.values():
            if ti.get("lang"):
                lang = ti["lang"]
                break
    if not lang:
        lang = org.OUTPUT_LANG_DEFAULT
    path = PROMPTS_DIR / "lang" / f"{lang}.txt"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return ""


def get_lang_code(team: str, owner_email: str | None = None) -> str:
    """Resolve language code: person override → subteam → team → default."""
    if owner_email:
        lang = org.PERSON_LANG_OVERRIDE.get(owner_email)
        if lang:
            return lang
        owner_team = get_subteam(owner_email)
        if owner_team:
            pi = org.PARTNER_IDENTITY.get(owner_team, {})
            if pi.get("lang"):
                return pi["lang"]
    pi = org.PARTNER_IDENTITY.get(team, {})
    if pi.get("lang"):
        return pi["lang"]
    for ti in org.TEAM_IDENTITY.values():
        if ti.get("lang"):
            return ti["lang"]
    return org.OUTPUT_LANG_DEFAULT


def get_tl_channel(team_name: str) -> str:
    sc = org.SLACK_TEAM_CHANNELS.get(team_name, {})
    return sc.get("tl_channel", org.SLACK_FALLBACK_CHANNEL)


def get_eb_alert_channel(team_name: str) -> str:
    return org.SLACK_EB_ALERT_CHANNELS.get(team_name, org.SLACK_FALLBACK_CHANNEL)


def get_slack_channel(email: str) -> str | None:
    return org.SLACK_PERSON_CHANNELS.get(email)


def get_slack_channel_by_name(name: str) -> str | None:
    for email, info in org.CRM_OWNER_MAP.items():
        if info["name"] == name and email in org.SLACK_PERSON_CHANNELS:
            return org.SLACK_PERSON_CHANNELS[email]
    return None


def get_deal_team(owner_email: str | None) -> str | None:
    if owner_email:
        teams = _EMAIL_TO_TEAMS.get(owner_email, [])
        if teams:
            return teams[0]
    return None


def get_owner_ids_for_team(team_name: str) -> list[str]:
    if team_name in org.PARTNERS_ORGCHART:
        emails = _collect_partner_emails(org.PARTNERS_ORGCHART[team_name])
    elif _find_ds_team(team_name):
        emails = _collect_ae_emails(_find_ds_team(team_name))
    elif team_name == "XL":
        emails = org.XL_SALES.get("ae", set()) | org.XL_SALES.get("sdr", set())
    else:
        return []
    return [org.CRM_OWNER_MAP[e]["id"] for e in emails if e in org.CRM_OWNER_MAP]


def get_email_by_owner_id(owner_id: str) -> str | None:
    return _OWNER_ID_TO_EMAIL.get(owner_id)


def get_display_name(email: str) -> str:
    return _EMAIL_TO_NAME.get(email, email)


def get_briefing_prompt_key(stage_category: str) -> str | None:
    return BRIEFING_PROMPT_MAP.get(stage_category)


def _find_ds_team(team_name: str, teams: dict | None = None) -> dict | None:
    if teams is None:
        teams = org.DIRECT_SALES.get("teams", {})
    if team_name in teams:
        return teams[team_name]
    for t in teams.values():
        result = _find_ds_team(team_name, t.get("subteams", {}))
        if result:
            return result
    return None
