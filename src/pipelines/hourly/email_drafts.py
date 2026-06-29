"""
Generate email drafts for deals where the primary action is EMAIL.
1 Claude call (Sonnet) per deal without a current draft.
Drafts persist until CORE changes the action.
Everything from config.
"""

import json
import re
from datetime import date

from src.config import (
    INTELLIGENCE_CONFIG,
    HOURLY_CONFIG,
    PARSER_CONFIG,
    PROMPTS_DIR,
    MODEL_DEFAULT,
    MAX_TOKENS_EMAIL_DRAFT,
)
from src.db.client import supabase
from src.integrations import claude

_I = INTELLIGENCE_CONFIG
_H = HOURLY_CONFIG
_P = PARSER_CONFIG
TODAY = date.today().isoformat()


def _fetch_deals_needing_draft() -> list[dict]:
    """Deals where action_type=EMAIL in deal_ui and no current draft exists."""
    # Get deals with EMAIL action
    ui_resp = (
        supabase.table(_P["table"])
        .select("deal_id, action_headline, action_who, snapshot_date")
        .eq("action_type", "EMAIL")
        .execute()
    )
    if not ui_resp.data:
        return []

    deal_ids = [r["deal_id"] for r in ui_resp.data]
    ui_map = {r["deal_id"]: r for r in ui_resp.data}

    # Check which already have a draft for the current action
    draft_resp = (
        supabase.table(_H["email_drafts_table"])
        .select("deal_id, action_headline")
        .in_("deal_id", deal_ids)
        .execute()
    )
    existing = {}
    for d in (draft_resp.data or []):
        existing[d["deal_id"]] = d.get("action_headline") or ""

    # Need draft if: no draft exists OR draft is for a different action
    needs_draft = []
    for deal_id in deal_ids:
        current_headline = ui_map[deal_id].get("action_headline") or ""
        existing_headline = existing.get(deal_id, "")
        if not existing_headline or existing_headline != current_headline:
            needs_draft.append(deal_id)

    if not needs_draft:
        return []

    # Fetch full deal data
    deals_resp = (
        supabase.table(_I["deals_table"])
        .select("*")
        .in_(_I["deal_col_id"], needs_draft[:20])
        .execute()
    )
    return deals_resp.data or []


def _build_user_prompt(deal: dict, action_headline: str) -> str:
    hs_deal_id = deal.get(_I["deal_col_deal_id"]) or ""
    lines = []

    lines.append("## DEAL")
    lines.append(f"- Name: {deal.get(_I['deal_col_deal_name']) or '?'}")
    lines.append(f"- Stage: {deal.get(_I['deal_col_stage']) or '?'}")
    lines.append(f"- MRR: €{deal.get(_I['deal_col_amount']) or '?'}")
    lines.append(f"- PAE: {deal.get(_I['deal_col_pae']) or '?'}")
    lines.append(f"- PBD: {deal.get(_I['deal_col_pbd']) or '?'}")
    lines.append("")

    lines.append("## ACTION — WHAT EMAIL TO SEND")
    lines.append(action_headline)
    lines.append("")

    # Snapshot context
    if hs_deal_id:
        snap_resp = (
            supabase.table(_I["snapshot_table"])
            .select("deal_summary, deal_assessment, next_step, buyer_signals, live_blockers")
            .eq(_I["fk_hs_deal_id"], hs_deal_id)
            .order(_I["fk_snapshot_date"], desc=True)
            .limit(1)
            .execute()
        )
        if snap_resp.data:
            s = snap_resp.data[0]
            lines.append("## SNAPSHOT CONTEXT")
            lines.append(f"Summary: {s.get('deal_summary') or '-'}")
            lines.append(f"Assessment: {s.get('deal_assessment') or '-'}")
            lines.append(f"Next Steps: {s.get('next_step') or '-'}")
            lines.append(f"Signals: {s.get('buyer_signals') or '-'}")
            lines.append(f"Blockers: {s.get('live_blockers') or '-'}")
            lines.append("")

    # Deal context (last 3000 chars — enough for email context)
    deal_context = deal.get(_I["deal_context_col"]) or ""
    if deal_context:
        lines.append("## RECENT DEAL CONTEXT")
        lines.append(deal_context[-3000:])

    return "\n".join(lines)


def generate_draft(deal: dict, action_headline: str) -> dict | None:
    """Generate email draft for a single deal."""
    deal_uuid = deal[_I["deal_col_id"]]
    deal_name = deal.get(_I["deal_col_deal_name"]) or "?"

    print(f"    EMAIL DRAFT: {deal_name}")

    from src.lang import get_lang_prompt
    team = deal.get(_I["deal_col_team"]) or ""
    system_prompt = (PROMPTS_DIR / _H["email_draft_prompt"]).read_text(encoding="utf-8").strip()
    lang_text = get_lang_prompt(team)
    if lang_text:
        system_prompt += "\n\n" + lang_text
    user_prompt = _build_user_prompt(deal, action_headline)

    print(f"    Claude ({len(user_prompt)} chars)...")
    try:
        raw = claude.analyze(system_prompt, user_prompt, model=MODEL_DEFAULT, max_tokens=MAX_TOKENS_EMAIL_DRAFT)
        text = re.sub(r"^```(?:json)?\s*", "", raw.strip())
        text = re.sub(r"\s*```$", "", text).strip()
        draft = json.loads(text)
    except Exception as e:
        print(f"    ✗ Claude failed: {e}")
        return None

    row = {
        "deal_id": deal_uuid,
        "deal_name": deal_name,
        "action_headline": action_headline,
        "subject": draft.get("subject") or "",
        "body": draft.get("body") or "",
        "to_description": draft.get("to_description") or "",
        "status": "draft",
    }

    try:
        supabase.table(_H["email_drafts_table"]).upsert(row, on_conflict="deal_id").execute()
        print(f"    ✓ Draft ready")
        return row
    except Exception as e:
        print(f"    ✗ Write failed: {e}")
        return None


def run() -> int:
    """Generate email drafts for deals with EMAIL action and no current draft."""
    deals = _fetch_deals_needing_draft()
    if not deals:
        print("    No deals need email drafts")
        return 0

    print(f"    {len(deals)} deals need email drafts")

    # Get action headlines from deal_ui
    deal_ids = [d[_I["deal_col_id"]] for d in deals]
    ui_resp = (
        supabase.table(_P["table"])
        .select("deal_id, action_headline")
        .in_("deal_id", deal_ids)
        .execute()
    )
    headline_map = {r["deal_id"]: r.get("action_headline") or "" for r in (ui_resp.data or [])}

    generated = 0
    for deal in deals:
        deal_uuid = deal[_I["deal_col_id"]]
        headline = headline_map.get(deal_uuid, "")
        if not headline:
            continue
        result = generate_draft(deal, headline)
        if result:
            generated += 1

    return generated
