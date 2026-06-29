"""
Generate briefings for deals with meetings today.
1 Claude call (Sonnet) per deal that doesn't have a briefing today.
Everything from config.
"""

import json
import re
from datetime import date

from src.config import (
    INTELLIGENCE_CONFIG,
    HOURLY_CONFIG,
    STAGE_CATEGORY_BRIEFING,
    PROMPTS_DIR,
    MODEL_DEFAULT,
    MAX_TOKENS_AUDIT,
    get_stage_category,
)
from src.db.client import supabase
from src.integrations import claude

_I = INTELLIGENCE_CONFIG
_H = HOURLY_CONFIG
TODAY = date.today().isoformat()


def _already_has_briefing(deal_ids: list[str]) -> set[str]:
    """Return deal_ids that already have a briefing today."""
    if not deal_ids:
        return set()
    resp = (
        supabase.table(_H["briefings_table"])
        .select("deal_id")
        .in_("deal_id", deal_ids)
        .gte("created_at", TODAY + "T00:00:00")
        .execute()
    )
    return {r["deal_id"] for r in (resp.data or [])}


def _detect_meeting_type(stage: str) -> str:
    """Stage → category → briefing prompt key."""
    category = get_stage_category(stage)
    return STAGE_CATEGORY_BRIEFING.get(category, "pae_brief_followup_meddic_multisector")


def _build_system_prompt(meeting_type: str) -> str:
    """Load base + type-specific prompt."""
    base = (PROMPTS_DIR / _H["briefing_prompt_base"]).read_text(encoding="utf-8").strip()
    type_path = _H["briefing_prompts"].get(meeting_type)
    if type_path:
        type_prompt = (PROMPTS_DIR / type_path).read_text(encoding="utf-8").strip()
        return f"{base}\n\n{type_prompt}"
    return base


def _build_user_prompt(deal: dict) -> str:
    """Build full context for the briefing."""
    deal_uuid = deal[_I["deal_col_id"]]
    hs_deal_id = deal.get(_I["deal_col_deal_id"]) or ""
    lines = []

    # Deal metadata
    lines.append("## DEAL METADATA")
    lines.append(f"- Name: {deal.get(_I['deal_col_deal_name']) or '?'}")
    lines.append(f"- Stage: {deal.get(_I['deal_col_stage']) or '?'}")
    lines.append(f"- MRR: €{deal.get(_I['deal_col_amount']) or '?'}")
    lines.append(f"- Deal Age: {deal.get(_I['deal_col_age']) or '?'} days")
    lines.append(f"- PAE: {deal.get(_I['deal_col_pae']) or '?'}")
    lines.append(f"- PBD: {deal.get(_I['deal_col_pbd']) or '?'}")
    lines.append(f"- Team: {deal.get(_I['deal_col_team']) or '?'}")
    lines.append(f"- Close Date: {deal.get(_I['deal_col_close_date']) or '?'}")
    lines.append("")

    # Atlas
    crm_id = deal.get(_I["deal_col_crm_id"])
    if crm_id:
        atlas_resp = (
            supabase.table(_I["atlas_table"])
            .select(f"{_I['atlas_col_company_context']}, {_I['atlas_col_company_card']}")
            .eq(_I["fk_crm_id"], crm_id)
            .maybe_single()
            .execute()
        )
        if atlas_resp.data:
            ctx = atlas_resp.data.get(_I["atlas_col_company_context"]) or atlas_resp.data.get(_I["atlas_col_company_card"]) or ""
            if ctx:
                lines.append("## ATLAS — COMPANY CONTEXT")
                lines.append(str(ctx))
                lines.append("")

    # Deal context
    deal_context = deal.get(_I["deal_context_col"]) or ""
    lines.append("## DEAL CONTEXT — FULL HISTORY")
    lines.append(deal_context if deal_context else "(no deal context)")
    lines.append("")

    # Snapshot
    if hs_deal_id:
        snap_resp = (
            supabase.table(_I["snapshot_table"])
            .select("*")
            .eq(_I["fk_hs_deal_id"], hs_deal_id)
            .order(_I["fk_snapshot_date"], desc=True)
            .limit(1)
            .execute()
        )
        if snap_resp.data:
            s = snap_resp.data[0]
            lines.append("## CURRENT SNAPSHOT")
            lines.append(f"Deal Summary: {s.get('deal_summary') or '-'}")
            lines.append(f"Assessment: {s.get('deal_assessment') or '-'}")
            scores = " | ".join(f"{k}={s.get(f'{k}_score', '?')}" for k in ["m", "e", "dc", "dp", "i", "c", "comp"])
            lines.append(f"MEDDIC: {scores}")
            lines.append(f"Signals: {s.get('buyer_signals') or '-'}")
            lines.append(f"Blockers: {s.get('live_blockers') or '-'}")
            lines.append(f"Next Step: {s.get('next_step') or '-'}")
            lines.append(f"Howto: {s.get('howto_label') or ''} — {s.get('howto_body') or '-'}")
            lines.append(f"Probability: {s.get('close_probability') or '?'}%")
            lines.append(f"Momentum: {s.get('deal_momentum') or '?'}")
            lines.append(f"Push Action: {s.get('push_action') or '-'}")
            lines.append(f"Risks: {s.get('forecast_risks') or '-'}")
            lines.append(f"Accelerators: {s.get('forecast_accelerators') or '-'}")
            lines.append("")

    # BANT (if PBD stage)
    if hs_deal_id:
        bant_resp = (
            supabase.table(_I["pbd_snapshot_table"])
            .select("*")
            .eq(_I["fk_hs_deal_id"], hs_deal_id)
            .order(_I["fk_snapshot_date"], desc=True)
            .limit(1)
            .execute()
        )
        if bant_resp.data:
            b = bant_resp.data[0]
            lines.append("## BANT")
            lines.append(f"B: {b.get('bant_b_status') or '?'} — {b.get('bant_b_evidence') or ''}")
            lines.append(f"A: {b.get('bant_a_status') or '?'} — {b.get('bant_a_evidence') or ''}")
            lines.append(f"N: {b.get('bant_n_status') or '?'} — {b.get('bant_n_evidence') or ''}")
            lines.append(f"T: {b.get('bant_t_status') or '?'} — {b.get('bant_t_evidence') or ''}")
            lines.append("")

    # Product signals
    prod_resp = (
        supabase.table(_I["product_signals_table"])
        .select("*")
        .eq("deal_id", deal_uuid)
        .order("snapshot_date", desc=True)
        .limit(1)
        .execute()
    )
    if prod_resp.data:
        ps = prod_resp.data[0]
        products = ps.get("products_discussed") or "[]"
        if isinstance(products, str):
            try:
                products = json.loads(products)
            except (json.JSONDecodeError, TypeError):
                products = []
        if products:
            lines.append("## PRODUCT SIGNALS")
            for p in products:
                lines.append(f"  - {p.get('product', '?')}: {p.get('context', '')} ({p.get('reception', '?')})")
            lines.append("")

    lines.append(f"Meeting type: {_detect_meeting_type(deal.get(_I['deal_col_stage']) or '')}")
    lines.append(f"Today: {TODAY}")

    return "\n".join(lines)


def generate_briefing(deal: dict) -> dict | None:
    """Generate briefing for a single deal."""
    deal_uuid = deal[_I["deal_col_id"]]
    deal_name = deal.get(_I["deal_col_deal_name"]) or "?"
    stage = deal.get(_I["deal_col_stage"]) or ""
    meeting_type = _detect_meeting_type(stage)

    print(f"    BRIEFING: {deal_name} ({meeting_type})")

    from src.lang import get_lang_prompt
    team = deal.get(_I["deal_col_team"]) or ""
    system_prompt = _build_system_prompt(meeting_type)
    lang_text = get_lang_prompt(team)
    if lang_text:
        system_prompt += "\n\n" + lang_text
    user_prompt = _build_user_prompt(deal)

    print(f"    Claude ({len(user_prompt)} chars)...")
    try:
        raw = claude.analyze(system_prompt, user_prompt, model=MODEL_DEFAULT, max_tokens=MAX_TOKENS_AUDIT)
        text = re.sub(r"^```(?:json)?\s*", "", raw.strip())
        text = re.sub(r"\s*```$", "", text).strip()
        brief = json.loads(text)
    except Exception as e:
        print(f"    ✗ Claude failed: {e}")
        return None

    row = {
        "deal_id": deal_uuid,
        "deal_name": deal_name,
        "meeting_type": meeting_type.split("_")[-1] if "_" in meeting_type else meeting_type,
        "brief": json.dumps(brief, ensure_ascii=False),
        "status": "ready",
    }

    try:
        supabase.table(_H["briefings_table"]).insert(row).execute()
        print(f"    ✓ Briefing ready")
        return row
    except Exception as e:
        print(f"    ✗ Write failed: {e}")
        return None


def run(meetings_map: dict[str, dict]) -> int:
    """Generate briefings for deals with meetings today that don't have one yet.
    meetings_map: {deal_uuid: {team: str}} from meetings.detect_today()."""
    if not meetings_map:
        return 0

    deal_ids = list(meetings_map.keys())
    existing = _already_has_briefing(deal_ids)
    new_ids = [did for did in deal_ids if did not in existing]

    if not new_ids:
        print("    All meetings already have briefings")
        return 0

    print(f"    {len(new_ids)} deals need briefings")

    generated = 0
    for deal_uuid in new_ids:
        deal_resp = (
            supabase.table(_I["deals_table"])
            .select("*")
            .eq(_I["deal_col_id"], deal_uuid)
            .limit(1)
            .execute()
        )
        if not deal_resp.data:
            continue
        result = generate_briefing(deal_resp.data[0])
        if result:
            generated += 1

    return generated
