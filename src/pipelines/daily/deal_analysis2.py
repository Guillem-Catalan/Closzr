"""
Daily Deal Analysis v2 — post-mortem for closed deals.

Runs after trajectories. Detects deals that have a trajectory but no analysis.
For each one: 1 Claude call with full context → detailed analysis for TLs/UI.

Internal names everywhere: schema.tbl(), schema.col(), config2.*.
"""

import json
import re

from src import schema
from src.config2 import DAILY, PROMPTS_DIR, MODEL_DEFAULT, MAX_TOKENS, get_lang_prompt
from src.db.client import supabase
from src.integrations import claude


# ═══════════════════════════════════════════════════════════════════════════
# RESOLVED CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════

_TBL_DEALS          = schema.tbl("deals")
_TBL_SNAPSHOTS      = schema.tbl("snapshots")
_TBL_TRAJECTORIES   = schema.tbl("trajectories")
_TBL_ANALYSIS       = schema.tbl("analysis")
_TBL_PRODUCT_SIGNALS = schema.tbl("product_signals")

_D_UUID       = schema.col("deal_uuid")
_D_NAME       = schema.col("deal_name")
_D_STAGE      = schema.col("stage")
_D_MRR        = schema.col("mrr")
_D_AGE        = schema.col("deal_age")
_D_CLOSE_DATE = schema.col("close_date")
_D_PAE        = schema.col("pae")
_D_PBD        = schema.col("pbd")
_D_TEAM       = schema.col("team")
_D_CONTEXT    = schema.col("deal_context")
_D_LOST_REASON = schema.col("closed_lost_reason")

_FK_DEAL_ID       = "deal_id"
_FK_SNAPSHOT_DATE  = schema.SNAPSHOT_IDENTITY_COLS["snapshot_date"]

_SNAP_TRAJ_COLS   = schema.TRAJECTORY_SNAPSHOT_COLS


# ═══════════════════════════════════════════════════════════════════════════
# FETCHERS
# ═══════════════════════════════════════════════════════════════════════════

def _fetch_deals_without_analysis() -> list[dict]:
    """Deals that have trajectory but no analysis yet."""
    traj_resp = (
        supabase.table(_TBL_TRAJECTORIES)
        .select(f"{_FK_DEAL_ID}, outcome")
        .order("created_at", desc=True)
        .limit(200)
        .execute()
    )
    if not traj_resp.data:
        return []
    traj_map = {r[_FK_DEAL_ID]: r.get("outcome") for r in traj_resp.data}
    traj_deal_ids = list(traj_map.keys())

    analysis_resp = (
        supabase.table(_TBL_ANALYSIS)
        .select(f"{_FK_DEAL_ID}, outcome")
        .in_(_FK_DEAL_ID, traj_deal_ids)
        .execute()
    )
    analysis_map = {r[_FK_DEAL_ID]: r.get("outcome") for r in (analysis_resp.data or [])}

    new_ids = []
    for did in traj_deal_ids:
        if did not in analysis_map:
            new_ids.append(did)
        elif analysis_map[did] == "on_hold" and traj_map[did] in ("won", "lost"):
            new_ids.append(did)

    if not new_ids:
        return []

    deals_resp = (
        supabase.table(_TBL_DEALS)
        .select("*")
        .in_(_D_UUID, new_ids[:DAILY["analysis_max"]])
        .execute()
    )
    return deals_resp.data or []


def _determine_outcome(stage: str) -> str:
    if stage in schema.WON:
        return "won"
    if stage in schema.LOST:
        return "lost"
    if stage in schema.STALLED:
        return "on_hold"
    return "unknown"


def _fetch_all_snapshots(deal_uuid: str) -> list[dict]:
    cols = ", ".join(_SNAP_TRAJ_COLS)
    resp = (
        supabase.table(_TBL_SNAPSHOTS)
        .select(cols)
        .eq(_FK_DEAL_ID, deal_uuid)
        .order(_FK_SNAPSHOT_DATE)
        .execute()
    )
    return resp.data or []


def _fetch_product_signals(deal_uuid: str) -> list[dict]:
    resp = (
        supabase.table(_TBL_PRODUCT_SIGNALS)
        .select("*")
        .eq(_FK_DEAL_ID, deal_uuid)
        .order(_FK_SNAPSHOT_DATE, desc=True)
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


# ═══════════════════════════════════════════════════════════════════════════
# PROMPT
# ═══════════════════════════════════════════════════════════════════════════

def _build_user_prompt(deal: dict, snapshots: list[dict], stage_dates: dict, product_signals: list[dict]) -> str:
    outcome = _determine_outcome(deal.get(_D_STAGE) or "")
    deal_context = deal.get(_D_CONTEXT) or ""

    lines = []

    lines.append("## DEAL METADATA")
    lines.append(f"- Name: {deal.get(_D_NAME) or '?'}")
    lines.append(f"- Outcome: {outcome}")
    lines.append(f"- Amount: €{deal.get(_D_MRR) or '?'}")
    lines.append(f"- Deal Age: {deal.get(_D_AGE) or '?'} days")
    lines.append(f"- Stage: {deal.get(_D_STAGE) or '?'}")
    lines.append(f"- PAE: {deal.get(_D_PAE) or '?'}")
    lines.append(f"- PBD: {deal.get(_D_PBD) or '?'}")
    lines.append(f"- Team: {deal.get(_D_TEAM) or '?'}")
    lines.append(f"- Close Date: {deal.get(_D_CLOSE_DATE) or '?'}")
    lines.append(f"- Closed Lost Reason: {deal.get(_D_LOST_REASON) or 'N/A'}")
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
        lines.append(f"  {s.get(_FK_SNAPSHOT_DATE, '?')}: prob={prob}% | {scores}")
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


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def analyze_deal(deal: dict) -> dict | None:
    """Generate post-mortem analysis for a single closed deal."""
    deal_uuid = deal[_D_UUID]
    deal_name = deal.get(_D_NAME) or "?"
    stage = deal.get(_D_STAGE) or ""
    outcome = _determine_outcome(stage)

    print(f"    ANALYSIS: {deal_name} ({outcome})")

    snapshots = _fetch_all_snapshots(deal_uuid)
    stage_dates = _build_stage_dates(deal)
    product_signals = _fetch_product_signals(deal_uuid)

    team = deal.get(_D_TEAM) or ""
    owner_email = deal.get(_D_PAE) or deal.get(_D_PBD)
    system_prompt = (PROMPTS_DIR / DAILY["analysis_prompt"]).read_text(encoding="utf-8").strip()
    lang_text = get_lang_prompt(team, owner_email=owner_email)
    if lang_text:
        system_prompt += "\n\n" + lang_text
    user_prompt = _build_user_prompt(deal, snapshots, stage_dates, product_signals)

    print(f"    Claude ({len(user_prompt)} chars)...")
    try:
        raw = claude.analyze(system_prompt, user_prompt, model=MODEL_DEFAULT, max_tokens=MAX_TOKENS["audit"])
        parsed = _parse_response(raw)
    except Exception as e:
        print(f"    ✗ Claude failed: {e}")
        return None

    row = {
        _FK_DEAL_ID: deal_uuid,
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
        supabase.table(_TBL_ANALYSIS).upsert(row, on_conflict=_FK_DEAL_ID).execute()
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
