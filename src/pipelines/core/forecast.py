"""
Core Forecast — Phase 4 of the CORE pipeline.

Entry point: run(deal_uuid)

Runs AFTER intelligence.py has created a fresh snapshot. Reads the snapshot,
deal trajectory, similar deals benchmark, learned patterns, and calibration
errors — makes 1 Opus call — computes close_probability — updates the snapshot.

Everything from FORECAST_CONFIG + shared columns from INTELLIGENCE_CONFIG.
"""

import json
import re
from datetime import date, timedelta

from src.config import (
    FORECAST_CONFIG,
    INTELLIGENCE_CONFIG,
    PROMPTS_DIR,
    MODEL_OPUS,
    MAX_TOKENS_FORECAST_V2,
)
from src.db.client import supabase
from src.integrations import claude

_F = FORECAST_CONFIG
_I = INTELLIGENCE_CONFIG
TODAY = date.today()


# ═══════════════════════════════════════════════════════════════════════════
# FETCHERS
# ═══════════════════════════════════════════════════════════════════════════

def _fetch_deal(deal_uuid: str) -> dict | None:
    resp = (
        supabase.table(_I["deals_table"])
        .select("*")
        .eq(_I["deal_col_id"], deal_uuid)
        .limit(1)
        .execute()
    )
    return resp.data[0] if resp.data else None


def _fetch_snapshot_today(hs_deal_id: str) -> dict | None:
    resp = (
        supabase.table(_I["snapshot_table"])
        .select("*")
        .eq(_I["fk_hs_deal_id"], hs_deal_id)
        .eq(_I["fk_snapshot_date"], TODAY.isoformat())
        .limit(1)
        .execute()
    )
    return resp.data[0] if resp.data else None


def _fetch_trajectory(deal_uuid: str) -> list[dict]:
    resp = (
        supabase.table(_I["snapshot_table"])
        .select(
            f"{_I['fk_snapshot_date']}, close_probability, "
            + ", ".join(c for c in _F["snapshot_input_cols"] if c in (
                "m_score", "e_score", "dc_score", "dp_score", "i_score", "c_score",
                "buyer_signals", "live_blockers", "next_step", "deal_assessment",
                "closes_this_month", "forecast_confidence", "forecast_reasoning",
                "push_action", "deal_momentum",
            ))
        )
        .eq(_I["fk_deal_id"], deal_uuid)
        .order(_I["fk_snapshot_date"])
        .execute()
    )
    return resp.data or []


def _fetch_similar_deals(deal_stage: str, amount: float, age: int, team: str) -> tuple[list[dict], list[dict]]:
    """Find similar won and lost deals from trajectories."""
    won = _query_trajectories("won", amount, age, team, _F["max_similar_won"])
    lost = _query_trajectories("lost", amount, age, team, _F["max_similar_lost"])
    return won, lost


def _query_trajectories(outcome: str, amount: float, age: int, team: str, limit: int) -> list[dict]:
    query = (
        supabase.table(_F["trajectories_table"])
        .select("outcome, amount, deal_age_days, pae, team, closed_lost_reason, trajectory, lessons")
        .eq("outcome", outcome)
    )
    if team:
        query = query.eq("team", team)

    resp = query.order("created_at", desc=True).limit(200).execute()
    candidates = resp.data or []
    if not candidates:
        return []

    def _score(c: dict) -> float:
        s = 0.0
        c_amount = float(c.get("amount") or 0)
        c_age = c.get("deal_age_days") or 0
        if amount and c_amount:
            ratio = min(amount, c_amount) / max(amount, c_amount) if max(amount, c_amount) > 0 else 0
            s += ratio * 3
        if age and c_age:
            ratio = min(age, c_age) / max(age, c_age) if max(age, c_age) > 0 else 0
            s += ratio * 2
        return s

    scored = sorted(candidates, key=_score, reverse=True)[:limit]

    results = []
    for c in scored:
        traj = c.get("trajectory")
        if isinstance(traj, str):
            try:
                traj = json.loads(traj)
            except (json.JSONDecodeError, TypeError):
                traj = []
        lessons = c.get("lessons")
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
            traj_lines.append(f"  {t.get('date', '?')} ({days}d before close): {prob}% | {signals} | {blockers}")

        results.append({
            "outcome": c["outcome"],
            "amount": c.get("amount"),
            "deal_age_days": c.get("deal_age_days"),
            "pae": c.get("pae"),
            "closed_lost_reason": c.get("closed_lost_reason"),
            "trajectory_summary": "\n".join(traj_lines) if traj_lines else "No trajectory data.",
            "lessons": (lessons or [])[:3],
        })

    return results


def _fetch_patterns() -> list[str]:
    resp = (
        supabase.table(_F["patterns_table"])
        .select("pattern")
        .order("generated_at", desc=True)
        .limit(_F["max_patterns"])
        .execute()
    )
    return [p["pattern"] for p in (resp.data or []) if p.get("pattern")]


def _fetch_calibration() -> list[dict]:
    prev_month = (TODAY.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    resp = (
        supabase.table(_F["calibration_table"])
        .select("deal_name, predicted_close_this_month, actual_outcome, error_analysis")
        .eq("month", prev_month)
        .limit(_F["max_calibration_entries"])
        .execute()
    )
    return resp.data or []


# ═══════════════════════════════════════════════════════════════════════════
# PROMPT BUILDER
# ═══════════════════════════════════════════════════════════════════════════

def _read_prompt(path: str) -> str:
    return (PROMPTS_DIR / path).read_text(encoding="utf-8").strip()


def _build_user_prompt(
    deal: dict,
    snapshot: dict,
    trajectory: list[dict],
    similar_won: list[dict],
    similar_lost: list[dict],
    patterns: list[str],
    calibration: list[dict],
    prev_forecast: dict | None,
) -> str:
    dc = _I
    lines = []

    deal_name = deal.get(dc["deal_col_deal_name"]) or "?"
    deal_stage = deal.get(dc["deal_col_stage"]) or "?"
    amount = deal.get(dc["deal_col_amount"]) or 0
    age = deal.get(dc["deal_col_age"]) or 0
    pae = deal.get(dc["deal_col_pae"]) or deal.get(dc["deal_col_pbd"]) or "?"
    close_date_rep = deal.get(dc["deal_col_close_date"]) or "?"

    lines.append("## DEAL TO FORECAST")
    lines.append(f"Name: {deal_name}")
    lines.append(f"Stage: {deal_stage} | Amount: €{amount} | Age: {age} days | PAE: {pae}")
    lines.append(f"PAE close_date: {close_date_rep}")
    lines.append(f"Today: {TODAY.isoformat()}")
    lines.append(f"Current month: {TODAY.strftime('%Y-%m')}")
    lines.append(f"Days left in month: {_days_left_in_month()}")
    lines.append("")

    # Previous forecast (continuity)
    if prev_forecast and prev_forecast.get("closes_this_month") is not None:
        ctm = "YES" if prev_forecast["closes_this_month"] else "NO"
        lines.append(f"## YOUR PREVIOUS FORECAST ({prev_forecast.get(_I['fk_snapshot_date'], '?')})")
        lines.append(f"closes_this_month: {ctm} ({prev_forecast.get('forecast_confidence', '?')})")
        lines.append(f"push_action: {prev_forecast.get('push_action') or 'none'}")
        lines.append(f"momentum: {prev_forecast.get('deal_momentum') or '?'}")
        lines.append(f"reasoning: {(prev_forecast.get('forecast_reasoning') or '')[:300]}")
        lines.append("→ Only change your prediction if there's a MATERIAL change since then.")
    else:
        lines.append("## YOUR PREVIOUS FORECAST")
        lines.append("First time forecasting this deal.")
    lines.append("")

    # Current snapshot
    scores = " | ".join(
        f"{k}={snapshot.get(k.lower().replace('_score', '_score'), '?')}"
        for k in ["M_score", "E_score", "DC_score", "DP_score", "I_score", "C_score", "Comp_score"]
    )
    lines.append("## CURRENT SNAPSHOT")
    lines.append(f"MEDDIC: {scores}")
    lines.append(f"Probability v1: {snapshot.get('close_probability', '?')}%")
    lines.append(f"Assessment: {(snapshot.get('deal_assessment') or '')[:300]}")
    lines.append(f"Signals: {(snapshot.get('buyer_signals') or '')[:200]}")
    lines.append(f"Blockers: {(snapshot.get('live_blockers') or '')[:200]}")
    lines.append(f"Next step: {(snapshot.get('next_step') or '')[:200]}")
    lines.append("")

    # Trajectory
    lines.append(f"## TRAJECTORY (last {_F['max_trajectory_snapshots']} snapshots)")
    traj_lines = []
    for s in trajectory[-_F["max_trajectory_snapshots"]:]:
        prob = s.get("close_probability", "?")
        signals = (s.get("buyer_signals") or "")[:80]
        blockers = (s.get("live_blockers") or "")[:80]
        traj_lines.append(f"  {s.get(_I['fk_snapshot_date'], '?')}: prob={prob}% | signals: {signals} | blockers: {blockers}")
    lines.append("\n".join(traj_lines) if traj_lines else "No previous snapshots.")
    lines.append("")

    # Recent deal context
    deal_context = (deal.get(dc.get("deal_context_col", "deal_context")) or "")[-_F["max_deal_context_chars"]:]
    lines.append("## RECENT INTERACTIONS (last 5K chars)")
    lines.append(deal_context if deal_context else "No interactions recorded.")
    lines.append("")

    # Similar deals
    lines.append("## SIMILAR DEALS THAT WON")
    if similar_won:
        for s in similar_won:
            lines.append(
                f"DEAL WON: €{s['amount'] or '?'} | {s['deal_age_days'] or '?'}d | PAE: {s['pae'] or '?'}\n"
                f"Trajectory:\n{s['trajectory_summary']}\n"
                f"Lessons: {'; '.join(s['lessons'][:3]) if s['lessons'] else 'None'}\n"
            )
    else:
        lines.append("No similar won deals in benchmark yet.")
    lines.append("")

    lines.append("## SIMILAR DEALS THAT LOST")
    if similar_lost:
        for s in similar_lost:
            lines.append(
                f"DEAL LOST ({s['closed_lost_reason'] or '?'}): €{s['amount'] or '?'} | {s['deal_age_days'] or '?'}d | PAE: {s['pae'] or '?'}\n"
                f"Trajectory:\n{s['trajectory_summary']}\n"
                f"Lessons: {'; '.join(s['lessons'][:3]) if s['lessons'] else 'None'}\n"
            )
    else:
        lines.append("No similar lost deals in benchmark yet.")
    lines.append("")

    # Patterns
    lines.append("## LEARNED PATTERNS")
    if patterns:
        for p in patterns:
            lines.append(f"• {p}")
    else:
        lines.append("No learned patterns yet (first month).")
    lines.append("")

    # Calibration
    lines.append("## CALIBRATION (last month errors)")
    if calibration:
        for c in calibration:
            pred = "close" if c.get("predicted_close_this_month") else "no close"
            lines.append(f"• {c['deal_name']}: predicted={pred}, actual={c['actual_outcome']}, lesson: {c['error_analysis']}")
    else:
        lines.append("No calibration data yet (first month).")

    return "\n".join(lines)


def _days_left_in_month() -> int:
    next_month = TODAY.replace(day=28) + timedelta(days=4)
    last_day = next_month - timedelta(days=next_month.day)
    return (last_day - TODAY).days


# ═══════════════════════════════════════════════════════════════════════════
# PROBABILITY FORMULA
# ═══════════════════════════════════════════════════════════════════════════

def _compute_probability(snapshot: dict, claude_out: dict) -> int:
    if claude_out.get("deal_killer"):
        val = claude_out.get("deal_killer_value")
        return int(val) if val is not None else 3

    weights = _F["meddic_weights"]
    try:
        scores = {
            "C": float(snapshot.get("c_score", 0) or 0),
            "E": float(snapshot.get("e_score", 0) or 0),
            "DP": float(snapshot.get("dp_score", 0) or 0),
            "DC": float(snapshot.get("dc_score", 0) or 0),
            "I": float(snapshot.get("i_score", 0) or 0),
            "M": float(snapshot.get("m_score", 0) or 0),
            "Comp": float(snapshot.get("comp_score", 0) or 0),
        }
    except (TypeError, ValueError):
        return 0

    bs = float(claude_out.get("bs") or 0)
    lb = float(claude_out.get("lb") or 0)

    base = sum(scores[k] * weights[k] for k in weights)
    adjusted = max(0.0, min(10.0, base + bs + lb))
    return round(adjusted * 10)


# ═══════════════════════════════════════════════════════════════════════════
# WRITER
# ═══════════════════════════════════════════════════════════════════════════

def _update_snapshot(snapshot_id: str, forecast_data: dict) -> bool:
    try:
        row = {}
        for col in _F["claude_cols"]:
            val = forecast_data.get(col)
            if val is not None:
                row[col] = val
        for col in _F["computed_cols"]:
            val = forecast_data.get(col)
            if val is not None:
                row[col] = val

        row = {k: v for k, v in row.items() if v is not None}
        supabase.table(_I["snapshot_table"]).update(row).eq("id", snapshot_id).execute()
        return True
    except Exception as e:
        print(f"    ✗ Forecast write failed: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def run(deal_uuid: str) -> dict | None:
    """Run forecast for a deal. Requires a fresh snapshot from intelligence.py."""

    deal = _fetch_deal(deal_uuid)
    if not deal:
        print(f"    FORECAST: deal not found")
        return None

    deal_name = deal.get(_I["deal_col_deal_name"]) or "?"
    hs_deal_id = deal.get(_I["deal_col_deal_id"]) or ""
    amount = float(deal.get(_I["deal_col_amount"]) or 0)
    stage = deal.get(_I["deal_col_stage"]) or ""
    age = deal.get(_I["deal_col_age"]) or 0
    team = deal.get(_I["deal_col_team"]) or ""

    snapshot = _fetch_snapshot_today(hs_deal_id)
    if not snapshot:
        print(f"    FORECAST: no snapshot today for {deal_name} — skipping")
        return None

    snapshot_id = snapshot.get("id")
    print(f"    FORECAST: {deal_name}")

    trajectory = _fetch_trajectory(deal_uuid)
    similar_won, similar_lost = _fetch_similar_deals(stage, amount, age, team)
    patterns = _fetch_patterns()
    calibration = _fetch_calibration()

    prev_forecast = None
    for s in reversed(trajectory):
        if s.get("closes_this_month") is not None:
            prev_forecast = s
            break

    system_prompt = _read_prompt(_F["system_prompt_path"])
    user_prompt = _build_user_prompt(
        deal, snapshot, trajectory,
        similar_won, similar_lost,
        patterns, calibration,
        prev_forecast,
    )

    print(f"    Claude Opus ({len(user_prompt)} chars)...")
    try:
        raw = claude.analyze(system_prompt, user_prompt, model=MODEL_OPUS, max_tokens=MAX_TOKENS_FORECAST_V2)
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
            print(f"    ✗ No JSON found in forecast response")
            return None
        parsed = json.loads(matches[-1])

    close_probability = _compute_probability(snapshot, parsed)
    mrr = float(snapshot.get("mrr") or 0)
    claudio_forecast = round((close_probability / 100) * mrr, 2)

    forecast_data = {}
    for col in _F["claude_cols"]:
        if col in parsed:
            forecast_data[col] = parsed[col]
    forecast_data["close_probability"] = close_probability
    forecast_data["claudio_forecast"] = claudio_forecast

    ok = _update_snapshot(snapshot_id, forecast_data)

    ctm = "YES" if parsed.get("closes_this_month") else "NO"
    conf = parsed.get("forecast_confidence", "?")
    mom = parsed.get("deal_momentum", "?")
    push = " | PUSHABLE" if parsed.get("forecast_pushable") else ""
    print(f"    → {ctm} ({conf}) | prob={close_probability}% | momentum={mom}{push} | close: {parsed.get('estimated_close_date', '?')}")

    return {
        "close_probability": close_probability,
        "claudio_forecast": claudio_forecast,
        "closes_this_month": parsed.get("closes_this_month"),
        "forecast_confidence": conf,
        "deal_momentum": mom,
        "estimated_close_date": parsed.get("estimated_close_date"),
        "ok": ok,
    }
