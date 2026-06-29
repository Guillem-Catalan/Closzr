"""
Daily Deal Analysis — post-mortem for closed deals.

Runs after trajectories. Detects deals that have a trajectory but no analysis.
For each one: 1 Claude call with full context → detailed analysis for TLs/UI.

Everything from config.
"""

import json
import re
from datetime import date

from src.config import (
    INTELLIGENCE_CONFIG,
    DAILY_CONFIG,
    PROMPTS_DIR,
    MODEL_DEFAULT,
    MAX_TOKENS_AUDIT,
)
from src.db.client import supabase
from src.integrations import claude

_I = INTELLIGENCE_CONFIG
_D = DAILY_CONFIG


def _fetch_deals_without_analysis() -> list[dict]:
    """Deals that have trajectory but no analysis yet.
    Also re-analyzes on_hold deals that later closed."""
    traj_resp = (
        supabase.table(_D["trajectories_table"])
        .select("deal_id, outcome")
        .order("created_at", desc=True)
        .limit(200)
        .execute()
    )
    if not traj_resp.data:
        return []
    traj_map = {r[_D["fk_deal_id"]]: r.get("outcome") for r in traj_resp.data}
    traj_deal_ids = list(traj_map.keys())

    analysis_resp = (
        supabase.table(_D["analysis_table"])
        .select("deal_id, outcome")
        .in_(_D["fk_deal_id"], traj_deal_ids)
        .execute()
    )
    analysis_map = {r[_D["fk_deal_id"]]: r.get("outcome") for r in (analysis_resp.data or [])}

    new_ids = []
    for did in traj_deal_ids:
        if did not in analysis_map:
            new_ids.append(did)
        elif analysis_map[did] == "on_hold" and traj_map[did] in ("won", "lost"):
            new_ids.append(did)

    if not new_ids:
        return []

    deals_resp = (
        supabase.table(_I["deals_table"])
        .select("*")
        .in_(_I["deal_col_id"], new_ids[:_D["analysis_max_per_run"]])
        .execute()
    )
    return deals_resp.data or []


def _determine_outcome(stage: str) -> str:
    from src.config import STAGE_WON, STAGE_LOST
    if stage in STAGE_WON:
        return "won"
    if stage in STAGE_LOST:
        return "lost"
    if stage in _D["on_hold_stages"]:
        return "on_hold"
    return "unknown"


def _fetch_all_snapshots(deal_uuid: str) -> list[dict]:
    cols = ", ".join(_D["snapshot_trajectory_cols"])
    resp = (
        supabase.table(_I["snapshot_table"])
        .select(cols)
        .eq(_I["fk_deal_id"], deal_uuid)
        .order(_I["fk_snapshot_date"])
        .execute()
    )
    return resp.data or []


def _fetch_product_signals(deal_uuid: str) -> list[dict]:
    resp = (
        supabase.table(_I["product_signals_table"])
        .select("*")
        .eq(_D["fk_deal_id"], deal_uuid)
        .order("snapshot_date", desc=True)
        .limit(5)
        .execute()
    )
    return resp.data or []


def _build_stage_dates(deal: dict) -> dict:
    stage_dates = {}
    for col_name, val in deal.items():
        if col_name.endswith("_entered") and val:
            key = col_name.replace("_entered", "")
            stage_dates[key] = {"entered": str(val)}
        elif col_name.endswith("_exited") and val:
            key = col_name.replace("_exited", "")
            if key not in stage_dates:
                stage_dates[key] = {}
            stage_dates[key]["exited"] = str(val)
    return stage_dates


def _build_user_prompt(deal: dict, snapshots: list[dict], stage_dates: dict, product_signals: list[dict]) -> str:
    outcome = _determine_outcome(deal.get(_I["deal_col_stage"]) or "")
    deal_context = deal.get(_I["deal_context_col"]) or ""

    lines = []

    lines.append("## DEAL METADATA")
    lines.append(f"- Name: {deal.get(_I['deal_col_deal_name']) or '?'}")
    lines.append(f"- Outcome: {outcome}")
    lines.append(f"- Amount: €{deal.get(_I['deal_col_amount']) or '?'}")
    lines.append(f"- Deal Age: {deal.get(_I['deal_col_age']) or '?'} days")
    lines.append(f"- Stage: {deal.get(_I['deal_col_stage']) or '?'}")
    lines.append(f"- PAE: {deal.get(_I['deal_col_pae']) or '?'}")
    lines.append(f"- PBD: {deal.get(_I['deal_col_pbd']) or '?'}")
    lines.append(f"- Team: {deal.get(_I['deal_col_team']) or '?'}")
    lines.append(f"- Close Date: {deal.get(_I['deal_col_close_date']) or '?'}")
    lines.append(f"- Closed Lost Reason: {deal.get('closed_lost_reason') or 'N/A'}")
    lines.append("")

    lines.append("## DEAL CONTEXT — FULL HISTORY")
    lines.append(deal_context if deal_context else "(no deal context)")
    lines.append("")

    lines.append(f"## SNAPSHOT TRAJECTORY ({len(snapshots)} snapshots)")
    for s in snapshots:
        prob = s.get("close_probability", "?")
        scores = " | ".join(
            f"{k}={s.get(f'{k}_score', '?')}"
            for k in ["m", "e", "dc", "dp", "i", "c", "comp"]
        )
        lines.append(f"  {s.get(_I['fk_snapshot_date'], '?')}: prob={prob}% | {scores}")
        assessment = s.get("deal_assessment") or ""
        if assessment:
            lines.append(f"    Assessment: {assessment}")
        signals = s.get("buyer_signals") or ""
        if signals:
            lines.append(f"    Signals: {signals}")
        blockers = s.get("live_blockers") or ""
        if blockers:
            lines.append(f"    Blockers: {blockers}")
    lines.append("")

    lines.append("## STAGE DATES")
    for stage_key, dates in stage_dates.items():
        entered = dates.get("entered", "?")
        exited = dates.get("exited", "")
        line = f"  {stage_key}: entered {entered}"
        if exited:
            line += f" → exited {exited}"
        lines.append(line)
    lines.append("")

    lines.append("## PRODUCT SIGNALS")
    if product_signals:
        for ps in product_signals:
            products = ps.get("products_discussed") or "[]"
            if isinstance(products, str):
                try:
                    products = json.loads(products)
                except (json.JSONDecodeError, TypeError):
                    products = []
            for p in (products if isinstance(products, list) else []):
                lines.append(f"  - {p.get('product', '?')}: {p.get('context', '')} ({p.get('reception', '?')})")
            upsell = ps.get("upsell_opportunity")
            if upsell:
                if isinstance(upsell, str):
                    try:
                        upsell = json.loads(upsell)
                    except (json.JSONDecodeError, TypeError):
                        upsell = {}
                if isinstance(upsell, dict) and upsell.get("detected"):
                    lines.append(f"  Upsell: {upsell.get('product', '?')} — {upsell.get('reason', '')}")
    else:
        lines.append("  (no product signals recorded)")

    return "\n".join(lines)


def _parse_response(text: str) -> dict:
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start:end + 1])
        raise


def analyze_deal(deal: dict) -> dict | None:
    """Generate post-mortem analysis for a single closed deal."""
    deal_uuid = deal[_I["deal_col_id"]]
    deal_name = deal.get(_I["deal_col_deal_name"]) or "?"
    stage = deal.get(_I["deal_col_stage"]) or ""
    outcome = _determine_outcome(stage)

    print(f"    ANALYSIS: {deal_name} ({outcome})")

    snapshots = _fetch_all_snapshots(deal_uuid)
    stage_dates = _build_stage_dates(deal)
    product_signals = _fetch_product_signals(deal_uuid)

    from src.lang import get_lang_prompt
    team = deal.get(_I["deal_col_team"]) or ""
    system_prompt = (PROMPTS_DIR / _D["analysis_prompt_path"]).read_text(encoding="utf-8").strip()
    lang_text = get_lang_prompt(team)
    if lang_text:
        system_prompt += "\n\n" + lang_text
    user_prompt = _build_user_prompt(deal, snapshots, stage_dates, product_signals)

    print(f"    Claude ({len(user_prompt)} chars)...")
    try:
        raw = claude.analyze(system_prompt, user_prompt, model=MODEL_DEFAULT, max_tokens=MAX_TOKENS_AUDIT)
        parsed = _parse_response(raw)
    except Exception as e:
        print(f"    ✗ Claude failed: {e}")
        return None

    row = {
        "deal_id": deal_uuid,
        "outcome": outcome,
        "full_narrative": parsed.get("full_narrative") or "",
        "outcome_summary": parsed.get("outcome_summary") or "",
        "deal_timeline": json.dumps(parsed.get("deal_timeline") or [], ensure_ascii=False),
        "what_worked": json.dumps(parsed.get("what_worked") or [], ensure_ascii=False),
        "what_failed": json.dumps(parsed.get("what_failed") or [], ensure_ascii=False),
        "what_could_have_changed": parsed.get("what_could_have_changed") or "",
        "rep_assessment": parsed.get("rep_assessment") or "",
        "key_people": json.dumps(parsed.get("key_people") or [], ensure_ascii=False),
        "products_pitched": json.dumps(parsed.get("products_pitched") or [], ensure_ascii=False),
        "products_missed": json.dumps(parsed.get("products_missed") or [], ensure_ascii=False),
        "product_assessment": parsed.get("product_assessment") or "",
    }
    row = {k: v for k, v in row.items() if v is not None}

    try:
        supabase.table(_D["analysis_table"]).upsert(row, on_conflict="deal_id").execute()
        print(f"    ✓ Analysis written")
        return row
    except Exception as e:
        print(f"    ✗ Write failed: {e}")
        return None


def run() -> int:
    """Generate analysis for all closed deals that have trajectory but no analysis."""
    print("\n  DEAL ANALYSIS: detecting deals without analysis...")

    deals = _fetch_deals_without_analysis()
    if not deals:
        print("    No new deals to analyze")
        return 0

    print(f"    {len(deals)} deals to analyze")

    analyzed = 0
    for deal in deals:
        result = analyze_deal(deal)
        if result:
            analyzed += 1

    print(f"    {analyzed}/{len(deals)} analyses completed")
    return analyzed
