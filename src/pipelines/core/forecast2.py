"""
Core Forecast v2 — Phase 4 of the CORE pipeline.

Entry point: run(deal_uuid, use_latest=False)

Changes vs v1:
  - All cols via schema.col() / schema.tbl()
  - All thresholds via config2.FORECAST
  - BUG FIX: today computed at call time (not module-level)
  - BUG FIX: calibration reads correct columns (predicted_close_date, not predicted_close_this_month)
  - BUG FIX: trajectory fetch includes claudio_close_date (prev_forecast was never found in v1)
  - Unified run() (no duplicate run_refresh — use_latest=True replaces it)
  - Patterns filtered by team scope (team-specific + global)
  - Similar deals scoring includes stage match bonus
  - New probability formula: MEDDIC base × activity_decay × momentum_multiplier
"""

import json
import re
from datetime import date, timedelta

from src import schema
from src.config2 import (
    PROMPTS_DIR, MODEL_OPUS, MAX_TOKENS, FORECAST,
    get_lang_prompt,
)
from src.db.client import supabase
from src.integrations import claude


# ═══════════════════════════════════════════════════════════════════════════
# RESOLVED CONSTANTS — computed once at import from schema / config2
# ═══════════════════════════════════════════════════════════════════════════

# ── Tables ──
_TBL_DEALS = schema.tbl("deals")
_TBL_SNAPSHOTS = schema.tbl("snapshots")
_TBL_TRAJECTORIES = schema.tbl("trajectories")
_TBL_PATTERNS = schema.tbl("patterns")
_TBL_CALIBRATION = schema.tbl("calibration")

# ── Deal columns (schema.col → Supabase column in deals table) ──
_D_UUID = schema.col("deal_uuid")
_D_ID = schema.col("deal_id")
_D_NAME = schema.col("deal_name")
_D_STAGE = schema.col("stage")
_D_MRR = schema.col("mrr")
_D_AGE = schema.col("deal_age")
_D_CLOSE = schema.col("close_date")
_D_PBD = schema.col("pbd")
_D_PAE = schema.col("pae")
_D_TEAM = schema.col("team")
_D_CONTEXT = schema.col("deal_context")
_D_LAST_CONTACT = schema.col("last_contacted")

# ── Snapshot columns ──
_SNAP_ID = schema.SNAPSHOT_IDENTITY_COLS
_S_HS_DEAL_ID = _SNAP_ID["hs_deal_id"]
_S_DATE = _SNAP_ID["snapshot_date"]
_S_DEAL_ID = _SNAP_ID["deal_id"]
# Snapshot data columns (keys from SNAPSHOT_METADATA = snapshot column names)
_S_MRR = "mrr"
_S_STAGE = "stage"

# ── Trajectory columns (deal_trajectories table) ──
_TC = schema.TRAJECTORY_COLS

# ── Patterns table columns (no schema mapping — stable table) ──
_P_PATTERN = "pattern"
_P_SCOPE = "scope"
_P_CONFIDENCE = "confidence"
_P_GENERATED_AT = "generated_at"

# ── Calibration table columns (no schema mapping — stable table) ──
_CAL_DEAL_NAME = "deal_name"
_CAL_PREDICTED_DATE = "predicted_close_date"
_CAL_ACTUAL = "actual_outcome"
_CAL_DAYS_OFF = "days_off"
_CAL_ERROR_TYPE = "error_type"
_CAL_ERROR_ANALYSIS = "error_analysis"
_CAL_MONTH = "month"

# ── Config ──
_F = FORECAST

# ── Schema groups ──
_CLAUDE_COLS = schema.FORECAST_CLAUDE_COLS
_COMPUTED_COLS = schema.FORECAST_COMPUTED_COLS
_TRAJ_COLS = schema.TRAJECTORY_SNAPSHOT_COLS

_SYS = schema.SYSTEM_COLS

_MEDDIC_DIMS = ["m", "e", "dc", "dp", "i", "c", "comp"]

# Snapshot Claude columns used for prompt (all members of schema.SNAPSHOT_CLAUDE_COLS)
_SC_ASSESSMENT = "deal_assessment"
_SC_SIGNALS = "buyer_signals"
_SC_BLOCKERS = "live_blockers"
_SC_NEXT_STEP = "next_step"

# Forecast Claude columns (all members of schema.FORECAST_CLAUDE_COLS)
_FC_CLOSE_DATE = "claudio_close_date"
_FC_CONFIDENCE = "forecast_confidence"
_FC_MOMENTUM = "deal_momentum"
_FC_PUSH_ACTION = "push_action"
_FC_PUSHABLE = "forecast_pushable"
_FC_REASONING = "forecast_reasoning"

# Forecast computed columns (schema.FORECAST_COMPUTED_COLS)
_FC_PROB = "close_probability"
_FC_FORECAST = "claudio_forecast"

_TRAJ_FETCH_COLS = list(dict.fromkeys(
    _TRAJ_COLS
    + [_FC_CLOSE_DATE, _FC_CONFIDENCE, _FC_REASONING,
       _FC_PUSH_ACTION, _FC_MOMENTUM, _S_STAGE]
))


# ═══════════════════════════════════════════════════════════════════════════
# FETCHERS
# ═══════════════════════════════════════════════════════════════════════════

def _fetch_deal(deal_uuid):
    resp = (
        supabase.table(_TBL_DEALS)
        .select("*")
        .eq(_D_UUID, deal_uuid)
        .limit(1)
        .execute()
    )
    return resp.data[0] if resp.data else None


def _fetch_snapshot(hs_deal_id, today, use_latest=False):
    query = (
        supabase.table(_TBL_SNAPSHOTS)
        .select("*")
        .eq(_S_HS_DEAL_ID, hs_deal_id)
    )
    if use_latest:
        query = query.order(_S_DATE, desc=True)
    else:
        query = query.eq(_S_DATE, today.isoformat())
    resp = query.limit(1).execute()
    return resp.data[0] if resp.data else None


def _fetch_trajectory(deal_uuid):
    cols = ", ".join(_TRAJ_FETCH_COLS)
    resp = (
        supabase.table(_TBL_SNAPSHOTS)
        .select(cols)
        .eq(_S_DEAL_ID, deal_uuid)
        .order(_S_DATE)
        .execute()
    )
    return resp.data or []


def _fetch_similar_deals(stage, amount, age, team):
    won = _query_trajectories("won", stage, amount, age, team, _F["max_similar_won"])
    lost = _query_trajectories("lost", stage, amount, age, team, _F["max_similar_lost"])
    return won, lost


def _query_trajectories(outcome, stage, amount, age, team, limit):
    select_cols = ", ".join([
        _TC["outcome"], _TC["amount"], _TC["deal_age_days"], _TC["pae"],
        _TC["team"], _TC["closed_lost_reason"], _TC["trajectory"],
        _TC["lessons"], _TC["close_date"],
    ])
    query = (
        supabase.table(_TBL_TRAJECTORIES)
        .select(select_cols)
        .eq(_TC["outcome"], outcome)
    )
    if team:
        query = query.eq(_TC["team"], team)

    resp = query.order(_SYS["created_at"], desc=True).limit(200).execute()
    candidates = resp.data or []
    if not candidates:
        return []

    def _score(c):
        s = 0.0
        c_amount = float(c.get(_TC["amount"]) or 0)
        c_age = c.get(_TC["deal_age_days"]) or 0
        if amount and c_amount:
            ratio = min(amount, c_amount) / max(amount, c_amount) if max(amount, c_amount) > 0 else 0
            s += ratio * 3
        if age and c_age:
            ratio = min(age, c_age) / max(age, c_age) if max(age, c_age) > 0 else 0
            s += ratio * 2
        traj = c.get(_TC["trajectory"])
        if isinstance(traj, str):
            try:
                traj = json.loads(traj)
            except (json.JSONDecodeError, TypeError):
                traj = []
        if traj and stage:
            last_stage = (traj[-1] if traj else {}).get("stage", "")
            if last_stage == stage:
                s += 2
        return s

    scored = sorted(candidates, key=_score, reverse=True)[:limit]

    results = []
    for c in scored:
        traj = c.get(_TC["trajectory"])
        if isinstance(traj, str):
            try:
                traj = json.loads(traj)
            except (json.JSONDecodeError, TypeError):
                traj = []
        lessons = c.get(_TC["lessons"])
        if isinstance(lessons, str):
            try:
                lessons = json.loads(lessons)
            except (json.JSONDecodeError, TypeError):
                lessons = []

        traj_lines = []
        for t in (traj or [])[-8:]:
            prob = t.get("probability", "?")
            days = t.get("days_before_close", "?")
            signals = (t.get("signals") or "")[:60]
            blockers = (t.get("blockers") or "")[:60]
            t_stage = t.get("stage", "?")
            traj_lines.append(
                f"  {t.get('date', '?')} ({days}d before close) [{t_stage}]: "
                f"{prob}% | {signals} | {blockers}"
            )

        results.append({
            _TC["outcome"]: c[_TC["outcome"]],
            _TC["amount"]: c.get(_TC["amount"]),
            _TC["deal_age_days"]: c.get(_TC["deal_age_days"]),
            _TC["pae"]: c.get(_TC["pae"]),
            _TC["close_date"]: c.get(_TC["close_date"]),
            _TC["closed_lost_reason"]: c.get(_TC["closed_lost_reason"]),
            "trajectory_summary": "\n".join(traj_lines) if traj_lines else "No trajectory data.",
            _TC["lessons"]: (lessons or [])[:3],
        })

    return results


def _fetch_patterns(team):
    patterns = []
    if team:
        resp = (
            supabase.table(_TBL_PATTERNS)
            .select(_P_PATTERN)
            .eq(_P_SCOPE, team)
            .order(_P_CONFIDENCE, desc=True)
            .order(_P_GENERATED_AT, desc=True)
            .limit(_F["max_patterns_team"])
            .execute()
        )
        patterns.extend(p[_P_PATTERN] for p in (resp.data or []) if p.get(_P_PATTERN))

    resp = (
        supabase.table(_TBL_PATTERNS)
        .select(_P_PATTERN)
        .eq(_P_SCOPE, "global")
        .order(_P_CONFIDENCE, desc=True)
        .order(_P_GENERATED_AT, desc=True)
        .limit(_F["max_patterns_global"])
        .execute()
    )
    patterns.extend(p[_P_PATTERN] for p in (resp.data or []) if p.get(_P_PATTERN))

    return patterns


def _fetch_calibration(today):
    prev_month = (today.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    cal_select = ", ".join([
        _CAL_DEAL_NAME, _CAL_PREDICTED_DATE, _CAL_ACTUAL,
        _CAL_DAYS_OFF, _CAL_ERROR_TYPE, _CAL_ERROR_ANALYSIS,
    ])
    resp = (
        supabase.table(_TBL_CALIBRATION)
        .select(cal_select)
        .eq(_CAL_MONTH, prev_month)
        .limit(_F["max_calibration"])
        .execute()
    )
    return resp.data or []


# ═══════════════════════════════════════════════════════════════════════════
# PROMPT BUILDER
# ═══════════════════════════════════════════════════════════════════════════

def _read_prompt(rel_path):
    return (PROMPTS_DIR / rel_path).read_text(encoding="utf-8").strip()


def _days_left_in_month(today):
    next_month = today.replace(day=28) + timedelta(days=4)
    last_day = next_month - timedelta(days=next_month.day)
    return (last_day - today).days


def _build_user_prompt(deal, snapshot, trajectory, similar_won, similar_lost,
                       patterns, calibration, prev_forecast, today):
    lines = []

    deal_name = deal.get(_D_NAME) or "?"
    deal_stage = deal.get(_D_STAGE) or "?"
    amount = deal.get(_D_MRR) or 0
    age = deal.get(_D_AGE) or 0
    pae = deal.get(_D_PAE) or deal.get(_D_PBD) or "?"
    close_date_rep = deal.get(_D_CLOSE) or "?"
    last_contacted = deal.get(_D_LAST_CONTACT) or "?"

    weekday = today.strftime("%A")
    lines.append("## DEAL TO FORECAST")
    lines.append(f"Name: {deal_name}")
    lines.append(f"Stage: {deal_stage} | Amount: €{amount} | Age: {age} days | PAE: {pae}")
    lines.append(f"PAE close_date: {close_date_rep}")
    lines.append(f"Last contacted: {last_contacted}")
    lines.append(f"Today: {weekday} {today.strftime('%d/%m/%Y')} ({today.isoformat()})")
    lines.append(f"Current month: {today.strftime('%Y-%m')}")
    lines.append(f"Days left in month: {_days_left_in_month(today)}")
    lines.append("")

    if prev_forecast and prev_forecast.get(_FC_CLOSE_DATE):
        snap_date = prev_forecast.get(_S_DATE, "?")
        lines.append(f"## YOUR PREVIOUS FORECAST ({snap_date})")
        lines.append(f"estimated_close_date: {prev_forecast.get(_FC_CLOSE_DATE, '?')} "
                      f"({prev_forecast.get(_FC_CONFIDENCE, '?')})")
        lines.append(f"push_action: {prev_forecast.get(_FC_PUSH_ACTION) or 'none'}")
        lines.append(f"momentum: {prev_forecast.get(_FC_MOMENTUM) or '?'}")
        lines.append(f"reasoning: {(prev_forecast.get(_FC_REASONING) or '')[:300]}")
        lines.append("→ Only change your prediction if there's a MATERIAL change since then.")
    else:
        lines.append("## YOUR PREVIOUS FORECAST")
        lines.append("First time forecasting this deal.")
    lines.append("")

    score_keys = [f"{d}_score" for d in _MEDDIC_DIMS]
    scores = " | ".join(f"{k}={snapshot.get(k, '?')}" for k in score_keys)
    lines.append("## CURRENT SNAPSHOT")
    lines.append(f"MEDDIC: {scores}")
    lines.append(f"Probability v1: {snapshot.get(_FC_PROB, '?')}%")
    lines.append(f"Assessment: {(snapshot.get(_SC_ASSESSMENT) or '')[:300]}")
    lines.append(f"Signals: {(snapshot.get(_SC_SIGNALS) or '')[:200]}")
    lines.append(f"Blockers: {(snapshot.get(_SC_BLOCKERS) or '')[:200]}")
    lines.append(f"Next step: {(snapshot.get(_SC_NEXT_STEP) or '')[:200]}")
    lines.append("")

    max_traj = _F["max_trajectory_snapshots"]
    lines.append(f"## TRAJECTORY (last {max_traj} snapshots)")
    traj_lines = []
    for s in trajectory[-max_traj:]:
        prob = s.get(_FC_PROB, "?")
        stg = s.get(_S_STAGE, "")
        signals = (s.get(_SC_SIGNALS) or "")[:80]
        blockers = (s.get(_SC_BLOCKERS) or "")[:80]
        stage_tag = f" [{stg}]" if stg else ""
        traj_lines.append(
            f"  {s.get(_S_DATE, '?')}{stage_tag}: prob={prob}% | "
            f"signals: {signals} | blockers: {blockers}"
        )
    lines.append("\n".join(traj_lines) if traj_lines else "No previous snapshots.")
    lines.append("")

    max_ctx = _F["max_deal_context_chars"]
    deal_context = (deal.get(_D_CONTEXT) or "")[-max_ctx:]
    lines.append(f"## RECENT INTERACTIONS (last {max_ctx // 1000}K chars)")
    lines.append(deal_context if deal_context else "No interactions recorded.")
    lines.append("")

    lines.append("## SIMILAR DEALS THAT WON")
    if similar_won:
        for s in similar_won:
            lines.append(
                f"DEAL WON: €{s[_TC['amount']] or '?'} | {s[_TC['deal_age_days']] or '?'}d "
                f"| PAE: {s[_TC['pae']] or '?'} | Closed: {s.get(_TC['close_date']) or '?'}\n"
                f"Trajectory:\n{s['trajectory_summary']}\n"
                f"Lessons: {'; '.join(s[_TC['lessons']][:3]) if s[_TC['lessons']] else 'None'}\n"
            )
    else:
        lines.append("No similar won deals in benchmark yet.")
    lines.append("")

    lines.append("## SIMILAR DEALS THAT LOST")
    if similar_lost:
        for s in similar_lost:
            lines.append(
                f"DEAL LOST ({s[_TC['closed_lost_reason']] or '?'}): "
                f"€{s[_TC['amount']] or '?'} | {s[_TC['deal_age_days']] or '?'}d "
                f"| PAE: {s[_TC['pae']] or '?'}\n"
                f"Trajectory:\n{s['trajectory_summary']}\n"
                f"Lessons: {'; '.join(s[_TC['lessons']][:3]) if s[_TC['lessons']] else 'None'}\n"
            )
    else:
        lines.append("No similar lost deals in benchmark yet.")
    lines.append("")

    lines.append("## LEARNED PATTERNS")
    if patterns:
        for p in patterns:
            lines.append(f"• {p}")
    else:
        lines.append("No learned patterns yet (first month).")
    lines.append("")

    lines.append("## CALIBRATION (last month errors)")
    if calibration:
        for c in calibration:
            pred_date = c.get(_CAL_PREDICTED_DATE) or "?"
            days_off = c.get(_CAL_DAYS_OFF)
            err_type = c.get(_CAL_ERROR_TYPE) or "?"
            lines.append(
                f"• {c[_CAL_DEAL_NAME]}: predicted={pred_date}, "
                f"actual={c[_CAL_ACTUAL]}, type={err_type}, "
                f"days_off={days_off}, lesson: {c.get(_CAL_ERROR_ANALYSIS) or '?'}"
            )
    else:
        lines.append("No calibration data yet (first month).")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# PROBABILITY FORMULA
# ═══════════════════════════════════════════════════════════════════════════

def _get_activity_decay(deal, today):
    last = deal.get(_D_LAST_CONTACT)
    if not last:
        return _F["activity_decay"][999]
    try:
        last_date = date.fromisoformat(last[:10]) if isinstance(last, str) else last
        days = (today - last_date).days
    except (ValueError, TypeError, AttributeError):
        return _F["activity_decay"][999]

    for threshold in sorted(_F["activity_decay"].keys()):
        if days <= threshold:
            return _F["activity_decay"][threshold]
    return _F["activity_decay"][999]


def _get_momentum_multiplier(momentum):
    return _F["momentum_multiplier"].get(momentum, 1.0)


def _compute_probability(snapshot, claude_out, deal, today):
    if claude_out.get("deal_killer"):
        val = claude_out.get("deal_killer_value")
        try:
            return max(0, min(5, int(float(val))))
        except (TypeError, ValueError):
            return 3

    weights = _F["meddic_weights"]
    _DIM_TO_WEIGHT = {"m": "M", "e": "E", "dc": "DC", "dp": "DP", "i": "I", "c": "C", "comp": "Comp"}
    try:
        scores = {
            _DIM_TO_WEIGHT[d]: float(snapshot.get(f"{d}_score", 0) or 0)
            for d in _MEDDIC_DIMS
        }
    except (TypeError, ValueError):
        return 0

    bs = float(claude_out.get("bs") or 0)
    lb = float(claude_out.get("lb") or 0)

    base = sum(scores[k] * weights[k] for k in weights)
    adjusted = max(0.0, min(10.0, base + bs + lb))
    percentage = adjusted * 10

    activity_mult = _get_activity_decay(deal, today)
    momentum = claude_out.get("deal_momentum", "stable")
    momentum_mult = _get_momentum_multiplier(momentum)

    final = percentage * activity_mult * momentum_mult
    return max(0, min(100, round(final)))


# ═══════════════════════════════════════════════════════════════════════════
# WRITER
# ═══════════════════════════════════════════════════════════════════════════

def _update_snapshot(snapshot_id, forecast_data):
    try:
        row = {}
        for col in _CLAUDE_COLS:
            val = forecast_data.get(col)
            if val is not None:
                row[col] = val
        for col in _COMPUTED_COLS:
            val = forecast_data.get(col)
            if val is not None:
                row[col] = val

        row = {k: v for k, v in row.items() if v is not None}
        supabase.table(_TBL_SNAPSHOTS).update(row).eq(_SYS["id"], snapshot_id).execute()
        return True
    except Exception as e:
        print(f"    ✗ Forecast write failed: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def run(deal_uuid, use_latest=False):
    """
    Run forecast for a deal.

    use_latest=False  after intelligence2 (today's fresh snapshot)
    use_latest=True   refresh flow (latest existing snapshot)
    """
    today = date.today()

    deal = _fetch_deal(deal_uuid)
    if not deal:
        print("    FORECAST: deal not found")
        return None

    deal_name = deal.get(_D_NAME) or "?"
    hs_deal_id = deal.get(_D_ID) or ""
    amount = float(deal.get(_D_MRR) or 0)
    stage = deal.get(_D_STAGE) or ""
    age = deal.get(_D_AGE) or 0
    team = deal.get(_D_TEAM) or ""

    label = "FORECAST REFRESH" if use_latest else "FORECAST"
    snapshot = _fetch_snapshot(hs_deal_id, today, use_latest=use_latest)
    if not snapshot:
        print(f"    {label}: no snapshot for {deal_name} — skipping")
        return None

    snapshot_id = snapshot.get(_SYS["id"])
    print(f"    {label}: {deal_name}")

    owner_email = deal.get(_D_PAE) or deal.get(_D_PBD)
    trajectory = _fetch_trajectory(deal_uuid)
    similar_won, similar_lost = _fetch_similar_deals(stage, amount, age, team)
    patterns = _fetch_patterns(team)
    calibration = _fetch_calibration(today)

    prev_forecast = None
    for s in reversed(trajectory):
        if s.get(_FC_CLOSE_DATE):
            prev_forecast = s
            break

    system_prompt = _read_prompt(_F["prompt"])
    lang_text = get_lang_prompt(team, owner_email=owner_email)
    if lang_text:
        system_prompt += "\n\n" + lang_text

    user_prompt = _build_user_prompt(
        deal, snapshot, trajectory,
        similar_won, similar_lost,
        patterns, calibration,
        prev_forecast, today,
    )

    print(f"    Claude Opus ({len(user_prompt)} chars)...")
    try:
        raw = claude.analyze(
            system_prompt, user_prompt,
            model=MODEL_OPUS, max_tokens=MAX_TOKENS["forecast_v2"],
        )
    except Exception as e:
        print(f"    ✗ Claude failed: {e}")
        return None

    text = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    text = re.sub(r"\s*```$", "", text).strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        matches = re.findall(r"\{[^{}]+\}", text)
        if not matches:
            print("    ✗ No JSON found in forecast response")
            return None
        try:
            parsed = json.loads(matches[-1])
        except json.JSONDecodeError:
            print("    ✗ Fallback JSON parse failed")
            return None

    if "estimated_close_date" in parsed and "claudio_close_date" not in parsed:
        parsed["claudio_close_date"] = parsed["estimated_close_date"]

    close_probability = _compute_probability(snapshot, parsed, deal, today)
    mrr = float(snapshot.get(_S_MRR) or 0)
    claudio_forecast = round((close_probability / 100) * mrr, 2)

    forecast_data = {}
    for col in _CLAUDE_COLS:
        if col in parsed:
            forecast_data[col] = parsed[col]
    forecast_data[_FC_PROB] = close_probability
    forecast_data[_FC_FORECAST] = claudio_forecast

    ok = _update_snapshot(snapshot_id, forecast_data)

    conf = parsed.get("forecast_confidence", "?")
    mom = parsed.get("deal_momentum", "?")
    push = " | PUSHABLE" if parsed.get("forecast_pushable") else ""
    close_dt = parsed.get("estimated_close_date", "?")
    print(f"    → ({conf}) | prob={close_probability}% | momentum={mom}{push} | close: {close_dt}")

    return {
        "close_probability": close_probability,
        "claudio_forecast": claudio_forecast,
        "forecast_confidence": conf,
        "deal_momentum": mom,
        "estimated_close_date": parsed.get("estimated_close_date"),
        "ok": ok,
    }
