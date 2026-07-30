"""
Weekly Team Stats — per-team benchmark aggregates.

Runs inside weekly/run2.py AFTER rep_stats. Reads rep_stat patterns
from learned_patterns, maps reps to teams via orgchart, and computes
team-level aggregates (mean, median, P25, P75) for every numeric metric.

Pattern key format: team_{period}_{stat}_{aggregate}_{team_slug}
Scope: "team:{team_name}"
History JSONB accumulates weekly (max 52 entries).
"""

import json
import re
import traceback
import unicodedata
from collections import defaultdict
from statistics import mean, median

from src import schema
from src.db.client import supabase


_TBL_PATTERNS = schema.tbl("patterns")

PERIODS = ("weekly", "monthly", "quarterly")

SKIP_STAT_PREFIXES = ("alert_",)


def _team_slug(name: str) -> str:
    """Normalize team name to slug: 'DS Rubén' -> 'ds_ruben'"""
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_str = nfkd.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "_", ascii_str.lower()).strip("_")


def _percentile(values: list[float], p: float) -> float:
    """Simple percentile (nearest-rank)."""
    if not values:
        return 0.0
    s = sorted(values)
    k = max(0, min(len(s) - 1, int(len(s) * p / 100)))
    return s[k]


def _parse_json(val):
    if isinstance(val, str):
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return val
    return val


def _upsert_team_pattern(pattern: dict, today: str):
    """Upsert a team_stat pattern — same logic as rep_stats._upsert_rep_pattern."""
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
        "pattern_type": "team_stat",
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


def run() -> int:
    """Compute team-level aggregates from rep stats + orgchart."""
    from datetime import date
    today = date.today().isoformat()

    print("\n  TEAM STATS: computing team benchmarks...")

    # 1. Load orgchart (active reps only)
    org_resp = (
        supabase.table("orgchart")
        .select("email, team_name, is_active")
        .eq("is_active", True)
        .execute()
    )
    org_rows = org_resp.data or []
    email_to_team: dict[str, str] = {r["email"]: r["team_name"] for r in org_rows}
    print(f"    orgchart: {len(email_to_team)} active reps")

    # 2. Load all rep_stat patterns
    all_rep_stats = []
    offset = 0
    while True:
        resp = (
            supabase.table(_TBL_PATTERNS)
            .select("pattern_key, value, scope, sample_size, confidence")
            .eq("pattern_type", "rep_stat")
            .range(offset, offset + 999)
            .execute()
        )
        batch = resp.data or []
        all_rep_stats.extend(batch)
        if len(batch) < 1000:
            break
        offset += 1000
    print(f"    rep_stat patterns: {len(all_rep_stats)}")

    # 3. Group by period, extract stat key, map to team
    all_patterns = []

    for period in PERIODS:
        prefix = f"rep_{period}_"
        period_stats = [r for r in all_rep_stats if (r.get("pattern_key") or "").startswith(prefix)]

        # Extract (stat_key, email, value) triples
        by_stat_by_team: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))

        for r in period_stats:
            if r.get("value") is None:
                continue

            scope = r.get("scope") or ""
            email = scope[4:] if scope.startswith("rep:") else ""
            if not email or email not in email_to_team:
                continue

            pk = r["pattern_key"]
            after_prefix = pk[len(prefix):]

            # The stat key is everything before the email slug
            # Email slug is email with @ and . replaced by _
            email_slug = email.replace("@", "_").replace(".", "_")
            if after_prefix.endswith("_" + email_slug):
                stat_key = after_prefix[:-(len(email_slug) + 1)]
            else:
                continue

            if any(stat_key.startswith(skip) for skip in SKIP_STAT_PREFIXES):
                continue

            team = email_to_team[email]
            by_stat_by_team[stat_key][team].append(float(r["value"]))

        # 4. Compute aggregates per stat per team
        for stat_key, teams in by_stat_by_team.items():
            for team_name, values in teams.items():
                if len(values) < 2:
                    continue

                t_slug = _team_slug(team_name)
                scope = f"team:{team_name}"

                aggregates = {
                    "avg": round(mean(values), 1),
                    "median": round(median(values), 1),
                    "p25": round(_percentile(values, 25), 1),
                    "p75": round(_percentile(values, 75), 1),
                }

                for agg_name, agg_value in aggregates.items():
                    all_patterns.append({
                        "pattern_key": f"team_{period}_{stat_key}_{agg_name}_{t_slug}",
                        "pattern_type": "team_stat",
                        "scope": scope,
                        "pattern": f"Team {team_name} {stat_key} {agg_name}: {agg_value} (n={len(values)})",
                        "confidence": min(0.90, len(values) / 5),
                        "sample_size": len(values),
                        "value": agg_value,
                    })

        print(f"    [{period}] {len([p for p in all_patterns if p['pattern_key'].startswith(f'team_{period}_')])} team patterns")

    # 5. Upsert all
    upserted = 0
    for p in all_patterns:
        try:
            _upsert_team_pattern(p, today)
            upserted += 1
        except Exception as e:
            print(f"    ! upsert failed ({p.get('pattern_key')}): {e}")

    print(f"\n    {upserted}/{len(all_patterns)} team patterns upserted")
    return upserted
