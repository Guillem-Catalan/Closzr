"""
Weekly Rep Stats — per-person performance patterns.

Runs inside weekly/run2.py after patterns. Pure Python (segments A-H, I alerts).
Segment K (post-mortem) uses Claude and runs quarterly only.

Each stat is computed for THREE time windows:
  - weekly  (7 days)   — last week snapshot
  - monthly (28 days)  — last 4 weeks review
  - quarterly (90 days) — last 3 months review

Pattern key format: rep_{period}_{stat}_{email_slug}
Scope: "rep:{email}"
History JSONB accumulates weekly executions.

Exception: Segment B (Pipeline Health) is always computed from current
open deals regardless of period — pipeline is a live snapshot.

Data sources:
  A. Closing Effectiveness  ← deal_trajectories (pae, pbd)
  B. Pipeline Health         ← deals + front_deal_snapshots (pae, pbd) — no period filter
  C. Process Quality         ← pae_audits / pbd_audits (owner_name)
  D. Coaching & Gaps         ← pae_audits / pbd_audits (owner_name)
  E. Activity & Cadence      ← calls + deals (owner_email, pae, pbd)
  F. Demo Funnel             ← deals (after_demo_date, createdate, close_date)
  G. Contact & Multi-threading ← deals (contact_count, contacts_info)
  H. Segment Performance     ← deals (amount, num_employees_custom)
  I. Coaching Alerts          ← learned_patterns (rep_stat + team_stat) — runs after team_stats
  J. Forecast Accuracy        ← calibration_log + snapshots (TODO)
  K. Post-mortem Patterns     ← deal_analysis — Claude, quarterly (TODO)
  L. Product Knowledge        ← deal_product_signals (TODO)
"""

import json
import traceback
from datetime import date, timedelta
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

CLOSING_PIPELINES = {"Partners Distribution", "XL Account Pipeline", "Sales Pipeline"}

EMPLOYEE_SIZE_BUCKETS = [
    ("XS", 1, 10),
    ("S", 11, 50),
    ("M", 51, 250),
    ("L", 251, 800),
    ("XL", 801, float("inf")),
]


PERIODS = {
    "weekly": 7,
    "monthly": 28,
    "quarterly": 90,
}


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


def _cutoff_date(period: str) -> date:
    """Return the earliest date to include for a given period."""
    return date.today() - timedelta(days=PERIODS[period])


def _filter_trajectories(trajectories: list[dict], period: str) -> list[dict]:
    """Filter closed trajectories by close_date within the period window.
    Open deals pass through unfiltered (for segment B)."""
    cutoff = _cutoff_date(period)
    result = []
    for t in trajectories:
        if t.get(_TC["outcome"]) == "open":
            result.append(t)
            continue
        cd = t.get(_TC["close_date"])
        if cd:
            try:
                if date.fromisoformat(str(cd)[:10]) >= cutoff:
                    result.append(t)
            except (ValueError, TypeError):
                pass
    return result


def _filter_audits(audits: list[dict], period: str) -> list[dict]:
    """Filter audits by created_at within the period window."""
    cutoff = _cutoff_date(period)
    result = []
    for a in audits:
        ca = a.get("created_at")
        if ca:
            try:
                if date.fromisoformat(str(ca)[:10]) >= cutoff:
                    result.append(a)
            except (ValueError, TypeError):
                pass
    return result


def _filter_calls(calls: list[dict], period: str) -> list[dict]:
    """Filter calls by fecha within the period window."""
    cutoff = _cutoff_date(period)
    result = []
    for c in calls:
        f = c.get("fecha")
        if f:
            try:
                if date.fromisoformat(str(f)[:10]) >= cutoff:
                    result.append(c)
            except (ValueError, TypeError):
                pass
    return result


def _inject_period(patterns: list[dict], period: str) -> list[dict]:
    """Insert period into every pattern_key: rep_{stat}_{slug} → rep_{stat}_{period}_{slug}.

    Convention: key starts with 'rep_', then stat name, then email slug at the end.
    We insert the period between the stat name and the slug by splitting on 'rep_'
    and prepending the period to the key after 'rep_'.
    """
    for p in patterns:
        key = p.get("pattern_key", "")
        if key.startswith("rep_"):
            p["pattern_key"] = f"rep_{period}_{key[4:]}"
    return patterns


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


def _load_deals() -> list[dict]:
    """Load deals from the deals table for segments F/G/H.
    Uses deals.pae (current owner) — attribution follows current ownership."""
    print("    Loading deals for segments F/G/H...")
    deals = _fetch_all_paginated(
        _TBL_DEALS,
        "deal_id, pae, pipeline_name, after_demo_date, createdate, close_date, "
        "is_closed_won, deal_stage, contact_count, contacts_info, amount, "
        "num_employees_custom",
        order_col="close_date",
    )
    deals = [d for d in deals if (d.get("pipeline_name") or "") in CLOSING_PIPELINES]
    print(f"      deals (closing pipelines): {len(deals)}")
    return deals


def _filter_deals(deals: list[dict], period: str) -> list[dict]:
    """Filter deals by close_date within the period window.
    Open deals (no close_date or not closed) are included for demo_rate."""
    cutoff = _cutoff_date(period)
    result = []
    for d in deals:
        cd = d.get("close_date")
        is_won = d.get("is_closed_won")
        stage = (d.get("deal_stage") or "").lower()
        is_closed = is_won or "lost" in stage

        if is_closed and cd:
            try:
                if date.fromisoformat(str(cd)[:10]) >= cutoff:
                    result.append(d)
            except (ValueError, TypeError):
                pass
        elif not is_closed:
            create = d.get("createdate")
            if create:
                try:
                    if date.fromisoformat(str(create)[:10]) >= cutoff:
                        result.append(d)
                except (ValueError, TypeError):
                    pass
    return result


def _group_deals_by_rep(deals: list[dict]) -> dict[str, list[dict]]:
    """Group deals by pae email (current owner)."""
    by_rep: dict[str, list[dict]] = defaultdict(list)
    for d in deals:
        email = (d.get("pae") or "").strip()
        if email:
            by_rep[email].append(d)
    return dict(by_rep)


def _classify_contact_role(role_str: str) -> str:
    """Classify a contact role string into a category."""
    role = (role_str or "").lower().strip()
    if any(w in role for w in ("ceo", "coo", "cfo", "cto", "fundador", "founder",
                                "director general", "gerente", "managing director")):
        return "C-suite"
    if any(w in role for w in ("director", "directora", "head of", "vp ", "vice president")):
        return "Director"
    if any(w in role for w in ("hr ", "rrhh", "recursos humanos", "people", "talent",
                                "human resources")):
        return "HR"
    if any(w in role for w in ("manager", "responsable", "jefe", "lead", "coordinador")):
        return "Manager"
    return "Other"


def _parse_contacts(contacts_info: str | None) -> list[dict]:
    """Parse contacts_info field: 'Name | Role | email' per line."""
    if not contacts_info:
        return []
    contacts = []
    for line in contacts_info.split("\n"):
        parts = [p.strip() for p in line.strip().split("|")]
        if len(parts) >= 2:
            contacts.append({
                "name": parts[0],
                "role_raw": parts[1] if len(parts) > 1 else "",
                "email": parts[2] if len(parts) > 2 else "",
                "role": _classify_contact_role(parts[1] if len(parts) > 1 else ""),
            })
    return contacts


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
    patterns = []
    by_rep: dict[str, list[dict]] = defaultdict(list)

    for t in trajectories:
        for role_col in ("pae", "pbd"):
            email = (t.get(_TC.get(role_col, role_col)) or "").strip().lower()
            if email and "@" in email:
                by_rep[email].append(t)

    for email, deals in by_rep.items():
        slug = _email_slug(email)
        scope = f"rep:{email}"
        closed = [d for d in deals if d.get(_TC["outcome"]) in ("won", "lost")]
        won = [d for d in closed if d[_TC["outcome"]] == "won"]
        lost = [d for d in closed if d[_TC["outcome"]] == "lost"]

        if len(closed) < 3:
            continue

        # ── A.1 win_rate ──
        wr = round(len(won) / len(closed) * 100, 1)
        patterns.append({
            "pattern_key": f"rep_win_rate_{slug}",
            "pattern_type": "rep_stat",
            "scope": scope,
            "pattern": f"Win rate: {wr}% ({len(won)} won / {len(closed)} closed)",
            "confidence": min(0.95, len(closed) / 50),
            "sample_size": len(closed),
            "value": wr,
        })

        # ── A.2 avg_cycle_won ──
        won_ages = [d[_TC["deal_age_days"]] for d in won if d.get(_TC["deal_age_days"])]
        if won_ages:
            avg_won = round(sum(won_ages) / len(won_ages), 1)
            patterns.append({
                "pattern_key": f"rep_avg_cycle_won_{slug}",
                "pattern_type": "rep_stat",
                "scope": scope,
                "pattern": f"Avg cycle (won): {avg_won} days ({len(won_ages)} deals)",
                "confidence": min(0.90, len(won_ages) / 20),
                "sample_size": len(won_ages),
                "value": avg_won,
            })

        # ── A.3 avg_cycle_lost ──
        lost_ages = [d[_TC["deal_age_days"]] for d in lost if d.get(_TC["deal_age_days"])]
        if lost_ages:
            avg_lost = round(sum(lost_ages) / len(lost_ages), 1)
            patterns.append({
                "pattern_key": f"rep_avg_cycle_lost_{slug}",
                "pattern_type": "rep_stat",
                "scope": scope,
                "pattern": f"Avg cycle (lost): {avg_lost} days ({len(lost_ages)} deals)",
                "confidence": min(0.90, len(lost_ages) / 20),
                "sample_size": len(lost_ages),
                "value": avg_lost,
            })

            # ── A.4 cycle_waste_ratio ──
            if won_ages:
                avg_won_val = sum(won_ages) / len(won_ages)
                if avg_won_val > 0:
                    ratio = round(avg_lost / avg_won_val, 2)
                    patterns.append({
                        "pattern_key": f"rep_cycle_waste_ratio_{slug}",
                        "pattern_type": "rep_stat",
                        "scope": scope,
                        "pattern": f"Cycle waste ratio: {ratio}x (lost avg {avg_lost:.0f}d vs won avg {avg_won_val:.0f}d)",
                        "confidence": min(0.85, min(len(won_ages), len(lost_ages)) / 15),
                        "sample_size": len(closed),
                        "value": ratio,
                    })

        # ── A.5 death_stage_distribution ──
        death_stages: dict[str, int] = defaultdict(int)
        for d in lost:
            sd = _parse_json(d.get(_TC["stage_dates"]) or {})
            if isinstance(sd, dict) and sd:
                last_stage = max(sd.keys(), key=lambda k: str(sd[k].get("entered", "") if isinstance(sd[k], dict) else ""))
                death_stages[last_stage] += 1
        if death_stages:
            top = sorted(death_stages.items(), key=lambda x: -x[1])[:3]
            top_text = ", ".join(f"{s}: {c}" for s, c in top)
            patterns.append({
                "pattern_key": f"rep_death_stage_distribution_{slug}",
                "pattern_type": "rep_stat",
                "scope": scope,
                "pattern": f"Death stages: {top_text} (of {len(lost)} lost)",
                "confidence": min(0.85, len(lost) / 15),
                "sample_size": len(lost),
                "value": None,
            })

        # ── A.6 slow_deaths ──
        slow = 0
        for d in lost:
            traj = _parse_json(d.get(_TC["trajectory"]) or [])
            if isinstance(traj, list) and len(traj) > 5:
                max_prob = max((s.get("close_probability", 0) or 0) for s in traj if isinstance(s, dict))
                if max_prob < 40:
                    slow += 1
        if len(lost) >= 3:
            pct_slow = round(slow / len(lost) * 100, 1)
            patterns.append({
                "pattern_key": f"rep_slow_deaths_{slug}",
                "pattern_type": "rep_stat",
                "scope": scope,
                "pattern": f"Slow deaths: {slow} ({pct_slow}% of {len(lost)} lost) — >5 snapshots, prob never >40%",
                "confidence": min(0.80, len(lost) / 15),
                "sample_size": len(lost),
                "value": pct_slow,
            })

        # ── A.7 weakest_meddic_at_loss ──
        meddic_pillars = ["m_score", "e_score", "dc_score", "dp_score", "i_score", "c_score", "comp_score"]
        pillar_sums: dict[str, list[float]] = defaultdict(list)
        for d in lost:
            traj = _parse_json(d.get(_TC["trajectory"]) or [])
            if isinstance(traj, list) and traj:
                last_snap = traj[-1] if isinstance(traj[-1], dict) else {}
                for p in meddic_pillars:
                    val = last_snap.get(p)
                    if val is not None:
                        try:
                            pillar_sums[p].append(float(val))
                        except (ValueError, TypeError):
                            pass
        if pillar_sums:
            pillar_avgs = {p: round(sum(vals) / len(vals), 1) for p, vals in pillar_sums.items() if vals}
            if pillar_avgs:
                weakest = min(pillar_avgs, key=pillar_avgs.get)
                weakest_label = weakest.replace("_score", "").upper()
                patterns.append({
                    "pattern_key": f"rep_weakest_meddic_at_loss_{slug}",
                    "pattern_type": "rep_stat",
                    "scope": scope,
                    "pattern": f"Weakest MEDDIC at loss: {weakest_label} ({pillar_avgs[weakest]}). All: {pillar_avgs}",
                    "confidence": min(0.80, len(lost) / 10),
                    "sample_size": len(lost),
                    "value": pillar_avgs[weakest],
                })

        # ── A.8 loss_reason_concentration ──
        reasons: dict[str, int] = defaultdict(int)
        for d in lost:
            r = d.get(_TC["closed_lost_reason"]) or "Unknown"
            reasons[r] += 1
        if reasons and len(lost) >= 5:
            top_reason, top_count = max(reasons.items(), key=lambda x: x[1])
            concentration = round(top_count / len(lost) * 100, 1)
            systemic = concentration > 50
            patterns.append({
                "pattern_key": f"rep_loss_reason_concentration_{slug}",
                "pattern_type": "rep_stat",
                "scope": scope,
                "pattern": f"Top loss reason: '{top_reason}' = {concentration}% of losses {'(SYSTEMIC)' if systemic else ''}. {dict(sorted(reasons.items(), key=lambda x: -x[1])[:3])}",
                "confidence": min(0.85, len(lost) / 15),
                "sample_size": len(lost),
                "value": concentration,
            })

        # ── A.9 high_conf_losses ──
        high_conf = 0
        for d in lost:
            traj = _parse_json(d.get(_TC["trajectory"]) or [])
            if isinstance(traj, list):
                max_prob = max((s.get("close_probability", 0) or 0) for s in traj if isinstance(s, dict)) if traj else 0
                if max_prob > 50:
                    high_conf += 1
        if len(lost) >= 3:
            pct_hc = round(high_conf / len(lost) * 100, 1)
            patterns.append({
                "pattern_key": f"rep_high_conf_losses_{slug}",
                "pattern_type": "rep_stat",
                "scope": scope,
                "pattern": f"High-conf losses: {high_conf} ({pct_hc}%) — lost deals that had prob >50% at some point",
                "confidence": min(0.85, len(lost) / 10),
                "sample_size": len(lost),
                "value": pct_hc,
            })

        # ── A.10 comeback_wins ──
        comebacks = 0
        for d in won:
            traj = _parse_json(d.get(_TC["trajectory"]) or [])
            if isinstance(traj, list):
                min_prob = min((s.get("close_probability", 100) or 100) for s in traj if isinstance(s, dict)) if traj else 100
                if min_prob < 30:
                    comebacks += 1
        if len(won) >= 3:
            pct_cb = round(comebacks / len(won) * 100, 1)
            patterns.append({
                "pattern_key": f"rep_comeback_wins_{slug}",
                "pattern_type": "rep_stat",
                "scope": scope,
                "pattern": f"Comeback wins: {comebacks} ({pct_cb}%) — won deals that dipped below 30% prob",
                "confidence": min(0.80, len(won) / 10),
                "sample_size": len(won),
                "value": pct_cb,
            })

        # ── A.11 prob_climb_rate_won ──
        climb_rates = []
        for d in won:
            traj = _parse_json(d.get(_TC["trajectory"]) or [])
            if isinstance(traj, list) and len(traj) >= 2:
                probs = [s.get("close_probability") for s in traj if isinstance(s, dict) and s.get("close_probability") is not None]
                if len(probs) >= 2:
                    climb = (probs[-1] - probs[0]) / len(probs)
                    climb_rates.append(climb)
        if climb_rates:
            avg_climb = round(sum(climb_rates) / len(climb_rates), 2)
            patterns.append({
                "pattern_key": f"rep_prob_climb_rate_won_{slug}",
                "pattern_type": "rep_stat",
                "scope": scope,
                "pattern": f"Prob climb rate (won): {avg_climb}% per snapshot ({len(climb_rates)} deals)",
                "confidence": min(0.80, len(climb_rates) / 10),
                "sample_size": len(climb_rates),
                "value": avg_climb,
            })

        # ── A.12 stage_conversion_funnel ──
        stage_reached: dict[str, dict[str, int]] = defaultdict(lambda: {"won": 0, "lost": 0})
        for d in closed:
            sd = _parse_json(d.get(_TC["stage_dates"]) or {})
            if isinstance(sd, dict):
                for stage_key in sd:
                    stage_reached[stage_key][d[_TC["outcome"]]] += 1
        funnel_parts = []
        for stage_key, counts in sorted(stage_reached.items()):
            total = counts["won"] + counts["lost"]
            if total >= 5:
                cvr = round(counts["won"] / total * 100)
                funnel_parts.append(f"{stage_key}: {cvr}% ({total})")
        if funnel_parts:
            patterns.append({
                "pattern_key": f"rep_stage_conversion_funnel_{slug}",
                "pattern_type": "rep_stat",
                "scope": scope,
                "pattern": f"Stage CVR: {'; '.join(funnel_parts[:8])}",
                "confidence": min(0.85, len(closed) / 30),
                "sample_size": len(closed),
                "value": None,
            })

        # ── A.13 / A.14 avg_calls_to_win / avg_calls_to_lose ──
        for outcome_label, outcome_deals in [("win", won), ("lose", lost)]:
            call_counts = []
            for d in outcome_deals:
                interactions = _parse_json(d.get(_TC["interactions"]) or {})
                if isinstance(interactions, dict):
                    n_calls = interactions.get("calls", 0) or 0
                    if isinstance(n_calls, (int, float)):
                        call_counts.append(n_calls)
            if call_counts:
                avg_calls = round(sum(call_counts) / len(call_counts), 1)
                patterns.append({
                    "pattern_key": f"rep_avg_calls_to_{outcome_label}_{slug}",
                    "pattern_type": "rep_stat",
                    "scope": scope,
                    "pattern": f"Avg calls to {outcome_label}: {avg_calls} ({len(call_counts)} deals)",
                    "confidence": min(0.80, len(call_counts) / 10),
                    "sample_size": len(call_counts),
                    "value": avg_calls,
                })

        # ── A.extra: win_rate_rolling_6m (TL priority) ──
        six_months_ago = date.today() - timedelta(days=180)
        recent_closed = []
        for d in closed:
            cd = d.get(_TC["close_date"])
            age = d.get(_TC["deal_age_days"])
            if cd and age:
                try:
                    close_d = date.fromisoformat(str(cd)[:10])
                    create_d = close_d - timedelta(days=int(age))
                    if create_d >= six_months_ago:
                        recent_closed.append(d)
                except (ValueError, TypeError):
                    pass
        if len(recent_closed) >= 3:
            recent_won = sum(1 for d in recent_closed if d[_TC["outcome"]] == "won")
            wr_6m = round(recent_won / len(recent_closed) * 100, 1)
            patterns.append({
                "pattern_key": f"rep_win_rate_rolling_6m_{slug}",
                "pattern_type": "rep_stat",
                "scope": scope,
                "pattern": f"Win rate (6m velocity): {wr_6m}% ({recent_won}/{len(recent_closed)} — only deals opened+closed in last 6 months)",
                "confidence": min(0.90, len(recent_closed) / 20),
                "sample_size": len(recent_closed),
                "value": wr_6m,
            })

    return patterns


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
    patterns = []
    by_rep: dict[str, list[dict]] = defaultdict(list)

    for t in trajectories:
        if t.get(_TC["outcome"]) != "open":
            continue
        for role_col in ("pae", "pbd"):
            email = (t.get(_TC.get(role_col, role_col)) or "").strip().lower()
            if email and "@" in email:
                by_rep[email].append(t)

    for email, active in by_rep.items():
        slug = _email_slug(email)
        scope = f"rep:{email}"

        if not active:
            continue

        # ── B.15 active_deals_count ──
        patterns.append({
            "pattern_key": f"rep_active_deals_count_{slug}",
            "pattern_type": "rep_stat",
            "scope": scope,
            "pattern": f"Active deals: {len(active)}",
            "confidence": 0.99,
            "sample_size": len(active),
            "value": len(active),
        })

        # ── B.16 pipeline_value ──
        amounts = [float(d.get(_TC["amount"]) or 0) for d in active if d.get(_TC["amount"])]
        total_mrr = round(sum(amounts), 2)
        patterns.append({
            "pattern_key": f"rep_pipeline_value_{slug}",
            "pattern_type": "rep_stat",
            "scope": scope,
            "pattern": f"Pipeline value: €{total_mrr:,.0f} MRR ({len(active)} deals)",
            "confidence": 0.99,
            "sample_size": len(active),
            "value": total_mrr,
        })

        # ── B.17 stale_deals ──
        stale_threshold = 14
        stale_count = 0
        today = date.today()
        for d in active:
            traj = _parse_json(d.get(_TC["trajectory"]) or [])
            if isinstance(traj, list) and traj:
                last_snap = traj[-1] if isinstance(traj[-1], dict) else {}
                snap_date = last_snap.get("snapshot_date")
                if snap_date:
                    try:
                        sd = date.fromisoformat(str(snap_date)[:10])
                        if (today - sd).days > stale_threshold:
                            stale_count += 1
                    except (ValueError, TypeError):
                        pass
        pct_stale = round(stale_count / len(active) * 100, 1) if active else 0
        patterns.append({
            "pattern_key": f"rep_stale_deals_{slug}",
            "pattern_type": "rep_stat",
            "scope": scope,
            "pattern": f"Stale deals: {stale_count} ({pct_stale}%) — no snapshot in >{stale_threshold} days",
            "confidence": 0.90,
            "sample_size": len(active),
            "value": pct_stale,
        })

        # ── B.18 momentum_distribution ──
        momentum_counts: dict[str, int] = defaultdict(int)
        for d in active:
            traj = _parse_json(d.get(_TC["trajectory"]) or [])
            if isinstance(traj, list) and len(traj) >= 2:
                probs = [s.get("close_probability") for s in traj[-3:] if isinstance(s, dict) and s.get("close_probability") is not None]
                if len(probs) >= 2:
                    delta = probs[-1] - probs[0]
                    if delta > 5:
                        momentum_counts["accelerating"] += 1
                    elif delta < -5:
                        momentum_counts["decelerating"] += 1
                    else:
                        momentum_counts["stable"] += 1
                else:
                    momentum_counts["unknown"] += 1
            else:
                momentum_counts["unknown"] += 1
        if active:
            parts = [f"{k}: {round(v / len(active) * 100)}%" for k, v in sorted(momentum_counts.items())]
            patterns.append({
                "pattern_key": f"rep_momentum_distribution_{slug}",
                "pattern_type": "rep_stat",
                "scope": scope,
                "pattern": f"Momentum: {', '.join(parts)} ({len(active)} deals)",
                "confidence": min(0.80, len(active) / 10),
                "sample_size": len(active),
                "value": momentum_counts.get("accelerating", 0),
            })

        # ── B.20 stage_distribution ──
        stage_counts: dict[str, int] = defaultdict(int)
        for d in active:
            sd = _parse_json(d.get(_TC["stage_dates"]) or {})
            if isinstance(sd, dict) and sd:
                last_stage = max(sd.keys(), key=lambda k: str(sd[k].get("entered", "") if isinstance(sd[k], dict) else ""))
                stage_counts[last_stage] += 1
        if stage_counts:
            parts = [f"{s}: {c}" for s, c in sorted(stage_counts.items(), key=lambda x: -x[1])[:5]]
            patterns.append({
                "pattern_key": f"rep_stage_distribution_{slug}",
                "pattern_type": "rep_stat",
                "scope": scope,
                "pattern": f"Stage distribution: {', '.join(parts)}",
                "confidence": 0.95,
                "sample_size": len(active),
                "value": None,
            })

        # ── B.22 forecast_category_distribution ──
        # forecast_category is not in trajectories — skip if not available

        # ── B.24 avg_deal_age ──
        ages = [d[_TC["deal_age_days"]] for d in active if d.get(_TC["deal_age_days"])]
        if ages:
            avg_age = round(sum(ages) / len(ages), 1)
            patterns.append({
                "pattern_key": f"rep_avg_deal_age_{slug}",
                "pattern_type": "rep_stat",
                "scope": scope,
                "pattern": f"Avg deal age: {avg_age} days ({len(ages)} active deals)",
                "confidence": 0.95,
                "sample_size": len(ages),
                "value": avg_age,
            })

    return patterns


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
    patterns = []

    # PAE audits → MEDDIC scores
    pae_by_rep: dict[str, list[dict]] = defaultdict(list)
    for a in pae_audits:
        name = (a.get("owner_name") or "").strip()
        if name:
            pae_by_rep[name].append(a)

    meddic_cols = {
        "M": "m_score", "E": "e_score", "DC": "dc_score",
        "DP": "dp_score", "I": "i_score", "C": "c_score", "COMP": "comp_score",
    }

    for rep_name, audits in pae_by_rep.items():
        slug = _email_slug(rep_name)
        scope = f"rep_name:{rep_name}"

        if len(audits) < 3:
            continue

        # ── C.25 avg_meddic_per_pillar ──
        pillar_avgs = {}
        for label, col in meddic_cols.items():
            vals = [float(a[col]) for a in audits if a.get(col) is not None]
            if vals:
                pillar_avgs[label] = round(sum(vals) / len(vals), 1)

        if pillar_avgs:
            parts = [f"{k}: {v}" for k, v in pillar_avgs.items()]
            overall = round(sum(pillar_avgs.values()) / len(pillar_avgs), 1)
            patterns.append({
                "pattern_key": f"rep_avg_meddic_per_pillar_{slug}",
                "pattern_type": "rep_stat",
                "scope": scope,
                "pattern": f"MEDDIC avg: {', '.join(parts)} (overall {overall})",
                "confidence": min(0.90, len(audits) / 15),
                "sample_size": len(audits),
                "value": overall,
            })

            # ── C.26 weakest_pillar ──
            weakest = min(pillar_avgs, key=pillar_avgs.get)
            patterns.append({
                "pattern_key": f"rep_weakest_pillar_{slug}",
                "pattern_type": "rep_stat",
                "scope": scope,
                "pattern": f"Weakest MEDDIC pillar: {weakest} ({pillar_avgs[weakest]})",
                "confidence": min(0.85, len(audits) / 10),
                "sample_size": len(audits),
                "value": pillar_avgs[weakest],
            })

            # ── C.27 strongest_pillar ──
            strongest = max(pillar_avgs, key=pillar_avgs.get)
            patterns.append({
                "pattern_key": f"rep_strongest_pillar_{slug}",
                "pattern_type": "rep_stat",
                "scope": scope,
                "pattern": f"Strongest MEDDIC pillar: {strongest} ({pillar_avgs[strongest]})",
                "confidence": min(0.85, len(audits) / 10),
                "sample_size": len(audits),
                "value": pillar_avgs[strongest],
            })

        # ── C.30 discovery_level_avg ──
        disc_vals = [float(a["discovery_level"]) for a in audits if a.get("discovery_level") is not None]
        if disc_vals:
            avg_disc = round(sum(disc_vals) / len(disc_vals), 1)
            patterns.append({
                "pattern_key": f"rep_discovery_level_avg_{slug}",
                "pattern_type": "rep_stat",
                "scope": scope,
                "pattern": f"Discovery level avg: {avg_disc} ({len(disc_vals)} audits)",
                "confidence": min(0.85, len(disc_vals) / 10),
                "sample_size": len(disc_vals),
                "value": avg_disc,
            })

        # ── C.31 win_rate_score_avg ──
        wr_vals = [float(a["win_rate_score"]) for a in audits if a.get("win_rate_score") is not None]
        if wr_vals:
            avg_wr = round(sum(wr_vals) / len(wr_vals), 1)
            patterns.append({
                "pattern_key": f"rep_win_rate_score_avg_{slug}",
                "pattern_type": "rep_stat",
                "scope": scope,
                "pattern": f"Audit win rate score avg: {avg_wr} ({len(wr_vals)} audits)",
                "confidence": min(0.85, len(wr_vals) / 10),
                "sample_size": len(wr_vals),
                "value": avg_wr,
            })

        # ── C.32 lead_temperature_distribution ──
        temps: dict[str, int] = defaultdict(int)
        for a in audits:
            t = a.get("lead_temperature")
            if t:
                temps[str(t)] += 1
        if temps:
            parts = [f"{k}: {v}" for k, v in sorted(temps.items(), key=lambda x: -x[1])]
            patterns.append({
                "pattern_key": f"rep_lead_temperature_distribution_{slug}",
                "pattern_type": "rep_stat",
                "scope": scope,
                "pattern": f"Lead temperature: {', '.join(parts)}",
                "confidence": min(0.85, len(audits) / 10),
                "sample_size": len(audits),
                "value": None,
            })

    # PBD audits → BANT
    pbd_by_rep: dict[str, list[dict]] = defaultdict(list)
    for a in pbd_audits:
        name = (a.get("owner_name") or "").strip()
        if name:
            pbd_by_rep[name].append(a)

    for rep_name, audits in pbd_by_rep.items():
        slug = _email_slug(rep_name)
        scope = f"rep_name:{rep_name}"

        if len(audits) < 3:
            continue

        # ── C.29 bant_completion_rate ──
        bant_cols = ["budget", "authority", "need", "timing"]
        complete = 0
        for a in audits:
            if all(a.get(c) is not None and str(a.get(c)).strip() for c in bant_cols):
                complete += 1
        pct_complete = round(complete / len(audits) * 100, 1)
        patterns.append({
            "pattern_key": f"rep_bant_completion_rate_{slug}",
            "pattern_type": "rep_stat",
            "scope": scope,
            "pattern": f"BANT completion: {pct_complete}% ({complete}/{len(audits)} audits fully scored)",
            "confidence": min(0.85, len(audits) / 10),
            "sample_size": len(audits),
            "value": pct_complete,
        })

    return patterns


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
    patterns = []
    all_audits_by_rep: dict[str, list[dict]] = defaultdict(list)

    for a in pae_audits + pbd_audits:
        name = (a.get("owner_name") or "").strip()
        if name:
            all_audits_by_rep[name].append(a)

    for rep_name, audits in all_audits_by_rep.items():
        slug = _email_slug(rep_name)
        scope = f"rep_name:{rep_name}"

        if len(audits) < 3:
            continue

        # ── D.33 top_improvement_items ──
        item_counts: dict[str, int] = defaultdict(int)
        for a in audits:
            items = _parse_json(a.get("improvement_items_json") or [])
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, str) and item.strip():
                        item_counts[item.strip()] += 1
                    elif isinstance(item, dict):
                        label = item.get("item") or item.get("label") or item.get("name") or ""
                        if label.strip():
                            item_counts[label.strip()] += 1
        if item_counts:
            top = sorted(item_counts.items(), key=lambda x: -x[1])[:5]
            top_text = ", ".join(f"{i}: {c}x" for i, c in top)
            patterns.append({
                "pattern_key": f"rep_top_improvement_items_{slug}",
                "pattern_type": "rep_stat",
                "scope": scope,
                "pattern": f"Top improvements: {top_text}",
                "confidence": min(0.80, len(audits) / 10),
                "sample_size": len(audits),
                "value": top[0][1] if top else None,
            })

        # ── D.35 top_strengths ──
        strength_counts: dict[str, int] = defaultdict(int)
        for a in audits:
            strengths = _parse_json(a.get("rep_strengths") or [])
            if isinstance(strengths, list):
                for s in strengths:
                    if isinstance(s, str) and s.strip():
                        strength_counts[s.strip()] += 1
            elif isinstance(strengths, str) and strengths.strip():
                strength_counts[strengths.strip()] += 1
        if strength_counts:
            top = sorted(strength_counts.items(), key=lambda x: -x[1])[:5]
            top_text = ", ".join(f"{s}: {c}x" for s, c in top)
            patterns.append({
                "pattern_key": f"rep_top_strengths_{slug}",
                "pattern_type": "rep_stat",
                "scope": scope,
                "pattern": f"Top strengths: {top_text}",
                "confidence": min(0.80, len(audits) / 10),
                "sample_size": len(audits),
                "value": None,
            })

        # ── D.36 recurring_biggest_gaps ──
        gap_counts: dict[str, int] = defaultdict(int)
        for a in audits:
            gap = a.get("biggest_gap")
            if gap and isinstance(gap, str) and gap.strip():
                gap_counts[gap.strip()] += 1
        if gap_counts:
            top = sorted(gap_counts.items(), key=lambda x: -x[1])[:3]
            top_text = ", ".join(f"{g}: {c}x" for g, c in top)
            patterns.append({
                "pattern_key": f"rep_recurring_biggest_gaps_{slug}",
                "pattern_type": "rep_stat",
                "scope": scope,
                "pattern": f"Recurring gaps: {top_text}",
                "confidence": min(0.80, len(audits) / 10),
                "sample_size": len(audits),
                "value": top[0][1] if top else None,
            })

        # ── D.37 / D.38 red_flags_frequency & trend ──
        rf_counts: dict[str, int] = defaultdict(int)
        total_flags = 0
        for a in audits:
            flags = _parse_json(a.get("red_flags_fired") or [])
            if isinstance(flags, list):
                total_flags += len(flags)
                for f in flags:
                    if isinstance(f, str) and f.strip():
                        rf_counts[f.strip()] += 1
        if total_flags > 0:
            avg_flags = round(total_flags / len(audits), 2)
            top_flags = sorted(rf_counts.items(), key=lambda x: -x[1])[:3]
            top_text = ", ".join(f"{f}: {c}x" for f, c in top_flags)
            patterns.append({
                "pattern_key": f"rep_red_flags_frequency_{slug}",
                "pattern_type": "rep_stat",
                "scope": scope,
                "pattern": f"Red flags: {avg_flags}/audit avg, {total_flags} total. Top: {top_text}",
                "confidence": min(0.80, len(audits) / 10),
                "sample_size": len(audits),
                "value": avg_flags,
            })

    return patterns


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
    patterns = []

    # Group calls by rep email
    calls_by_rep: dict[str, list[dict]] = defaultdict(list)
    for c in calls:
        email = (c.get("owner_email") or "").strip().lower()
        if email and "@" in email:
            calls_by_rep[email].append(c)

    for email, rep_calls in calls_by_rep.items():
        slug = _email_slug(email)
        scope = f"rep:{email}"

        if len(rep_calls) < 5:
            continue

        # ── E.40 calls_per_week ──
        call_dates = []
        for c in rep_calls:
            f = c.get("fecha")
            if f:
                try:
                    call_dates.append(date.fromisoformat(str(f)[:10]))
                except (ValueError, TypeError):
                    pass
        if len(call_dates) >= 2:
            call_dates.sort()
            span_weeks = max((call_dates[-1] - call_dates[0]).days / 7, 1)
            cpw = round(len(call_dates) / span_weeks, 1)
            patterns.append({
                "pattern_key": f"rep_calls_per_week_{slug}",
                "pattern_type": "rep_stat",
                "scope": scope,
                "pattern": f"Calls/week: {cpw} ({len(call_dates)} calls over {span_weeks:.0f} weeks)",
                "confidence": min(0.90, len(call_dates) / 30),
                "sample_size": len(call_dates),
                "value": cpw,
            })

        # ── E.41 avg_call_duration ──
        durations = [c["duracion_segundos"] for c in rep_calls if c.get("duracion_segundos") and c["duracion_segundos"] > 0]
        if durations:
            avg_dur_min = round(sum(durations) / len(durations) / 60, 1)
            patterns.append({
                "pattern_key": f"rep_avg_call_duration_{slug}",
                "pattern_type": "rep_stat",
                "scope": scope,
                "pattern": f"Avg call duration: {avg_dur_min} min ({len(durations)} calls)",
                "confidence": min(0.90, len(durations) / 20),
                "sample_size": len(durations),
                "value": avg_dur_min,
            })

        # ── E.42 calls_per_deal ──
        deal_ids = set()
        calls_with_deal = 0
        for c in rep_calls:
            did = c.get("deal_id")
            if did:
                deal_ids.add(did)
                calls_with_deal += 1
        if deal_ids:
            cpd = round(calls_with_deal / len(deal_ids), 1)
            patterns.append({
                "pattern_key": f"rep_calls_per_deal_{slug}",
                "pattern_type": "rep_stat",
                "scope": scope,
                "pattern": f"Calls/deal: {cpd} ({calls_with_deal} calls across {len(deal_ids)} deals)",
                "confidence": min(0.85, len(deal_ids) / 10),
                "sample_size": len(deal_ids),
                "value": cpd,
            })

    return patterns


# ═══════════════════════════════════════════════════════════════════════════
# SEGMENT F — DEMO FUNNEL (5 stats per rep)
#
# Source: deals table (after_demo_date, createdate, close_date, is_closed_won)
# Closing pipelines only. Uses current ownership (deals.pae).
# ═══════════════════════════════════════════════════════════════════════════

def _compute_segment_f(deals_by_rep: dict[str, list[dict]]) -> list[dict]:
    """Demo funnel stats — per rep from deals table."""
    patterns = []

    for email, rep_deals in deals_by_rep.items():
        slug = _email_slug(email)
        scope = f"rep:{email}"

        if len(rep_deals) < 3:
            continue

        has_demo = [d for d in rep_deals if d.get("after_demo_date")]
        no_demo = [d for d in rep_deals if not d.get("after_demo_date")]
        won = [d for d in rep_deals if d.get("is_closed_won")]
        lost_stage = [d for d in rep_deals if "lost" in (d.get("deal_stage") or "").lower()]
        won_with_demo = [d for d in won if d.get("after_demo_date")]

        # ── F.1 demo_rate ──
        dr = round(len(has_demo) / len(rep_deals) * 100, 1)
        patterns.append({
            "pattern_key": f"rep_demo_rate_{slug}",
            "pattern_type": "rep_stat",
            "scope": scope,
            "pattern": f"Demo rate: {dr}% ({len(has_demo)}/{len(rep_deals)} deals reached demo)",
            "confidence": min(0.90, len(rep_deals) / 30),
            "sample_size": len(rep_deals),
            "value": dr,
        })

        # ── F.2 post_demo_win_rate ──
        if has_demo:
            pdwr = round(len(won_with_demo) / len(has_demo) * 100, 1)
            patterns.append({
                "pattern_key": f"rep_post_demo_win_rate_{slug}",
                "pattern_type": "rep_stat",
                "scope": scope,
                "pattern": f"Post-demo WR: {pdwr}% ({len(won_with_demo)}/{len(has_demo)} demo deals won)",
                "confidence": min(0.90, len(has_demo) / 20),
                "sample_size": len(has_demo),
                "value": pdwr,
            })

        # ── F.3 avg_days_to_demo ──
        days_to_demo = []
        for d in has_demo:
            try:
                created = date.fromisoformat(str(d["createdate"])[:10])
                demo = date.fromisoformat(str(d["after_demo_date"])[:10])
                diff = (demo - created).days
                if diff >= 0:
                    days_to_demo.append(diff)
            except (ValueError, TypeError, KeyError):
                pass
        if days_to_demo:
            avg_dtd = round(sum(days_to_demo) / len(days_to_demo), 1)
            patterns.append({
                "pattern_key": f"rep_avg_days_to_demo_{slug}",
                "pattern_type": "rep_stat",
                "scope": scope,
                "pattern": f"Avg days to demo: {avg_dtd}d ({len(days_to_demo)} deals)",
                "confidence": min(0.85, len(days_to_demo) / 15),
                "sample_size": len(days_to_demo),
                "value": avg_dtd,
            })

        # ── F.4 demo_to_close_days (won only) ──
        dtc_days = []
        for d in won_with_demo:
            try:
                demo = date.fromisoformat(str(d["after_demo_date"])[:10])
                close = date.fromisoformat(str(d["close_date"])[:10])
                diff = (close - demo).days
                if diff >= 0:
                    dtc_days.append(diff)
            except (ValueError, TypeError, KeyError):
                pass
        if dtc_days:
            avg_dtc = round(sum(dtc_days) / len(dtc_days), 1)
            patterns.append({
                "pattern_key": f"rep_demo_to_close_days_{slug}",
                "pattern_type": "rep_stat",
                "scope": scope,
                "pattern": f"Demo-to-close: {avg_dtc}d ({len(dtc_days)} won deals)",
                "confidence": min(0.85, len(dtc_days) / 10),
                "sample_size": len(dtc_days),
                "value": avg_dtc,
            })

        # ── F.5 no_demo_loss_rate ──
        lost_no_demo = [d for d in lost_stage if not d.get("after_demo_date")]
        if lost_stage:
            ndlr = round(len(lost_no_demo) / len(lost_stage) * 100, 1)
            patterns.append({
                "pattern_key": f"rep_no_demo_loss_rate_{slug}",
                "pattern_type": "rep_stat",
                "scope": scope,
                "pattern": f"No-demo loss rate: {ndlr}% ({len(lost_no_demo)}/{len(lost_stage)} lost without demo)",
                "confidence": min(0.85, len(lost_stage) / 15),
                "sample_size": len(lost_stage),
                "value": ndlr,
            })

    return patterns


# ═══════════════════════════════════════════════════════════════════════════
# SEGMENT G — CONTACT & MULTI-THREADING (5 stats per rep)
#
# Source: deals table (contact_count, contacts_info, after_demo_date)
# Closing pipelines only. Uses current ownership (deals.pae).
# ═══════════════════════════════════════════════════════════════════════════

def _compute_segment_g(deals_by_rep: dict[str, list[dict]]) -> list[dict]:
    """Contact & multi-threading stats — per rep from deals table."""
    patterns = []

    for email, rep_deals in deals_by_rep.items():
        slug = _email_slug(email)
        scope = f"rep:{email}"

        if len(rep_deals) < 3:
            continue

        # ── G.1 avg_contacts_per_deal ──
        contact_counts = [d.get("contact_count") or 0 for d in rep_deals]
        avg_cc = round(sum(contact_counts) / len(contact_counts), 1)
        patterns.append({
            "pattern_key": f"rep_avg_contacts_per_deal_{slug}",
            "pattern_type": "rep_stat",
            "scope": scope,
            "pattern": f"Avg contacts/deal: {avg_cc} ({len(rep_deals)} deals)",
            "confidence": min(0.90, len(rep_deals) / 30),
            "sample_size": len(rep_deals),
            "value": avg_cc,
        })

        # ── G.2 multi_thread_rate ──
        multi = sum(1 for cc in contact_counts if cc >= 2)
        mtr = round(multi / len(rep_deals) * 100, 1)
        patterns.append({
            "pattern_key": f"rep_multi_thread_rate_{slug}",
            "pattern_type": "rep_stat",
            "scope": scope,
            "pattern": f"Multi-thread rate: {mtr}% ({multi}/{len(rep_deals)} deals with 2+ contacts)",
            "confidence": min(0.90, len(rep_deals) / 30),
            "sample_size": len(rep_deals),
            "value": mtr,
        })

        # ── G.3 multi_thread_demo_rate ──
        demo_deals = [d for d in rep_deals if d.get("after_demo_date")]
        if demo_deals:
            demo_multi = sum(1 for d in demo_deals if (d.get("contact_count") or 0) >= 2)
            mtdr = round(demo_multi / len(demo_deals) * 100, 1)
            patterns.append({
                "pattern_key": f"rep_multi_thread_demo_rate_{slug}",
                "pattern_type": "rep_stat",
                "scope": scope,
                "pattern": f"Multi-thread on demo deals: {mtdr}% ({demo_multi}/{len(demo_deals)})",
                "confidence": min(0.85, len(demo_deals) / 20),
                "sample_size": len(demo_deals),
                "value": mtdr,
            })

        # ── G.4 dm_access_rate ──
        dm_roles = {"C-suite", "Director"}
        deals_with_dm = 0
        for d in rep_deals:
            contacts = _parse_contacts(d.get("contacts_info"))
            if any(c["role"] in dm_roles for c in contacts):
                deals_with_dm += 1
        dm_rate = round(deals_with_dm / len(rep_deals) * 100, 1)
        patterns.append({
            "pattern_key": f"rep_dm_access_rate_{slug}",
            "pattern_type": "rep_stat",
            "scope": scope,
            "pattern": f"DM access rate: {dm_rate}% ({deals_with_dm}/{len(rep_deals)} deals with C-suite/Director)",
            "confidence": min(0.85, len(rep_deals) / 20),
            "sample_size": len(rep_deals),
            "value": dm_rate,
        })

        # ── G.5 contact_role_distribution ──
        role_counts: dict[str, int] = defaultdict(int)
        total_contacts = 0
        for d in rep_deals:
            contacts = _parse_contacts(d.get("contacts_info"))
            for c in contacts:
                role_counts[c["role"]] += 1
                total_contacts += 1
        if total_contacts > 0:
            parts = []
            for role in ("C-suite", "Director", "HR", "Manager", "Other"):
                pct = round(role_counts[role] / total_contacts * 100)
                parts.append(f"{role}: {pct}%")
            dist_text = ", ".join(parts)
            patterns.append({
                "pattern_key": f"rep_contact_role_distribution_{slug}",
                "pattern_type": "rep_stat",
                "scope": scope,
                "pattern": f"Role distribution: {dist_text} ({total_contacts} total contacts)",
                "confidence": min(0.80, total_contacts / 50),
                "sample_size": total_contacts,
                "value": None,
            })

    return patterns


# ═══════════════════════════════════════════════════════════════════════════
# SEGMENT H — SEGMENT PERFORMANCE (3 stats per rep)
#
# Source: deals table (amount, num_employees_custom, is_closed_won)
# Closing pipelines only. Closed deals within period.
# ═══════════════════════════════════════════════════════════════════════════

def _employee_bucket(count: int | None) -> str | None:
    """Classify employee count into size bucket."""
    if not count or count < 1:
        return None
    for label, lo, hi in EMPLOYEE_SIZE_BUCKETS:
        if lo <= count <= hi:
            return label
    return None


def _compute_segment_h(deals_by_rep: dict[str, list[dict]]) -> list[dict]:
    """Segment performance stats — per rep from deals table."""
    patterns = []

    for email, rep_deals in deals_by_rep.items():
        slug = _email_slug(email)
        scope = f"rep:{email}"

        closed = [d for d in rep_deals
                  if d.get("is_closed_won") or "lost" in (d.get("deal_stage") or "").lower()]
        won = [d for d in closed if d.get("is_closed_won")]

        if len(closed) < 5:
            continue

        # ── H.1 wr_by_employee_size ──
        bucket_stats: dict[str, dict[str, int]] = {}
        for label, _, _ in EMPLOYEE_SIZE_BUCKETS:
            bucket_stats[label] = {"won": 0, "total": 0}

        for d in closed:
            emp = d.get("num_employees_custom")
            try:
                emp_int = int(emp) if emp else None
            except (ValueError, TypeError):
                emp_int = None
            b = _employee_bucket(emp_int)
            if b:
                bucket_stats[b]["total"] += 1
                if d.get("is_closed_won"):
                    bucket_stats[b]["won"] += 1

        parts = []
        for label, _, _ in EMPLOYEE_SIZE_BUCKETS:
            s = bucket_stats[label]
            if s["total"] > 0:
                wr = round(s["won"] / s["total"] * 100)
                parts.append(f"{label}: {wr}% ({s['total']}d)")
            else:
                parts.append(f"{label}: — (0d)")

        patterns.append({
            "pattern_key": f"rep_wr_by_employee_size_{slug}",
            "pattern_type": "rep_stat",
            "scope": scope,
            "pattern": f"WR by size: {', '.join(parts)}",
            "confidence": min(0.80, len(closed) / 30),
            "sample_size": len(closed),
            "value": None,
        })

        # ── H.2 sweet_spot_segment ──
        best_label = None
        best_wr = -1
        for label, _, _ in EMPLOYEE_SIZE_BUCKETS:
            s = bucket_stats[label]
            if s["total"] >= 5:
                wr = s["won"] / s["total"]
                if wr > best_wr:
                    best_wr = wr
                    best_label = label
        if best_label:
            patterns.append({
                "pattern_key": f"rep_sweet_spot_segment_{slug}",
                "pattern_type": "rep_stat",
                "scope": scope,
                "pattern": f"Sweet spot: {best_label} ({round(best_wr * 100)}% WR, {bucket_stats[best_label]['total']} deals)",
                "confidence": min(0.75, bucket_stats[best_label]["total"] / 10),
                "sample_size": bucket_stats[best_label]["total"],
                "value": round(best_wr * 100, 1),
            })

        # ── H.3 avg_deal_size_won ──
        won_amounts = [d.get("amount") for d in won if d.get("amount") and d["amount"] > 0]
        if won_amounts:
            avg_size = round(sum(won_amounts) / len(won_amounts))
            patterns.append({
                "pattern_key": f"rep_avg_deal_size_won_{slug}",
                "pattern_type": "rep_stat",
                "scope": scope,
                "pattern": f"Avg deal size (won): €{avg_size} ({len(won_amounts)} deals)",
                "confidence": min(0.85, len(won_amounts) / 10),
                "sample_size": len(won_amounts),
                "value": avg_size,
            })

    return patterns


# ═══════════════════════════════════════════════════════════════════════════
# SEGMENT J — FORECAST ACCURACY (5 stats per rep)  (was F)
#
# Source: calibration_log + front_deal_snapshots
# Key stats:
#   - forecast_accuracy_pct, avg_days_off
#   - false_positive_rate, false_negative_rate
#   - probability_calibration (predicted vs actual)
# ═══════════════════════════════════════════════════════════════════════════

def _compute_segment_j() -> list[dict]:
    """Forecast accuracy — per rep from calibration data.

    Requires calibration_log table (populated by daily forecast pipeline).
    Each row has a deal_id, predicted_close_date, actual_close_date, and
    whether the prediction was correct. Needs a join with deals to get pae/pbd.

    TODO: implement once calibration_log has enough data.
    Current calibration_log may not have per-rep attribution yet.
    """
    return []


# ═══════════════════════════════════════════════════════════════════════════
# SEGMENT K — POST-MORTEM PATTERNS (was G)
#
# Source: deal_analysis
# Key stats:
#   - what_worked patterns, what_failed patterns
#   - products_missed frequency
#   - rep_assessment summary
#   - key turning points patterns
# ═══════════════════════════════════════════════════════════════════════════

def _compute_segment_k() -> list[dict]:
    """Post-mortem patterns — per rep, quarterly, uses Claude.

    Reads deal_analysis table (what_worked, what_failed, products_missed,
    rep_assessment). Groups by rep, sends to Claude for pattern extraction.
    Only runs at quarter end.

    TODO: implement quarterly schedule check + Claude prompt.
    """
    return []


# ═══════════════════════════════════════════════════════════════════════════
# SEGMENT L — PRODUCT KNOWLEDGE (was H)
#
# Source: deal_product_signals
# Key stats:
#   - products_pitched distribution
#   - missed_vs_pitched ratio
#   - pitch_quality avg
#   - upsell_detection_rate
# ═══════════════════════════════════════════════════════════════════════════

def _compute_segment_l() -> list[dict]:
    """Product knowledge — per rep from deal_product_signals.

    Each row has products_discussed, upsell_opportunity, pitch_quality
    per deal per snapshot. Needs aggregation by rep (via deal→pae/pbd join).

    TODO: implement — requires loading deal_product_signals + joining with
    deals to get rep attribution. Low volume currently.
    """
    return []


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def run() -> int:
    print("\n  REP STATS: computing per-person patterns...")
    today = date.today().isoformat()

    data = _load_data()
    all_deals_raw = _load_deals()
    all_trajectories = data["trajectories"]

    if len(all_trajectories) < 10:
        print(f"    Only {len(all_trajectories)} trajectories — skipping rep stats")
        return 0

    all_patterns = []

    for period, days in PERIODS.items():
        print(f"\n    ── {period.upper()} ({days}d) ──")

        trajs = _filter_trajectories(all_trajectories, period)
        pae = _filter_audits(data["pae_audits"], period)
        pbd = _filter_audits(data["pbd_audits"], period)
        calls = _filter_calls(data["calls"], period)
        deals = _filter_deals(all_deals_raw, period)
        deals_by_rep = _group_deals_by_rep(deals)
        print(f"      deals: {len(deals)} ({len(deals_by_rep)} reps)")

        closed_count = sum(1 for t in trajs if t.get(_TC["outcome"]) in ("won", "lost"))
        print(f"      data: {closed_count} closed trajectories, {len(pae)} pae_audits, {len(pbd)} pbd_audits, {len(calls)} calls")

        # Segment A — Closing Effectiveness (period-filtered closed deals)
        print(f"    [{period}] A. Closing Effectiveness...")
        all_patterns.extend(_inject_period(_compute_segment_a(trajs), period))

        # Segment B — Pipeline Health (ALWAYS current snapshot, no period filter)
        # Only compute once (on the weekly pass) to avoid triplicating identical data
        if period == "weekly":
            print(f"    [{period}] B. Pipeline Health (live snapshot)...")
            all_patterns.extend(_inject_period(_compute_segment_b(all_trajectories), period))

        # Segment C — Process Quality (period-filtered audits)
        print(f"    [{period}] C. Process Quality...")
        all_patterns.extend(_inject_period(_compute_segment_c(pae, pbd), period))

        # Segment D — Coaching & Gaps (period-filtered audits)
        print(f"    [{period}] D. Coaching & Gaps...")
        all_patterns.extend(_inject_period(_compute_segment_d(pae, pbd), period))

        # Segment E — Activity & Cadence (period-filtered calls)
        print(f"    [{period}] E. Activity & Cadence...")
        all_patterns.extend(_inject_period(_compute_segment_e(calls, trajs), period))

        # Segment F — Demo Funnel (period-filtered deals)
        print(f"    [{period}] F. Demo Funnel...")
        all_patterns.extend(_inject_period(_compute_segment_f(deals_by_rep), period))

        # Segment G — Contact & Multi-threading (period-filtered deals)
        print(f"    [{period}] G. Contact & Multi-threading...")
        all_patterns.extend(_inject_period(_compute_segment_g(deals_by_rep), period))

        # Segment H — Segment Performance (period-filtered deals)
        print(f"    [{period}] H. Segment Performance...")
        all_patterns.extend(_inject_period(_compute_segment_h(deals_by_rep), period))

        # Segment J — Forecast Accuracy (deferred, was F)
        all_patterns.extend(_inject_period(_compute_segment_j(), period))

        # Segment K — Post-mortem (quarterly only, deferred, was G)
        # if period == "quarterly":
        #     all_patterns.extend(_inject_period(_compute_segment_k(), period))

        # Segment L — Product Knowledge (deferred, was H)
        all_patterns.extend(_inject_period(_compute_segment_l(), period))

    # Upsert all
    upserted = 0
    for p in all_patterns:
        try:
            _upsert_rep_pattern(p, today)
            upserted += 1
        except Exception as e:
            print(f"    ! upsert failed ({p.get('pattern_key')}): {e}")

    print(f"\n    {upserted}/{len(all_patterns)} rep patterns upserted (across {len(PERIODS)} periods)")
    return upserted


# ═══════════════════════════════════════════════════════════════════════════
# SEGMENT I — COACHING ALERTS
#
# Runs as a separate pass after team_stats.py.
# Compares each rep's stats against team benchmarks to generate alerts.
# ═══════════════════════════════════════════════════════════════════════════

_ALERT_RULES = [
    # (slug, stat_key, comparison, threshold, severity, template)
    # comparison: "lt_team_p25" = rep < team P25, "gt_team_p75" = rep > team P75
    # "gt_abs" = rep > absolute threshold, "lt_abs" = rep < absolute threshold
    # "decline_pp" = dropped >N pp vs prior history
    ("wr_below_team", "win_rate", "lt_team_p25", None, 3,
     "Win rate {val}% is below team P25 of {team_val}%"),
    ("wr_declining", "win_rate", "decline_pp", 10, 3,
     "Win rate dropped {delta}pp vs prior period ({prev}% → {val}%)"),
    ("post_demo_wr_weak", "post_demo_win_rate", "lt_team_p25", None, 3,
     "Post-demo WR {val}% is below team P25 of {team_val}%"),
    ("low_multi_thread_demo", "multi_thread_demo_rate", "lt_abs", 20, 2,
     "Multi-thread rate on demo deals is {val}% (below 20% threshold)"),
    ("slow_to_demo", "avg_days_to_demo", "gt_team_p75", None, 2,
     "Avg {val}d to demo — above team P75 of {team_val}d"),
    ("stale_pipeline", "stale_deals", "gt_abs", 50, 2,
     "Stale pipeline: {val}% of deals are stale (above 50%)"),
    ("cycle_waste", "cycle_waste_ratio", "gt_abs", 1.5, 2,
     "Cycle waste ratio {val}x — lost deals take {val}x longer than won"),
    ("size_mismatch", "wr_by_employee_size", "size_mismatch", None, 1,
     "WR below 5% in {bucket} segment ({bucket_wr}%, {bucket_n} deals)"),
    ("meddic_weakness", "avg_meddic_per_pillar", "lt_team_p25", None, 1,
     "MEDDIC avg {val} is below team P25 of {team_val}"),
]


def run_alerts() -> int:
    """Generate coaching alerts by comparing rep stats vs team benchmarks."""
    today = date.today().isoformat()
    print("\n  COACHING ALERTS: generating alerts...")

    # Load orgchart
    org_resp = supabase.table("orgchart").select("email, team_name, is_active").eq("is_active", True).execute()
    email_to_team = {r["email"]: r["team_name"] for r in (org_resp.data or [])}

    # Load all rep_stat and team_stat patterns
    all_patterns_data = []
    for ptype in ("rep_stat", "team_stat"):
        offset = 0
        while True:
            resp = (
                supabase.table(_TBL_PATTERNS)
                .select("pattern_key, pattern_type, value, scope, history, pattern, sample_size")
                .eq("pattern_type", ptype)
                .range(offset, offset + 999)
                .execute()
            )
            batch = resp.data or []
            all_patterns_data.extend(batch)
            if len(batch) < 1000:
                break
            offset += 1000

    # Index rep stats by (period, email, stat_key)
    rep_index: dict[tuple, dict] = {}
    for r in all_patterns_data:
        if r["pattern_type"] != "rep_stat":
            continue
        pk = r.get("pattern_key") or ""
        scope = r.get("scope") or ""
        email = scope[4:] if scope.startswith("rep:") else ""
        if not email:
            continue
        for period in PERIODS:
            prefix = f"rep_{period}_"
            if pk.startswith(prefix):
                slug = _email_slug(email)
                after = pk[len(prefix):]
                if after.endswith("_" + slug):
                    stat_key = after[:-(len(slug) + 1)]
                    rep_index[(period, email, stat_key)] = r
                break

    # Index team stats by (period, team, stat_key, aggregate)
    team_index: dict[tuple, float] = {}
    for r in all_patterns_data:
        if r["pattern_type"] != "team_stat":
            continue
        pk = r.get("pattern_key") or ""
        scope = r.get("scope") or ""
        team = scope[5:] if scope.startswith("team:") else ""
        if not team or r.get("value") is None:
            continue
        for period in PERIODS:
            prefix = f"team_{period}_"
            if pk.startswith(prefix):
                after = pk[len(prefix):]
                # Pattern: {stat_key}_{aggregate}_{team_slug}
                # We need to find the aggregate (avg/median/p25/p75)
                for agg in ("avg", "median", "p25", "p75"):
                    marker = f"_{agg}_"
                    idx = after.rfind(marker)
                    if idx >= 0:
                        stat_key = after[:idx]
                        team_index[(period, team, stat_key, agg)] = float(r["value"])
                        break
                break

    # Generate alerts
    alert_patterns = []

    for period in PERIODS:
        for email, team in email_to_team.items():
            slug = _email_slug(email)
            scope = f"rep:{email}"

            for rule in _ALERT_RULES:
                alert_slug, stat_key, comparison, threshold, severity, template = rule

                if comparison == "size_mismatch":
                    # Special case: parse wr_by_employee_size pattern text
                    r = rep_index.get((period, email, stat_key))
                    if not r or not r.get("pattern"):
                        continue
                    import re as _re
                    for match in _re.finditer(r"(\w+):\s*(\d+)%\s*\((\d+)d\)", r.get("pattern", "")):
                        bucket, wr_str, n_str = match.group(1), match.group(2), match.group(3)
                        wr_val, n_val = int(wr_str), int(n_str)
                        if wr_val < 5 and n_val >= 10:
                            alert_patterns.append({
                                "pattern_key": f"rep_{period}_alert_{alert_slug}_{bucket.lower()}_{slug}",
                                "pattern_type": "rep_stat",
                                "scope": scope,
                                "pattern": template.format(bucket=bucket, bucket_wr=wr_val, bucket_n=n_val),
                                "confidence": 0.70,
                                "sample_size": n_val,
                                "value": severity,
                            })
                    continue

                r = rep_index.get((period, email, stat_key))
                if not r or r.get("value") is None:
                    continue
                val = float(r["value"])

                fired = False
                fmt_kwargs = {"val": round(val, 1)}

                if comparison == "lt_team_p25":
                    team_val = team_index.get((period, team, stat_key, "p25"))
                    if team_val is not None and val < team_val:
                        fired = True
                        fmt_kwargs["team_val"] = round(team_val, 1)
                elif comparison == "gt_team_p75":
                    team_val = team_index.get((period, team, stat_key, "p75"))
                    if team_val is not None and val > team_val:
                        fired = True
                        fmt_kwargs["team_val"] = round(team_val, 1)
                elif comparison == "lt_abs":
                    if val < threshold:
                        fired = True
                elif comparison == "gt_abs":
                    if val > threshold:
                        fired = True
                elif comparison == "decline_pp":
                    history = _parse_json(r.get("history") or [])
                    if isinstance(history, list) and history:
                        prev_val = history[-1].get("value")
                        if prev_val is not None:
                            delta = val - float(prev_val)
                            if delta < -threshold:
                                fired = True
                                fmt_kwargs["delta"] = round(abs(delta), 1)
                                fmt_kwargs["prev"] = round(float(prev_val), 1)

                if fired:
                    alert_patterns.append({
                        "pattern_key": f"rep_{period}_alert_{alert_slug}_{slug}",
                        "pattern_type": "rep_stat",
                        "scope": scope,
                        "pattern": template.format(**fmt_kwargs),
                        "confidence": 0.80,
                        "sample_size": r.get("sample_size") or 0,
                        "value": severity,
                    })

        print(f"    [{period}] {sum(1 for p in alert_patterns if p['pattern_key'].startswith(f'rep_{period}_'))} alerts")

    # Upsert alerts
    upserted = 0
    for p in alert_patterns:
        try:
            _upsert_rep_pattern(p, today)
            upserted += 1
        except Exception as e:
            print(f"    ! alert upsert failed ({p.get('pattern_key')}): {e}")

    print(f"\n    {upserted}/{len(alert_patterns)} alerts upserted")
    return upserted
