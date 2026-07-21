"""
Weekly Rep Stats — per-person performance patterns.

Runs inside weekly/run2.py after patterns. Pure Python (segments A-F, H).
Segment G (post-mortem) uses Claude and runs quarterly only.

Each stat becomes a learned_pattern with:
  - pattern_key: rep_{stat}_{email_slug}
  - scope: "rep:{email}"
  - history JSONB accumulates weekly executions

Data sources:
  A. Closing Effectiveness  ← deal_trajectories (pae, pbd)
  B. Pipeline Health         ← deals + front_deal_snapshots (pae, pbd)
  C. Process Quality         ← pae_audits / pbd_audits (owner_name)
  D. Coaching & Gaps         ← pae_audits / pbd_audits (owner_name)
  E. Activity & Cadence      ← calls + deals (owner_email, pae, pbd)
  F. Forecast Accuracy       ← calibration_log + snapshots (via deal FK)
  G. Post-mortem Patterns    ← deal_analysis (via deal FK) — Claude, quarterly
  H. Product Knowledge       ← deal_product_signals (via deal FK)
"""

import json
import traceback
from datetime import date
from collections import defaultdict

from src import schema
from src.db.client import supabase


# ═══════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════

_TBL_TRAJECTORIES = schema.tbl("trajectories")
_TBL_DEALS        = schema.tbl("deals")
_TBL_PAE_AUDITS   = schema.tbl("pae_audits")
_TBL_PBD_AUDITS   = schema.tbl("pbd_audits")
_TBL_CALLS        = schema.tbl("calls")
_TBL_SNAPSHOTS    = schema.tbl("snapshots")
_TBL_CALIBRATION  = schema.tbl("calibration")
_TBL_PROD_SIGNALS = schema.tbl("product_signals")
_TBL_PATTERNS     = schema.tbl("patterns")

_TC = schema.TRAJECTORY_COLS


def _email_slug(email: str) -> str:
    """maria.garcia@factorial.co -> maria_garcia_factorial_co"""
    return email.replace("@", "_").replace(".", "_")


def _parse_json(val):
    if isinstance(val, str):
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return val
    return val


# ═══════════════════════════════════════════════════════════════════════════
# DATA LOADING (one query per table, cached)
# ═══════════════════════════════════════════════════════════════════════════

def _fetch_all_paginated(table: str, select: str, order_col: str = "created_at") -> list[dict]:
    results = []
    offset = 0
    while True:
        resp = (
            supabase.table(table)
            .select(select)
            .order(order_col, desc=True)
            .range(offset, offset + 999)
            .execute()
        )
        batch = resp.data or []
        results.extend(batch)
        if len(batch) < 1000:
            break
        offset += 1000
    return results


def _load_data() -> dict:
    """Load all required tables once. Returns dict keyed by source name."""
    print("    Loading data for rep stats...")

    data = {}

    # A: trajectories (has pae, pbd, outcome, trajectory, stage_dates, etc.)
    data["trajectories"] = _fetch_all_paginated(
        _TBL_TRAJECTORIES,
        ", ".join([
            _TC["deal_id"], _TC["outcome"], _TC["amount"], _TC["deal_age_days"],
            _TC["pae"], _TC["pbd"], _TC["team"], _TC["pipeline_name"],
            _TC["closed_lost_reason"], _TC["close_date"],
            _TC["trajectory"], _TC["stage_dates"], _TC["interactions"],
        ]),
    )
    print(f"      trajectories: {len(data['trajectories'])}")

    # C/D: audits
    audit_select = "owner_name, win_rate_score, lead_temperature, discovery_level, biggest_gap, improvement_items_json, red_flags_fired, rep_strengths, created_at"
    data["pae_audits"] = _fetch_all_paginated(_TBL_PAE_AUDITS, audit_select + ", m_score, e_score, dc_score, dp_score, i_score, c_score, comp_score")
    data["pbd_audits"] = _fetch_all_paginated(_TBL_PBD_AUDITS, audit_select + ", budget, authority, need, timing")
    print(f"      pae_audits: {len(data['pae_audits'])}, pbd_audits: {len(data['pbd_audits'])}")

    # E: calls
    data["calls"] = _fetch_all_paginated(
        _TBL_CALLS,
        "call_id, deal_id, owner_email, fecha, duracion_segundos, team",
    )
    print(f"      calls: {len(data['calls'])}")

    return data


# ═══════════════════════════════════════════════════════════════════════════
# UPSERT (reuses same pattern as patterns2.py)
# ═══════════════════════════════════════════════════════════════════════════

def _upsert_rep_pattern(pattern: dict, today: str):
    key = pattern.get("pattern_key")
    if not key:
        return

    existing_resp = (
        supabase.table(_TBL_PATTERNS)
        .select("id, history, confidence, sample_size, value")
        .eq("pattern_key", key)
        .maybe_single()
        .execute()
    )
    existing = existing_resp.data if existing_resp else None

    history = []
    if existing:
        old_history = _parse_json(existing.get("history") or [])
        if isinstance(old_history, list):
            history = old_history
        history.append({
            "date": today,
            "confidence": existing.get("confidence"),
            "sample_size": existing.get("sample_size"),
            "value": existing.get("value"),
        })

    row = {
        "pattern_key": key,
        "pattern_type": pattern.get("pattern_type", "rep_stat"),
        "scope": pattern.get("scope", "all"),
        "pattern": pattern.get("pattern", ""),
        "confidence": pattern.get("confidence"),
        "sample_size": pattern.get("sample_size"),
        "value": pattern.get("value"),
        "history": json.dumps(history[-52:], ensure_ascii=False),
        "updated_at": "now()",
    }
    row = {k: v for k, v in row.items() if v is not None}

    if existing:
        supabase.table(_TBL_PATTERNS).update(row).eq("id", existing["id"]).execute()
    else:
        row["generated_at"] = "now()"
        supabase.table(_TBL_PATTERNS).insert(row).execute()


# ═══════════════════════════════════════════════════════════════════════════
# SEGMENT A — CLOSING EFFECTIVENESS (~40 stats per rep)
#
# Source: deal_trajectories (pae, pbd columns)
# Key stats:
#   - win_rate, avg_cycle_won, avg_cycle_lost, cycle_waste_ratio
#   - death_stage_distribution (WHERE deals die)
#   - slow_deaths (>5 snapshots, prob never >40%)
#   - loss_reason_concentration (top1 reason >50% = systemic)
#   - high_conf_losses (lost deals where prob was >50% at some point)
#   - comeback_wins (dipped <30% prob, still won)
#   - prob_climb_rate_won (how fast prob rises per snapshot in wins)
#   - avg_calls_to_win vs avg_calls_to_lose
#   - stage_conversion_funnel (per-stage conversion for THIS rep)
# ═══════════════════════════════════════════════════════════════════════════

def _compute_segment_a(trajectories: list[dict]) -> list[dict]:
    """Closing effectiveness — per rep from trajectories."""
    # TODO: implement — deep dive spec in memory project-rep-stats-plan.md
    return []


# ═══════════════════════════════════════════════════════════════════════════
# SEGMENT B — PIPELINE HEALTH (10 stats per rep)
#
# Source: deals + front_deal_snapshots (pae, pbd columns)
# Key stats:
#   - active_deals_count, pipeline_value
#   - stale_deals (no activity > X days)
#   - momentum_distribution (% accelerating/steady/decelerating)
#   - pushable_deals (high MEDDIC, close to close)
#   - stage_distribution (where are THIS rep's deals?)
#   - deals_without_next_meeting
# ═══════════════════════════════════════════════════════════════════════════

def _compute_segment_b(trajectories: list[dict], deals: list[dict] | None = None) -> list[dict]:
    """Pipeline health — per rep from active deals + snapshots."""
    # TODO: implement
    return []


# ═══════════════════════════════════════════════════════════════════════════
# SEGMENT C — PROCESS QUALITY / MEDDIC-BANT (10 stats per rep)
#
# Source: pae_audits (MEDDIC), pbd_audits (BANT)
# Key stats:
#   - avg MEDDIC score per pillar (m,e,dc,dp,i,c,comp)
#   - weakest / strongest pillar
#   - MEDDIC trend (improving or declining over time)
#   - BANT completion rate
#   - discovery_level avg, lead_temperature distribution
#   - win_rate_score avg
# ═══════════════════════════════════════════════════════════════════════════

def _compute_segment_c(pae_audits: list[dict], pbd_audits: list[dict]) -> list[dict]:
    """Process quality — per rep from audit scores."""
    # TODO: implement
    return []


# ═══════════════════════════════════════════════════════════════════════════
# SEGMENT D — COACHING & GAPS (10 stats per rep)
#
# Source: pae_audits / pbd_audits
# Key stats:
#   - top recurring improvement_items
#   - improvement trend (corrects or repeats same issues?)
#   - top strengths
#   - recurring biggest_gaps
#   - red_flags frequency & trend
#   - two_slot_close rate (PBD only)
#   - partner_leverage avg
# ═══════════════════════════════════════════════════════════════════════════

def _compute_segment_d(pae_audits: list[dict], pbd_audits: list[dict]) -> list[dict]:
    """Coaching & gaps — per rep from audit qualitative fields."""
    # TODO: implement
    return []


# ═══════════════════════════════════════════════════════════════════════════
# SEGMENT E — ACTIVITY & CADENCE (10 stats per rep)
#
# Source: calls + deals
# Key stats:
#   - calls_per_week, avg_call_duration
#   - calls/emails/meetings per deal
#   - contact_cadence (avg days between touches)
#   - lead_response_days (createdate -> first call)
#   - days_to_first_meeting
#   - no_show_rate (demo_booked -> to_reschedule transitions)
#   - activity vs result correlation
# ═══════════════════════════════════════════════════════════════════════════

def _compute_segment_e(calls: list[dict], trajectories: list[dict]) -> list[dict]:
    """Activity & cadence — per rep from calls + deals."""
    # TODO: implement
    return []


# ═══════════════════════════════════════════════════════════════════════════
# SEGMENT F — FORECAST ACCURACY (5 stats per rep)
#
# Source: calibration_log + front_deal_snapshots
# Key stats:
#   - forecast_accuracy_pct, avg_days_off
#   - false_positive_rate, false_negative_rate
#   - probability_calibration (predicted vs actual)
# ═══════════════════════════════════════════════════════════════════════════

def _compute_segment_f() -> list[dict]:
    """Forecast accuracy — per rep from calibration data."""
    # TODO: implement
    return []


# ═══════════════════════════════════════════════════════════════════════════
# SEGMENT G — POST-MORTEM PATTERNS (5 stats per rep, QUARTERLY, Claude)
#
# Source: deal_analysis
# Key stats:
#   - what_worked patterns, what_failed patterns
#   - products_missed frequency
#   - rep_assessment summary
#   - key turning points patterns
# ═══════════════════════════════════════════════════════════════════════════

def _compute_segment_g() -> list[dict]:
    """Post-mortem patterns — per rep, quarterly, uses Claude."""
    # TODO: implement (quarterly only, needs Claude)
    return []


# ═══════════════════════════════════════════════════════════════════════════
# SEGMENT H — PRODUCT KNOWLEDGE (4 stats per rep)
#
# Source: deal_product_signals
# Key stats:
#   - products_pitched distribution
#   - missed_vs_pitched ratio
#   - pitch_quality avg
#   - upsell_detection_rate
# ═══════════════════════════════════════════════════════════════════════════

def _compute_segment_h() -> list[dict]:
    """Product knowledge — per rep from product signals."""
    # TODO: implement
    return []


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def run() -> int:
    print("\n  REP STATS: computing per-person patterns...")
    today = date.today().isoformat()

    data = _load_data()
    trajectories = data["trajectories"]

    if len(trajectories) < 10:
        print(f"    Only {len(trajectories)} trajectories — skipping rep stats")
        return 0

    all_patterns = []

    # Segment A — Closing Effectiveness
    print("    [A] Closing Effectiveness...")
    all_patterns.extend(_compute_segment_a(trajectories))

    # Segment B — Pipeline Health
    print("    [B] Pipeline Health...")
    all_patterns.extend(_compute_segment_b(trajectories))

    # Segment C — Process Quality
    print("    [C] Process Quality...")
    all_patterns.extend(_compute_segment_c(data["pae_audits"], data["pbd_audits"]))

    # Segment D — Coaching & Gaps
    print("    [D] Coaching & Gaps...")
    all_patterns.extend(_compute_segment_d(data["pae_audits"], data["pbd_audits"]))

    # Segment E — Activity & Cadence
    print("    [E] Activity & Cadence...")
    all_patterns.extend(_compute_segment_e(data["calls"], trajectories))

    # Segment F — Forecast Accuracy
    print("    [F] Forecast Accuracy...")
    all_patterns.extend(_compute_segment_f())

    # Segment G — Post-mortem (quarterly, skip if not quarter end)
    # TODO: add quarter-end check
    # print("    [G] Post-mortem Patterns (quarterly)...")
    # all_patterns.extend(_compute_segment_g())

    # Segment H — Product Knowledge
    print("    [H] Product Knowledge...")
    all_patterns.extend(_compute_segment_h())

    # Upsert all
    upserted = 0
    for p in all_patterns:
        try:
            _upsert_rep_pattern(p, today)
            upserted += 1
        except Exception as e:
            print(f"    ! upsert failed ({p.get('pattern_key')}): {e}")

    print(f"    {upserted}/{len(all_patterns)} rep patterns upserted")
    return upserted
