"""
Core Parser — translates pipeline outputs into UI-ready data.

Writes to deal_ui table. Each entry point updates ONLY its columns.
Pure Python — zero API calls. Called by each CORE phase after it finishes.

Entry points:
  update_from_sync(deal_uuid)         — metadata: stage, mrr, last_contact
  update_from_atlas(deal_uuid)        — atlas: company, contacts, warnings
  update_from_intelligence(deal_uuid) — snapshot: MEDDIC, blockers, signals, actions, BANT
  update_from_forecast(deal_uuid)     — forecast: probability, timing, push_action, risks

Everything from config.
"""

import json
import re
from datetime import date, timedelta

from src.config import (
    INTELLIGENCE_CONFIG,
    FORECAST_CONFIG,
    DAILY_CONFIG,
    PARSER_CONFIG,
    HUBSPOT_APP_URL,
    STAGE_WON,
    STAGE_LOST,
)
from src.db.client import supabase

_I = INTELLIGENCE_CONFIG
_F = FORECAST_CONFIG


def _safe_int(v):
    if v is None:
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None
_D = DAILY_CONFIG
_P = PARSER_CONFIG

TODAY = date.today()


# ═══════════════════════════════════════════════════════════════════════════
# TEXT HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _parse_action_type(text: str) -> str:
    upper = text.upper()
    lower = text.lower()
    for action_type, keywords in _P["action_tags"].items():
        for kw in keywords:
            if kw.startswith("[") and kw in upper:
                return action_type
            elif not kw.startswith("[") and kw in lower:
                return action_type
    return _P["action_default_type"]


def _parse_who_and_text(raw: str) -> tuple[str, str]:
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
    t = text.lower()
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
    month_match = re.search(r"(\d{1,2}) de (\w+)", t)
    if month_match:
        day = int(month_match.group(1))
        month_num = _P["month_names"].get(month_match.group(2).lower())
        if month_num:
            try:
                return date(ref.year, month_num, day)
            except ValueError:
                pass
    if "hoy" in t or "ahora" in t or "inmediatamente" in t or "today" in t:
        return ref
    if "mañana" in t or "tomorrow" in t:
        return ref + timedelta(days=1)
    for name, weekday in _P["day_names"].items():
        if name in t:
            days_ahead = weekday - ref.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            return ref + timedelta(days=days_ahead)
    if "esta semana" in t or "this week" in t:
        d = 4 - ref.weekday()
        return ref + timedelta(days=d if d >= 0 else d + 7)
    if "próxima semana" in t or "semana que viene" in t or "next week" in t:
        return ref + timedelta(days=7 - ref.weekday())
    return ref + timedelta(days=_P["default_followup_days"])


def _due_label(due: date) -> str:
    diff = (due - TODAY).days
    if diff < 0:
        return f"atrasado ({abs(diff)}d)"
    if diff == 0:
        return "hoy"
    if diff == 1:
        return "mañana"
    if diff < 7:
        names = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
        return f"{names[due.weekday()]} {due.day:02d}/{due.month:02d}"
    if diff < 14:
        return "próxima semana"
    return f"{due.day:02d}/{due.month:02d}"


def _absolutize_text(text: str, ref: date) -> str:
    result = text
    def _fmt(d: date) -> str:
        names = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
        return f"{names[d.weekday()]} {d.day:02d}/{d.month:02d}"
    result = re.sub(r'\bhoy\b', _fmt(ref), result, flags=re.IGNORECASE)
    result = re.sub(r'\bmañana\b', _fmt(ref + timedelta(days=1)), result, flags=re.IGNORECASE)
    d2f = 4 - ref.weekday()
    if d2f < 0: d2f += 7
    fri = ref + timedelta(days=d2f)
    result = re.sub(r'\besta semana\b', f"antes del viernes {fri.day:02d}/{fri.month:02d}", result, flags=re.IGNORECASE)
    nm = ref + timedelta(days=7 - ref.weekday())
    result = re.sub(r'\bpróxima semana\b', f"semana del lunes {nm.day:02d}/{nm.month:02d}", result, flags=re.IGNORECASE)
    result = re.sub(r'\bsemana que viene\b', f"semana del lunes {nm.day:02d}/{nm.month:02d}", result, flags=re.IGNORECASE)
    for name, weekday in _P["day_names"].items():
        pattern = rf'\b{name}\b(?!\s+\d)'
        da = weekday - ref.weekday()
        if da <= 0: da += 7
        target = ref + timedelta(days=da)
        result = re.sub(pattern, f"{name} {target.day:02d}/{target.month:02d}", result, flags=re.IGNORECASE)
    return result


def _parse_bullets(text: str | None) -> list[str]:
    if not text:
        return []
    return [s.strip() for s in re.split(r"[\n•\-*]", text) if s.strip() and len(s.strip()) > 3]


def _parse_next_steps(next_step: str | None, ref: date) -> list[dict]:
    if not next_step:
        return []
    result = []
    for line in next_step.split("\n"):
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
            "when_label": _due_label(due),
            "due_date": due.isoformat(),
        })
    return result[:_P["max_next_steps"]]


def _extract_company_name(deal_name: str) -> str:
    if not deal_name:
        return "?"
    return deal_name.split(" - ")[0].split(" | ")[0].split(" from ")[0].strip()


def _extract_partner_label(deal_name: str, team: str) -> str:
    if " - from " in (deal_name or ""):
        return deal_name.split(" - from ")[-1].strip()
    if " from " in (deal_name or ""):
        return "from " + deal_name.split(" from ")[-1].strip()
    if team:
        return f"from {team}"
    return ""


def _days_since(date_str: str | None) -> int:
    if not date_str:
        return 999
    try:
        d = date.fromisoformat(str(date_str)[:10])
        return (TODAY - d).days
    except (ValueError, TypeError):
        return 999


# ═══════════════════════════════════════════════════════════════════════════
# ENTRY POINT 1: SYNC — metadata
# ═══════════════════════════════════════════════════════════════════════════

def update_from_sync(deal_uuid: str):
    deal = _fetch_deal(deal_uuid)
    if not deal:
        return

    deal_name = deal.get(_I["deal_col_deal_name"]) or ""
    stage = deal.get(_I["deal_col_stage"]) or ""
    team = deal.get(_I["deal_col_team"]) or ""
    last_contact = deal.get("last_contacted_hs")
    hs_deal_id = deal.get(_I["deal_col_deal_id"]) or ""
    days = _days_since(last_contact)
    macro = _P["macro_stage_map"].get(stage, "other")
    threshold = _P["stale_thresholds"].get(macro, _P["stale_default"])

    row = {
        "deal_id": deal_uuid,
        "hs_deal_id": hs_deal_id,
        "company_name": _extract_company_name(deal_name),
        "partner_label": _extract_partner_label(deal_name, team),
        "deal_name_full": deal_name,
        "stage": stage,
        "pae": deal.get(_I["deal_col_pae"]) or "",
        "pbd": deal.get(_I["deal_col_pbd"]) or "",
        "team": team,
        "last_contact": last_contact,
        "last_contact_label": f"Hace {days}d" if days < 999 else "—",
        "hs_link": f"{HUBSPOT_APP_URL}/contacts/{hs_deal_id}" if hs_deal_id else None,
        "mrr": deal.get(_I["deal_col_amount"]),
        "close_date_hs": deal.get(_I["deal_col_close_date"]),
        "forecast_category": deal.get(_I["deal_col_forecast_cat"]) or "",
        "macro_stage": macro,
        "is_stale": days > threshold,
        "stale_days": days if days < 999 else None,
        "employees": deal.get("num_employees") or deal.get("num_employees_custom") or "",
    }

    if stage in STAGE_WON:
        row["outcome"] = "won"
    elif stage in STAGE_LOST:
        row["outcome"] = "lost"

    _upsert(deal_uuid, row)


# ═══════════════════════════════════════════════════════════════════════════
# ENTRY POINT 2: ATLAS — company info
# ═══════════════════════════════════════════════════════════════════════════

def update_from_atlas(deal_uuid: str):
    deal = _fetch_deal(deal_uuid)
    if not deal:
        return
    crm_id = deal.get(_I["deal_col_crm_id"])
    if not crm_id:
        return

    atlas = (
        supabase.table(_I["atlas_table"])
        .select("*")
        .eq(_I["fk_crm_id"], crm_id)
        .maybe_single()
        .execute()
    )
    if not atlas.data:
        return
    a = atlas.data

    # Contacts: try JSON array first, fallback to contacts_breakdown text
    contacts = []
    contacts_raw = a.get("contacts_map")
    if contacts_raw:
        if isinstance(contacts_raw, str):
            try:
                parsed_contacts = json.loads(contacts_raw)
                if isinstance(parsed_contacts, list):
                    contacts_raw = parsed_contacts
                else:
                    contacts_raw = None
            except (json.JSONDecodeError, TypeError):
                contacts_raw = None
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

    # Fallback: parse contacts_breakdown text (line-based)
    if not contacts:
        breakdown = a.get("contacts_breakdown") or ""
        if breakdown:
            import re
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
        "atlas_company_name": a.get("company_name") or "",
        "atlas_industry": a.get("industry") or "",
        "atlas_country": a.get("country") or "",
        "atlas_employees": str(a.get("company_size") or ""),
        "atlas_revenue": str(a.get("annual_revenue") or "No disponible"),
        "atlas_website": a.get("website") or "",
        "atlas_description": a.get("company_context") or "",
        "atlas_contacts": json.dumps(contacts, ensure_ascii=False),
        "atlas_contacts_count": _safe_int(len(contacts)),
        "employees": str(a.get("company_size") or ""),
    }

    # Atlas company_card (fit, history_summary, warnings)
    company_card = a.get("company_card")
    if company_card:
        if isinstance(company_card, str):
            try:
                company_card = json.loads(company_card)
            except (json.JSONDecodeError, TypeError):
                company_card = {}
        if isinstance(company_card, dict):
            fit = company_card.get("fit") or {}
            row["atlas_fit_level"] = fit.get("score") or "Fit por validar"
            row["atlas_fit_text"] = fit.get("reason") or ""
            row["atlas_history_summary"] = company_card.get("history_summary") or ""
            row["atlas_warnings"] = json.dumps(company_card.get("warnings") or [], ensure_ascii=False)

    # Atlas deal_insights (signals, blockers, patterns, loss_reasons)
    deal_insights = a.get("deal_insights")
    if deal_insights:
        if isinstance(deal_insights, str):
            try:
                deal_insights = json.loads(deal_insights)
            except (json.JSONDecodeError, TypeError):
                deal_insights = {}
        if isinstance(deal_insights, dict):
            row["atlas_signals"] = json.dumps(deal_insights.get("buying_signals") or [], ensure_ascii=False)
            row["atlas_blockers"] = json.dumps(deal_insights.get("blockers") or [], ensure_ascii=False)
            row["atlas_patterns"] = json.dumps(deal_insights.get("patterns") or [], ensure_ascii=False)

    # Atlas deal counts (from deals_breakdown text)
    deals_text = a.get("deals_breakdown") or ""
    if deals_text:
        active = deals_text.lower().count("activo") + deals_text.lower().count("open")
        lost = deals_text.lower().count("perdido") + deals_text.lower().count("closedlost") + deals_text.lower().count("closed lost")
        row["atlas_deals_active"] = _safe_int(active)
        row["atlas_deals_lost"] = _safe_int(lost)

    _upsert(deal_uuid, row)


# ═══════════════════════════════════════════════════════════════════════════
# ENTRY POINT 3: INTELLIGENCE — snapshot + BANT
# ═══════════════════════════════════════════════════════════════════════════

def update_from_intelligence(deal_uuid: str):
    deal = _fetch_deal(deal_uuid)
    if not deal:
        return
    hs_deal_id = deal.get(_I["deal_col_deal_id"]) or ""

    snap = (
        supabase.table(_I["snapshot_table"])
        .select("*")
        .eq(_I["fk_hs_deal_id"], hs_deal_id)
        .order(_I["fk_snapshot_date"], desc=True)
        .limit(1)
        .execute()
    )
    if not snap.data:
        return
    s = snap.data[0]
    snap_date_str = s.get(_I["fk_snapshot_date"]) or TODAY.isoformat()
    try:
        snap_dt = date.fromisoformat(str(snap_date_str))
    except ValueError:
        snap_dt = TODAY

    # MEDDIC
    scores = {k: float(s.get(f"{k}_score") or 0) for k in ["m", "e", "dc", "dp", "i", "c", "comp"]}
    meddic_total = round(sum(scores.values()))

    # Blockers
    blockers_list = _parse_bullets(s.get("live_blockers"))
    # Signals
    signals_list = _parse_bullets(s.get("buyer_signals"))

    # Next steps parsed
    next_steps = _parse_next_steps(s.get("next_step"), snap_dt)

    # Action unification: push_action > action_signal > first next_step
    push_action_raw = (s.get("push_action") or "").strip()
    action_signal_raw = _absolutize_text((s.get("action_signal") or "").strip(), snap_dt)

    if push_action_raw:
        action_source = "forecast"
        action_raw = push_action_raw
    elif action_signal_raw:
        action_source = "snapshot"
        action_raw = action_signal_raw
    elif next_steps:
        action_source = "next_step"
        action_raw = f"[{next_steps[0]['type']}] {next_steps[0]['who']} → {next_steps[0]['text']}" if next_steps[0]['who'] else next_steps[0]['text']
    else:
        action_source = ""
        action_raw = ""

    if action_raw:
        action_type = _parse_action_type(action_raw)
        who, headline = _parse_who_and_text(action_raw)
        headline = _absolutize_text(headline, snap_dt)
        due = _resolve_due_date(action_raw, snap_dt)
        if not who:
            who = deal.get(_I["deal_col_pae"]) or deal.get(_I["deal_col_pbd"]) or "Rep"
    else:
        action_type = ""
        who = ""
        headline = ""
        due = TODAY

    # Dedup next_steps: remove if first step is same as action headline
    if next_steps and action_source != "next_step":
        first_text = next_steps[0].get("text", "").lower()[:50]
        if first_text and first_text in headline.lower():
            next_steps = next_steps[1:]
            for i, ns in enumerate(next_steps):
                ns["order"] = i + 1

    # Probability timeline
    hist_resp = (
        supabase.table(_I["snapshot_table"])
        .select(f"{_I['fk_snapshot_date']}, close_probability")
        .eq(_I["fk_deal_id"], deal_uuid)
        .order(_I["fk_snapshot_date"])
        .execute()
    )
    timeline = [
        {"date": h[_I["fk_snapshot_date"]], "prob": h.get("close_probability") or 0}
        for h in (hist_resp.data or [])
        if h.get("close_probability") is not None
    ]

    # Trend
    prev_prob = timeline[-2]["prob"] if len(timeline) >= 2 else None
    curr_prob = s.get("close_probability")
    trend = (curr_prob - prev_prob) if curr_prob is not None and prev_prob is not None else None

    # Stage roadmap from deal stage dates
    stage_roadmap = _build_stage_roadmap(deal)

    # Score (0-5 from probability)
    prob = s.get("close_probability")
    score = round((prob / _P["score_divisor"]) * 10) / 10 if prob is not None else None

    row = {
        "snapshot_date": snap_date_str,
        "deal_summary": s.get("deal_summary") or "",
        "deal_assessment": s.get("deal_assessment") or "",
        "meddic_total": _safe_int(meddic_total),
        "m_score": _safe_int(scores["m"]), "m_text": s.get("m_accumulate") or "",
        "e_score": _safe_int(scores["e"]), "e_text": s.get("e_accumulate") or "",
        "dc_score": _safe_int(scores["dc"]), "dc_text": s.get("dc_accumulate") or "",
        "dp_score": _safe_int(scores["dp"]), "dp_text": s.get("dp_accumulate") or "",
        "i_score": _safe_int(scores["i"]), "i_text": s.get("i_accumulate") or "",
        "c_score": _safe_int(scores["c"]), "c_text": s.get("c_accumulate") or "",
        "comp_score": _safe_int(scores["comp"]), "comp_text": s.get("comp_accumulate") or "",
        "blockers_count": len(blockers_list),
        "blockers": json.dumps([{"text": b} for b in blockers_list], ensure_ascii=False),
        "signals_count": _safe_int(len(signals_list)),
        "signals": json.dumps([{"text": si, "strength": "Fuerte" if "fuerte" in si.lower() else "Moderada"} for si in signals_list], ensure_ascii=False),
        "objections": s.get("objections") or "",
        "howto_label": s.get("howto_label") or "",
        "howto_body": s.get("howto_body") or "",
        "action_source": action_source,
        "action_type": action_type,
        "action_headline": headline,
        "action_headline_short": headline[:_P["signal_max_chars"]] + ("…" if len(headline) > _P["signal_max_chars"] else ""),
        "action_signal": action_signal_raw,
        "action_due_label": _due_label(due),
        "action_due_date": due.isoformat(),
        "action_who": who,
        "next_steps": json.dumps(next_steps, ensure_ascii=False),
        "next_steps_total": _safe_int(len(next_steps)),
        "next_steps_done": 0,
        "probability_timeline": json.dumps(timeline, ensure_ascii=False),
        "trend": _safe_int(trend),
        "stage_roadmap": json.dumps(stage_roadmap, ensure_ascii=False),
        "score": score,
    }

    # BANT (from pbd_snapshots)
    pbd_snap = (
        supabase.table(_I["pbd_snapshot_table"])
        .select("*")
        .eq(_I["fk_hs_deal_id"], hs_deal_id)
        .order(_I["fk_snapshot_date"], desc=True)
        .limit(1)
        .execute()
    )
    if pbd_snap.data:
        b = pbd_snap.data[0]
        statuses = {
            "B": b.get("bant_b_status") or "Missing",
            "A": b.get("bant_a_status") or "Missing",
            "N": b.get("bant_n_status") or "Missing",
            "T": b.get("bant_t_status") or "Missing",
        }
        row["bant_summary_line"] = " · ".join(f"{k}: {v}" for k, v in statuses.items())
        row["bant_b_status"] = statuses["B"]
        row["bant_b_text"] = b.get("bant_b_evidence") or ""
        row["bant_a_status"] = statuses["A"]
        row["bant_a_text"] = b.get("bant_a_evidence") or ""
        row["bant_n_status"] = statuses["N"]
        row["bant_n_text"] = b.get("bant_n_evidence") or ""
        row["bant_t_status"] = statuses["T"]
        row["bant_t_text"] = b.get("bant_t_evidence") or ""

    # Product intel (from deal_product_signals)
    pi = (
        supabase.table(_I["product_signals_table"])
        .select("product_assessment, product_actions, expansion_summary")
        .eq(_I["product_col_deal_id"], deal_uuid)
        .order(_I["product_col_snapshot_date"], desc=True)
        .limit(1)
        .execute()
    )
    if pi.data:
        p = pi.data[0]
        if p.get("product_assessment"):
            row["product_assessment"] = p["product_assessment"]
        if p.get("product_actions"):
            row["product_actions"] = p["product_actions"] if isinstance(p["product_actions"], str) else json.dumps(p["product_actions"], ensure_ascii=False)
        if p.get("expansion_summary"):
            row["expansion_summary"] = p["expansion_summary"]

    _upsert(deal_uuid, row)


# ═══════════════════════════════════════════════════════════════════════════
# ENTRY POINT 4: FORECAST
# ═══════════════════════════════════════════════════════════════════════════

def update_from_forecast(deal_uuid: str):
    deal = _fetch_deal(deal_uuid)
    if not deal:
        return
    hs_deal_id = deal.get(_I["deal_col_deal_id"]) or ""
    mrr = float(deal.get(_I["deal_col_amount"]) or 0)

    snap = (
        supabase.table(_I["snapshot_table"])
        .select("close_probability, claudio_close_date, closes_this_month, closes_next_month, "
                "forecast_confidence, deal_momentum, forecast_reasoning, "
                "push_action, push_action_reasoning, forecast_accelerators, forecast_risks")
        .eq(_I["fk_hs_deal_id"], hs_deal_id)
        .order(_I["fk_snapshot_date"], desc=True)
        .limit(1)
        .execute()
    )
    if not snap.data:
        return
    s = snap.data[0]

    prob = s.get("close_probability") or 0
    momentum = s.get("deal_momentum") or ""
    closes_tm = s.get("closes_this_month")
    pushable = bool(s.get("push_action"))

    # Accelerators and risks as JSONB
    accel_raw = _parse_bullets(s.get("forecast_accelerators"))
    risks_raw = _parse_bullets(s.get("forecast_risks"))

    # Bucket
    if closes_tm:
        bucket = "forecast"
    elif pushable:
        bucket = "pushable"
    elif s.get("closes_next_month"):
        bucket = "next_month"
    elif risks_raw:
        bucket = "blocker"
    else:
        bucket = "pipeline"

    # Priority
    priority = 5
    if bucket == "forecast":
        priority = 1
    elif bucket == "pushable":
        priority = 2
    elif bucket == "next_month":
        priority = 3
    elif bucket == "blocker":
        priority = 4

    row = {
        "close_probability": _safe_int(prob),
        "close_date": s.get("claudio_close_date"),
        "forecast_amount": round((prob / 100) * mrr, 2) if mrr else None,
        "closes_this_month": closes_tm,
        "closes_next_month": s.get("closes_next_month"),
        "forecast_confidence": s.get("forecast_confidence") or "",
        "deal_momentum": momentum,
        "momentum_arrow": _P["momentum_arrows"].get(momentum, ""),
        "estimated_close_date": s.get("claudio_close_date"),
        "forecast_reasoning": s.get("forecast_reasoning") or "",
        "push_action": s.get("push_action") or "",
        "push_action_reasoning": s.get("push_action_reasoning") or "",
        "forecast_accelerators": json.dumps([{"text": a} for a in accel_raw], ensure_ascii=False),
        "forecast_risks": json.dumps([{"text": r} for r in risks_raw], ensure_ascii=False),
        "forecast_risks_count": _safe_int(len(risks_raw)),
        "forecast_accelerators_count": _safe_int(len(accel_raw)),
        "bucket": bucket,
        "action_priority": _safe_int(priority),
        "score": round((prob / _P["score_divisor"]) * 10) / 10 if prob else None,
    }

    # Re-evaluate action if forecast has push_action and it's better
    push_raw = (s.get("push_action") or "").strip()
    if push_raw:
        snap_dt = TODAY
        action_type = _parse_action_type(push_raw)
        who, headline = _parse_who_and_text(push_raw)
        headline = _absolutize_text(headline, snap_dt)
        due = _resolve_due_date(push_raw, snap_dt)
        if not who:
            who = deal.get(_I["deal_col_pae"]) or deal.get(_I["deal_col_pbd"]) or "Rep"
        row["action_source"] = "forecast"
        row["action_type"] = action_type
        row["action_headline"] = headline
        row["action_headline_short"] = headline[:_P["signal_max_chars"]] + ("…" if len(headline) > _P["signal_max_chars"] else "")
        row["action_due_label"] = _due_label(due)
        row["action_due_date"] = due.isoformat()
        row["action_who"] = who

    _upsert(deal_uuid, row)


# ═══════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _fetch_deal(deal_uuid: str) -> dict | None:
    resp = supabase.table(_I["deals_table"]).select("*").eq(_I["deal_col_id"], deal_uuid).limit(1).execute()
    return resp.data[0] if resp.data else None


def _upsert(deal_uuid: str, row: dict):
    row["deal_id"] = deal_uuid
    row = {k: v for k, v in row.items() if v is not None}
    supabase.table(_P["table"]).upsert(row, on_conflict=_P["upsert_key"]).execute()


def _build_stage_roadmap(deal: dict) -> list[dict]:
    """Build stage roadmap from deal stage date columns."""
    current_stage = deal.get(_I["deal_col_stage"]) or ""
    roadmap = []

    stage_date_pairs = [
        # SDR Partner Opportunities Pipeline
        ("Pre-qualified", "sdr_prequalified_entered", "sdr_prequalified_exited"),
        ("Attempting to contact", "sdr_attempting_to_contact_entered", "sdr_attempting_to_contact_exited"),
        ("Engaged", "sdr_engaged_entered", "sdr_engaged_exited"),
        ("Demo Booked", "sdr_demo_booked_entered", "sdr_demo_booked_exited"),
        # Partners Distribution Pipeline
        ("New Deals", "dist_new_deals_entered", "dist_new_deals_exited"),
        ("Demo Booked", "dist_demo_booked_entered", "dist_demo_booked_exited"),
        ("Product Alignment", "dist_product_alignment_entered", "dist_product_alignment_exited"),
        ("MEDDPICC", "dist_meddpicc_validation_entered", "dist_meddpicc_validation_exited"),
        ("Pricing & Packaging", "dist_pricing_and_packaging_entered", "dist_pricing_and_packaging_exited"),
        ("Contracting", "dist_contracting_entered", "dist_contracting_exited"),
        # Sales Pipeline
        ("Meeting Booked", "sales_meeting_booked_entered", "sales_meeting_booked_exited"),
        ("Discovery", "sales_discovery_entered", "sales_discovery_exited"),
        ("Product Alignment", "sales_product_alignment_entered", "sales_product_alignment_exited"),
        ("Pricing & Packaging", "sales_pricing_and_packaging_entered", "sales_pricing_and_packaging_exited"),
        ("Contracting", "sales_contracting_entered", "sales_contracting_exited"),
        # OB SDR Pipeline
        ("New", "ob_new_entered", "ob_new_exited"),
        ("Research & Outreach", "ob_research_outreach_entered", "ob_research_outreach_exited"),
        ("Engaged", "ob_engaged_entered", "ob_engaged_exited"),
        ("Meeting Booked", "ob_meeting_booked_entered", "ob_meeting_booked_exited"),
        # IB SDR Pipeline
        ("New Qualified", "ib_new_qualified_entered", "ib_new_qualified_exited"),
        ("Attempted to contact", "ib_attempted_contact_entered", "ib_attempted_contact_exited"),
        ("Engaged", "ib_engaged_entered", "ib_engaged_exited"),
        ("Meeting Booked", "ib_meeting_booked_entered", "ib_meeting_booked_exited"),
        # XL Account Pipeline
        ("New", "xl_new_entered", "xl_new_exited"),
        ("Outreach", "xl_outreach_entered", "xl_outreach_exited"),
        ("Engaged", "xl_engaged_entered", "xl_engaged_exited"),
        ("Meeting Booked", "xl_meeting_booked_entered", "xl_meeting_booked_exited"),
        ("Discovery", "xl_discovery_entered", "xl_discovery_exited"),
        ("Product Alignment", "xl_product_alignment_entered", "xl_product_alignment_exited"),
        ("Pricing & Packaging", "xl_pricing_packaging_entered", "xl_pricing_packaging_exited"),
        ("Contracting", "xl_contracting_entered", "xl_contracting_exited"),
        # XL SDR Pipeline
        ("New", "xlsdr_new_entered", "xlsdr_new_exited"),
        ("Research & Outreach", "xlsdr_research_outreach_entered", "xlsdr_research_outreach_exited"),
        ("Engaged", "xlsdr_engaged_entered", "xlsdr_engaged_exited"),
        ("Meeting Booked", "xlsdr_meeting_booked_entered", "xlsdr_meeting_booked_exited"),
        # IT AE Pipeline
        ("New", "itae_new_entered", "itae_new_exited"),
        ("Outreach", "itae_outreach_entered", "itae_outreach_exited"),
        ("Engaged", "itae_engaged_entered", "itae_engaged_exited"),
        ("Meeting Booked", "itae_meeting_booked_entered", "itae_meeting_booked_exited"),
        ("Discovery", "itae_discovery_entered", "itae_discovery_exited"),
        ("Product Alignment", "itae_product_alignment_entered", "itae_product_alignment_exited"),
        ("Pricing & Packaging", "itae_pricing_packaging_entered", "itae_pricing_packaging_exited"),
        ("Contracting", "itae_contracting_entered", "itae_contracting_exited"),
        # IT SDR Pipeline
        ("New", "itsdr_new_entered", "itsdr_new_exited"),
        ("Research & Outreach", "itsdr_research_outreach_entered", "itsdr_research_outreach_exited"),
        ("Engaged", "itsdr_engaged_entered", "itsdr_engaged_exited"),
        ("Meeting Booked", "itsdr_meeting_booked_entered", "itsdr_meeting_booked_exited"),
    ]

    seen_stages = set()
    for stage_label, entered_col, exited_col in stage_date_pairs:
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

    if current_stage and current_stage not in seen_stages:
        roadmap.append({
            "stage": current_stage,
            "entered": TODAY.isoformat(),
            "exited": None,
            "duration_days": None,
            "done": False,
            "current": True,
        })

    return roadmap


# ═══════════════════════════════════════════════════════════════════════════
# ENTRY POINT 5: DAILY — deal analysis (post-mortem)
# ═══════════════════════════════════════════════════════════════════════════

def update_from_daily(deal_uuid: str):
    """Copy deal_analysis + trajectory fields to deal_ui. For closed deals."""
    row = {}

    # Deal analysis
    analysis_resp = (
        supabase.table(_D["analysis_table"])
        .select("*")
        .eq("deal_id", deal_uuid)
        .maybe_single()
        .execute()
    )
    if analysis_resp and analysis_resp.data:
        a = analysis_resp.data
        row.update({
            "outcome": a.get("outcome") or "",
            "full_narrative": a.get("full_narrative") or "",
            "outcome_summary": a.get("outcome_summary") or "",
            "analysis_timeline": a.get("deal_timeline") if isinstance(a.get("deal_timeline"), str) else json.dumps(a.get("deal_timeline") or [], ensure_ascii=False),
            "analysis_what_worked": a.get("what_worked") if isinstance(a.get("what_worked"), str) else json.dumps(a.get("what_worked") or [], ensure_ascii=False),
            "analysis_what_failed": a.get("what_failed") if isinstance(a.get("what_failed"), str) else json.dumps(a.get("what_failed") or [], ensure_ascii=False),
            "analysis_could_have_changed": a.get("what_could_have_changed") or "",
            "analysis_rep_assessment": a.get("rep_assessment") or "",
            "analysis_key_people": a.get("key_people") if isinstance(a.get("key_people"), str) else json.dumps(a.get("key_people") or [], ensure_ascii=False),
            "analysis_products_pitched": a.get("products_pitched") if isinstance(a.get("products_pitched"), str) else json.dumps(a.get("products_pitched") or [], ensure_ascii=False),
            "analysis_products_missed": a.get("products_missed") if isinstance(a.get("products_missed"), str) else json.dumps(a.get("products_missed") or [], ensure_ascii=False),
            "analysis_product_assessment": a.get("product_assessment") or "",
        })

    # Trajectory
    traj_resp = (
        supabase.table(_D["trajectories_table"])
        .select("*")
        .eq(_D["fk_deal_id"], deal_uuid)
        .maybe_single()
        .execute()
    )
    if traj_resp and traj_resp.data:
        t = traj_resp.data
        row.update({
            "trajectory": t.get("trajectory") if isinstance(t.get("trajectory"), str) else json.dumps(t.get("trajectory") or [], ensure_ascii=False),
            "interactions": t.get("interactions") if isinstance(t.get("interactions"), str) else json.dumps(t.get("interactions") or {}, ensure_ascii=False),
            "lessons": t.get("lessons") if isinstance(t.get("lessons"), str) else json.dumps(t.get("lessons") or [], ensure_ascii=False),
            "closed_lost_reason": t.get("closed_lost_reason") or "",
            "key_turning_point": t.get("key_turning_point") or "",
            "deal_age_days": _safe_int(t.get("deal_age_days")),
        })
        if not row.get("outcome"):
            row["outcome"] = t.get("outcome") or ""

    if row:
        _upsert(deal_uuid, row)
