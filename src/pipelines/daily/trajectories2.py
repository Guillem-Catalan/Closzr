"""
Daily Trajectories v2 — compiles closed deals into learning data.

Detects deals that closed (won/lost/on_hold) since the last daily run
and don't have a trajectory yet. For each one:
  1. Compiles full history (snapshots, stage dates, interactions)
  2. 1 Claude call → outcome analysis + lessons
  3. Writes to deal_trajectories

Internal names everywhere: schema.tbl(), schema.col(), config2.*.
"""

import json
import re
from datetime import date

from src import schema
from src.config2 import DAILY, PROMPTS_DIR, MODEL_DEFAULT, MAX_TOKENS, get_lang_prompt
from src.db.client import supabase
from src.integrations import claude


# ═══════════════════════════════════════════════════════════════════════════
# RESOLVED CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════

_TBL_DEALS        = schema.tbl("deals")
_TBL_SNAPSHOTS    = schema.tbl("snapshots")
_TBL_TRAJECTORIES = schema.tbl("trajectories")
_TBL_CALLS        = schema.tbl("calls")
_TBL_MEETINGS     = schema.tbl("meetings")

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
_D_PIPELINE   = schema.col("pipeline")
_D_LOST_REASON = schema.col("closed_lost_reason")
_D_CALL_COUNT  = schema.col("call_count")
_D_EMAIL_COUNT = schema.col("email_count")
_D_NOTE_COUNT  = schema.col("note_count")

_FK_DEAL_ID       = "deal_id"
_FK_SNAPSHOT_DATE  = schema.SNAPSHOT_IDENTITY_COLS["snapshot_date"]
_FK_MEETINGS_DEAL  = "hs_deal_id"

_SNAP_TRAJ_COLS   = schema.TRAJECTORY_SNAPSHOT_COLS

_CLOSED_STAGES = list(schema.CLOSED)
_STALLED_STAGES = list(schema.STALLED)
_ALL_TERMINAL = _CLOSED_STAGES + _STALLED_STAGES


# ═══════════════════════════════════════════════════════════════════════════
# FETCHERS
# ═══════════════════════════════════════════════════════════════════════════

def _fetch_deals_to_compile() -> list[dict]:
    """Find deals that need trajectory compilation."""
    has_snapshot: set[str] = set()
    offset = 0
    while True:
        snap_resp = (
            supabase.table(_TBL_SNAPSHOTS)
            .select(_FK_DEAL_ID)
            .range(offset, offset + 999)
            .execute()
        )
        batch = snap_resp.data or []
        has_snapshot.update(d[_FK_DEAL_ID] for d in batch)
        if len(batch) < 1000:
            break
        offset += 1000

    if not has_snapshot:
        return []

    snapshot_ids = list(has_snapshot)
    all_deals = []
    for i in range(0, len(snapshot_ids), 200):
        batch = snapshot_ids[i:i + 200]
        deals_resp = (
            supabase.table(_TBL_DEALS)
            .select("*")
            .in_(_D_UUID, batch)
            .in_(_D_STAGE, _ALL_TERMINAL)
            .execute()
        )
        all_deals.extend(deals_resp.data or [])

    if not all_deals:
        return []

    deal_ids = [d[_D_UUID] for d in all_deals]

    existing = {}
    for i in range(0, len(deal_ids), 200):
        batch = deal_ids[i:i + 200]
        existing_resp = (
            supabase.table(_TBL_TRAJECTORIES)
            .select(f"{_FK_DEAL_ID}, outcome")
            .in_(_FK_DEAL_ID, batch)
            .execute()
        )
        for r in (existing_resp.data or []):
            existing[r[_FK_DEAL_ID]] = r.get("outcome")

    result = []
    for d in all_deals:
        did = d[_D_UUID]
        stage = d.get(_D_STAGE) or ""

        if did not in existing:
            result.append(d)
        elif existing[did] == "on_hold" and stage in _CLOSED_STAGES:
            result.append(d)

    return result[:DAILY["trajectories_max"]]


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


def _build_trajectory(snapshots: list[dict], close_date: str | None) -> list[dict]:
    trajectory = []
    for s in snapshots:
        days_before = None
        if close_date and s.get(_FK_SNAPSHOT_DATE):
            try:
                cd = date.fromisoformat(str(close_date)[:10])
                sd = date.fromisoformat(str(s[_FK_SNAPSHOT_DATE])[:10])
                days_before = (cd - sd).days
            except (ValueError, TypeError):
                pass

        trajectory.append({
            "date": s.get(_FK_SNAPSHOT_DATE),
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
    calls_resp = supabase.table(_TBL_CALLS).select("id").eq(_FK_DEAL_ID, deal_uuid).execute()
    meetings_resp = supabase.table(_TBL_MEETINGS).select("id").eq(_FK_MEETINGS_DEAL, deal_uuid).execute()

    return {
        "total_calls": deal.get(_D_CALL_COUNT) or 0,
        "total_emails": deal.get(_D_EMAIL_COUNT) or 0,
        "total_notes": deal.get(_D_NOTE_COUNT) or 0,
        "modjo_calls": len(calls_resp.data or []),
        "hs_meetings": len(meetings_resp.data or []),
    }


def _resolve_team(deal: dict) -> str:
    return deal.get(_D_TEAM) or ""


# ═══════════════════════════════════════════════════════════════════════════
# PROMPT
# ═══════════════════════════════════════════════════════════════════════════

def _build_user_prompt(deal: dict, trajectory: list[dict], stage_dates: dict) -> str:
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


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def compile_trajectory(deal: dict) -> dict | None:
    """Compile trajectory for a single closed deal."""
    deal_uuid = deal[_D_UUID]
    deal_name = deal.get(_D_NAME) or "?"
    stage = deal.get(_D_STAGE) or ""
    outcome = _determine_outcome(stage)

    print(f"    TRAJECTORY: {deal_name} ({outcome})")

    snapshots = _fetch_all_snapshots(deal_uuid)
    trajectory = _build_trajectory(snapshots, deal.get(_D_CLOSE_DATE))
    stage_dates = _build_stage_dates(deal)
    interactions = _count_interactions(deal, deal_uuid)
    team = _resolve_team(deal)

    owner_email = deal.get(_D_PAE) or deal.get(_D_PBD)
    system_prompt = (PROMPTS_DIR / DAILY["trajectories_prompt"]).read_text(encoding="utf-8").strip()
    lang_text = get_lang_prompt(team, owner_email=owner_email)
    if lang_text:
        system_prompt += "\n\n" + lang_text
    user_prompt = _build_user_prompt(deal, trajectory, stage_dates)

    print(f"    Claude ({len(user_prompt)} chars)...")
    try:
        raw = claude.analyze(system_prompt, user_prompt, model=MODEL_DEFAULT, max_tokens=MAX_TOKENS["audit"])
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
        _FK_DEAL_ID: deal_uuid,
        "outcome": outcome,
        "amount": deal.get(_D_MRR),
        "deal_age_days": deal.get(_D_AGE),
        "pae": deal.get(_D_PAE),
        "pbd": deal.get(_D_PBD),
        "team": team,
        "pipeline_name": deal.get(_D_PIPELINE),
        "closed_lost_reason": deal.get(_D_LOST_REASON),
        "close_date": deal.get(_D_CLOSE_DATE),
        "trajectory": json.dumps(trajectory),
        "stage_dates": json.dumps(stage_dates),
        "interactions": json.dumps(interactions),
        "lessons": json.dumps(lessons, ensure_ascii=False),
        "outcome_analysis": parsed.get("outcome_analysis") or "",
        "key_turning_point": parsed.get("key_turning_point") or "",
    }
    row = {k: v for k, v in row.items() if v is not None}

    try:
        supabase.table(_TBL_TRAJECTORIES).upsert(row, on_conflict=_FK_DEAL_ID).execute()
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
