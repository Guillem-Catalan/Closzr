"""
Daily Trajectories — compiles closed deals into learning data.

Detects deals that closed (won/lost/on_hold) since the last daily run
and don't have a trajectory yet. For each one:
  1. Compiles full history (snapshots, stage dates, interactions)
  2. 1 Claude call → outcome analysis + lessons
  3. Writes to deal_trajectories

The forecast uses deal_trajectories as benchmark for predicting active deals.
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
    get_subteam,
)
from src.db.client import supabase
from src.integrations import claude

_I = INTELLIGENCE_CONFIG
_D = DAILY_CONFIG


def _fetch_deals_to_compile() -> list[dict]:
    """Find deals that need trajectory compilation.
    - Closed (won/lost): only if no trajectory exists (one shot)
    - On Hold: if no trajectory OR if previously compiled as on_hold but now closed (redo)
    """
    all_stages = _D["closed_stages"] + _D["on_hold_stages"]

    # Paginate to avoid payload too large
    all_deals = []
    offset = 0
    while True:
        deals_resp = (
            supabase.table(_I["deals_table"])
            .select("*")
            .in_(_I["deal_col_stage"], all_stages)
            .not_.is_("deal_context", "null")
            .range(offset, offset + 499)
            .execute()
        )
        batch = deals_resp.data or []
        all_deals.extend(batch)
        if len(batch) < 500 or len(all_deals) >= _D["trajectories_max_per_run"] * 3:
            break
        offset += 500

    if not all_deals:
        return []

    deal_ids = [d[_I["deal_col_id"]] for d in all_deals]

    # Filter to deals that have snapshots (no snapshots = no trajectory data)
    has_snapshot: set[str] = set()
    for i in range(0, len(deal_ids), 200):
        batch = deal_ids[i:i + 200]
        snap_resp = (
            supabase.table(_I["snapshot_table"])
            .select("deal_id")
            .in_("deal_id", batch)
            .execute()
        )
        has_snapshot.update(d["deal_id"] for d in (snap_resp.data or []))

    all_deals = [d for d in all_deals if d[_I["deal_col_id"]] in has_snapshot]
    deal_ids = [d[_I["deal_col_id"]] for d in all_deals]

    if not all_deals:
        return []

    # Check existing trajectories in batches
    existing = {}
    for i in range(0, len(deal_ids), 200):
        batch = deal_ids[i:i + 200]
        existing_resp = (
            supabase.table(_D["trajectories_table"])
            .select("deal_id, outcome")
            .in_(_D["fk_deal_id"], batch)
            .execute()
        )
        for r in (existing_resp.data or []):
            existing[r["deal_id"]] = r.get("outcome")

    result = []
    for d in all_deals:
        did = d[_I["deal_col_id"]]
        stage = d.get(_I["deal_col_stage"]) or ""

        if did not in existing:
            result.append(d)
        elif existing[did] == "on_hold" and stage in _D["closed_stages"]:
            result.append(d)

    return result[:_D["trajectories_max_per_run"]]


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


def _build_trajectory(snapshots: list[dict], close_date: str | None) -> list[dict]:
    trajectory = []
    for s in snapshots:
        days_before = None
        if close_date and s.get(_I["fk_snapshot_date"]):
            try:
                cd = date.fromisoformat(str(close_date)[:10])
                sd = date.fromisoformat(str(s[_I["fk_snapshot_date"]])[:10])
                days_before = (cd - sd).days
            except (ValueError, TypeError):
                pass

        trajectory.append({
            "date": s.get(_I["fk_snapshot_date"]),
            "days_before_close": days_before,
            "probability": s.get("close_probability"),
            "meddic": {
                "m": s.get("m_score"), "e": s.get("e_score"),
                "dc": s.get("dc_score"), "dp": s.get("dp_score"),
                "i": s.get("i_score"), "c": s.get("c_score"),
                "comp": s.get("comp_score"),
            },
            "signals": s.get("buyer_signals") or "",
            "blockers": s.get("live_blockers") or "",
            "next_step": s.get("next_step") or "",
            "assessment": s.get("deal_assessment") or "",
        })
    return trajectory


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


def _count_interactions(deal: dict, deal_uuid: str) -> dict:
    calls_resp = supabase.table(_I["calls_table"]).select("id").eq(_I["fk_deal_id"], deal_uuid).execute()
    from src.config import SYNC_CONFIG
    meetings_resp = supabase.table(SYNC_CONFIG["meetings_table"]).select("id").eq(SYNC_CONFIG["meetings_col_deal_id"], deal_uuid).execute()

    return {
        "total_calls": deal.get("numero_de_calls") or 0,
        "total_emails": deal.get("numero_de_emails") or 0,
        "total_notes": deal.get("numero_de_notas") or 0,
        "modjo_calls": len(calls_resp.data or []),
        "hs_meetings": len(meetings_resp.data or []),
    }


def _resolve_team(deal: dict) -> str:
    pae = deal.get(_I["deal_col_pae"]) or ""
    pbd = deal.get(_I["deal_col_pbd"]) or ""
    team = deal.get(_I["deal_col_team"]) or ""
    if team:
        return team
    return ""


def _build_user_prompt(deal: dict, trajectory: list[dict], stage_dates: dict) -> str:
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

    lines.append(f"## TRAJECTORY ({len(trajectory)} snapshots)")
    for t in trajectory:
        prob = t.get("probability", "?")
        days = t.get("days_before_close", "?")
        m = t["meddic"]
        scores = f"M={m.get('m','?')} E={m.get('e','?')} DC={m.get('dc','?')} DP={m.get('dp','?')} I={m.get('i','?')} C={m.get('c','?')}"
        signals = t.get("signals") or "-"
        blockers = t.get("blockers") or "-"
        lines.append(f"  {t.get('date', '?')} ({days}d before close): prob={prob}% | {scores}")
        lines.append(f"    Signals: {signals}")
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


def compile_trajectory(deal: dict) -> dict | None:
    """Compile trajectory for a single closed deal."""
    deal_uuid = deal[_I["deal_col_id"]]
    deal_name = deal.get(_I["deal_col_deal_name"]) or "?"
    stage = deal.get(_I["deal_col_stage"]) or ""
    outcome = _determine_outcome(stage)

    print(f"    TRAJECTORY: {deal_name} ({outcome})")

    snapshots = _fetch_all_snapshots(deal_uuid)
    trajectory = _build_trajectory(snapshots, deal.get(_I["deal_col_close_date"]))
    stage_dates = _build_stage_dates(deal)
    interactions = _count_interactions(deal, deal_uuid)
    team = _resolve_team(deal)

    from src.lang import get_lang_prompt
    system_prompt = (PROMPTS_DIR / _D["trajectories_prompt_path"]).read_text(encoding="utf-8").strip()
    lang_text = get_lang_prompt(team)
    if lang_text:
        system_prompt += "\n\n" + lang_text
    user_prompt = _build_user_prompt(deal, trajectory, stage_dates)

    print(f"    Claude ({len(user_prompt)} chars)...")
    try:
        raw = claude.analyze(system_prompt, user_prompt, model=MODEL_DEFAULT, max_tokens=MAX_TOKENS_AUDIT)
        parsed = _parse_response(raw)
    except Exception as e:
        print(f"    ✗ Claude failed: {e}")
        parsed = {}

    lessons = parsed.get("lessons") or []
    if isinstance(lessons, str):
        try:
            lessons = json.loads(lessons)
        except (json.JSONDecodeError, TypeError):
            lessons = [lessons]

    row = {
        "deal_id": deal_uuid,
        "outcome": outcome,
        "amount": deal.get(_I["deal_col_amount"]),
        "deal_age_days": deal.get(_I["deal_col_age"]),
        "pae": deal.get(_I["deal_col_pae"]),
        "pbd": deal.get(_I["deal_col_pbd"]),
        "team": team,
        "pipeline_name": deal.get("pipeline_name"),
        "closed_lost_reason": deal.get("closed_lost_reason"),
        "close_date": deal.get(_I["deal_col_close_date"]),
        "trajectory": json.dumps(trajectory),
        "stage_dates": json.dumps(stage_dates),
        "interactions": json.dumps(interactions),
        "lessons": json.dumps(lessons, ensure_ascii=False),
        "outcome_analysis": parsed.get("outcome_analysis") or "",
        "key_turning_point": parsed.get("key_turning_point") or "",
    }
    row = {k: v for k, v in row.items() if v is not None}

    try:
        supabase.table(_D["trajectories_table"]).upsert(row, on_conflict="deal_id").execute()
        print(f"    ✓ Trajectory written ({len(trajectory)} snapshots, {len(lessons)} lessons)")
        return row
    except Exception as e:
        print(f"    ✗ Write failed: {e}")
        return None


def run() -> int:
    """Compile trajectories for all newly closed deals."""
    print("\n  TRAJECTORIES: detecting closed deals without trajectory...")

    deals = _fetch_deals_to_compile()
    if not deals:
        print("    No new closed deals to process")
        return 0

    print(f"    {len(deals)} deals to compile")

    compiled = 0
    for deal in deals:
        result = compile_trajectory(deal)
        if result:
            compiled += 1

    print(f"    {compiled}/{len(deals)} trajectories compiled")
    return compiled
