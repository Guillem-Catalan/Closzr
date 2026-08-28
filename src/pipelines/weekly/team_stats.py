"""
Weekly Team Stats — team-level aggregated performance patterns.

Runs inside weekly/run2.py after rep_stats. Pure Python.
Aggregates rep-level data by team using org.py ORGCHART.

Each stat becomes a learned_pattern with:
  - pattern_key: team_{stat}_{team_slug}
  - scope: "team:{team_slug}"
  - history JSONB accumulates weekly executions

Uses the same 8 segments as rep_stats but aggregated:
  A. Closing Effectiveness  — team win rate, cycle times, loss patterns
  B. Pipeline Health         — team pipeline value, stale deals, momentum
  C. Process Quality         — team avg MEDDIC/BANT, weakest pillars
  D. Coaching & Gaps         — common team-wide gaps, recurring issues
  E. Activity & Cadence      — team calls/week, cadence benchmarks
  F. Forecast Accuracy       — team forecast accuracy, calibration
  G. Post-mortem Patterns    — team-wide what_worked/what_failed (quarterly)
  H. Product Knowledge       — team product coverage, missed products

Plus cross-rep comparisons:
  - Ranking within team per stat
  - Percentile distribution
  - Deviation from team mean
  - Best/worst performer per stat
  - Team trend (improving/declining week over week)
"""

import json
import traceback
from datetime import date
from collections import defaultdict

from src import schema, org
from src.db.client import supabase


# ═══════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════

_TBL_PATTERNS = schema.tbl("patterns")


def _team_slug(team_name: str) -> str:
    """TIM -> tim, Direct Sales -> direct_sales"""
    return team_name.lower().replace(" ", "_")


def _parse_json(val):
    if isinstance(val, str):
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return val
    return val


# ═══════════════════════════════════════════════════════════════════════════
# TEAM RESOLUTION — maps emails to teams via org.py
# ═══════════════════════════════════════════════════════════════════════════

def _build_email_to_team() -> dict[str, str]:
    """Build email -> team_name mapping from org.py ORGCHART structures."""
    mapping = {}

    for team_name, team_cfg in org.PARTNERS_ORGCHART.items():
        for email in team_cfg.get("pbd", set()):
            mapping[email] = team_name
        for email in team_cfg.get("pae", set()):
            mapping[email] = team_name
        leadership = team_cfg.get("leadership", {})
        for role_cfg in leadership.values():
            if isinstance(role_cfg, dict) and "email" in role_cfg:
                mapping[role_cfg["email"]] = team_name

    if hasattr(org, "DIRECT_SALES"):
        for team_name, team_cfg in org.DIRECT_SALES.items():
            for email in team_cfg.get("ae", set()):
                mapping[email] = team_name

    if hasattr(org, "XL_SALES"):
        for team_name, team_cfg in org.XL_SALES.items():
            for email in team_cfg.get("ae", set()):
                mapping[email] = team_name

    return mapping


# ═══════════════════════════════════════════════════════════════════════════
# DATA LOADING — reads rep patterns from learned_patterns
# ═══════════════════════════════════════════════════════════════════════════

def _fetch_rep_patterns() -> list[dict]:
    """Load all rep_stat patterns to aggregate by team."""
    results = []
    offset = 0
    while True:
        resp = (
            supabase.table(_TBL_PATTERNS)
            .select("pattern_key, pattern_type, scope, pattern, confidence, sample_size, value")
            .eq("pattern_type", "rep_stat")
            .range(offset, offset + 999)
            .execute()
        )
        batch = resp.data or []
        results.extend(batch)
        if len(batch) < 1000:
            break
        offset += 1000
    return results


# ═══════════════════════════════════════════════════════════════════════════
# UPSERT
# ═══════════════════════════════════════════════════════════════════════════

def _upsert_team_pattern(pattern: dict, today: str):
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
        "pattern_type": pattern.get("pattern_type", "team_stat"),
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
# TEAM AGGREGATION — same 8 segments as rep_stats, aggregated
#
# Two approaches depending on segment:
#   1. Aggregate FROM rep patterns (read learned_patterns where type=rep_stat)
#   2. Compute directly from raw data grouped by team
#
# Approach 1 is simpler and avoids re-reading all tables.
# Approach 2 is needed for stats that don't aggregate cleanly (distributions).
# ═══════════════════════════════════════════════════════════════════════════

def _compute_team_aggregates(rep_patterns: list[dict], email_to_team: dict) -> list[dict]:
    """Aggregate rep patterns into team-level patterns.

    Groups rep patterns by team, computes:
      - team avg/median for each stat
      - best/worst performer
      - distribution (percentiles)
      - team trend from history
    """
    # TODO: implement
    return []


def _compute_cross_rep_rankings(rep_patterns: list[dict], email_to_team: dict) -> list[dict]:
    """Rank reps within their team for each stat.

    Generates patterns like:
      - team_{team}_ranking_{stat}: ordered list of reps by performance
      - team_{team}_spread_{stat}: how much variance within the team
    """
    # TODO: implement
    return []


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def run() -> int:
    print("\n  TEAM STATS: computing team-level patterns...")
    today = date.today().isoformat()

    email_to_team = _build_email_to_team()
    print(f"    {len(email_to_team)} emails mapped to teams")

    rep_patterns = _fetch_rep_patterns()
    if not rep_patterns:
        print("    No rep patterns found — skipping team stats")
        return 0
    print(f"    {len(rep_patterns)} rep patterns loaded")

    all_patterns = []

    # Team aggregates
    print("    Computing team aggregates...")
    all_patterns.extend(_compute_team_aggregates(rep_patterns, email_to_team))

    # Cross-rep rankings
    print("    Computing cross-rep rankings...")
    all_patterns.extend(_compute_cross_rep_rankings(rep_patterns, email_to_team))

    # Upsert all
    upserted = 0
    for p in all_patterns:
        try:
            _upsert_team_pattern(p, today)
            upserted += 1
        except Exception as e:
            print(f"    ! upsert failed ({p.get('pattern_key')}): {e}")

    print(f"    {upserted}/{len(all_patterns)} team patterns upserted")
    return upserted
