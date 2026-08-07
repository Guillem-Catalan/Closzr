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
from datetime import date
from statistics import mean, median
from uuid import uuid4

from src import schema
from src.db.client import supabase
from src.pipelines.weekly.period_window import period_window, PERIOD_TYPES


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


def _compute_pooled_metrics(rep_rows: list[dict]) -> dict:
    """Compute pooled (weighted) team metrics from rep_summary rows.

    Pooled = total won / total closed, weighting reps by deal volume.
    """
    total_won = sum(r.get("deals_won_count") or 0 for r in rep_rows)
    total_lost = sum(r.get("deals_lost_count") or 0 for r in rep_rows)
    total_closed = total_won + total_lost

    # Pooled win rate
    win_rate_pooled = round(total_won / total_closed * 100, 1) if total_closed > 0 else None

    # Pooled avg cycle won: weighted mean across all won deals
    # Approximate by weighting each rep's avg by their won count
    cycle_sum = 0
    cycle_n = 0
    for r in rep_rows:
        avg_c = r.get("avg_cycle_won")
        n = r.get("deals_won_count") or 0
        if avg_c is not None and n > 0:
            cycle_sum += float(avg_c) * n
            cycle_n += n
    avg_cycle_won_pooled = round(cycle_sum / cycle_n, 1) if cycle_n > 0 else None

    # Pooled avg deal size won
    size_sum = 0
    size_n = 0
    for r in rep_rows:
        avg_s = r.get("avg_deal_size_won")
        n = r.get("deals_won_count") or 0
        if avg_s is not None and n > 0:
            size_sum += float(avg_s) * n
            size_n += n
    avg_deal_size_won_pooled = round(size_sum / size_n, 1) if size_n > 0 else None

    # Pipeline value (weekly only — sum)
    pipeline_values = [float(r["pipeline_value"]) for r in rep_rows if r.get("pipeline_value") is not None]
    total_pipeline = round(sum(pipeline_values), 2) if pipeline_values else None

    return {
        "win_rate_pooled": win_rate_pooled,
        "avg_cycle_won_pooled": avg_cycle_won_pooled,
        "avg_deal_size_won_pooled": avg_deal_size_won_pooled,
        "total_deals_closed": total_closed,
        "total_deals_won": total_won,
        "total_deals_lost": total_lost,
        "total_pipeline_value": total_pipeline,
    }


def _compute_distribution_metrics(rep_rows: list[dict]) -> dict:
    """Compute unweighted distribution metrics (each rep counts equally)."""

    def _dist(field: str) -> dict:
        vals = [float(r[field]) for r in rep_rows if r.get(field) is not None]
        if len(vals) < 2:
            return {}
        return {
            f"{field}_avg": round(mean(vals), 1),
            f"{field}_median": round(median(vals), 1),
            f"{field}_p25": round(_percentile(vals, 25), 1),
            f"{field}_p75": round(_percentile(vals, 75), 1),
        }

    result = {}

    # Win rate distribution
    wr = _dist("win_rate")
    result["win_rate_avg"] = wr.get("win_rate_avg")
    result["win_rate_median"] = wr.get("win_rate_median")
    result["win_rate_p25"] = wr.get("win_rate_p25")
    result["win_rate_p75"] = wr.get("win_rate_p75")

    # Cycle won distribution
    cyc = _dist("avg_cycle_won")
    result["avg_cycle_won_avg"] = cyc.get("avg_cycle_won_avg")
    result["avg_cycle_won_median"] = cyc.get("avg_cycle_won_median")

    # Calls per week distribution
    cpw = _dist("calls_per_week")
    result["calls_per_week_avg"] = cpw.get("calls_per_week_avg")
    result["calls_per_week_median"] = cpw.get("calls_per_week_median")

    # MEDDIC average (sum of pillar values per rep)
    meddic_totals = []
    for r in rep_rows:
        meddic = r.get("avg_meddic_per_pillar")
        if meddic and isinstance(meddic, dict):
            total = sum(float(v) for v in meddic.values() if v is not None)
            meddic_totals.append(total)
    if len(meddic_totals) >= 2:
        result["avg_meddic_avg"] = round(mean(meddic_totals), 1)
        result["avg_meddic_p25"] = round(_percentile(meddic_totals, 25), 1)
        result["avg_meddic_p75"] = round(_percentile(meddic_totals, 75), 1)
    elif rep_rows:
        # JSONB columns (incl. avg_meddic_per_pillar) not yet populated in
        # rep_summary during dual-write phase — MEDDIC distributions will be
        # empty until Phase 4 adds structured data extraction.
        print("      MEDDIC distribution skipped — avg_meddic_per_pillar not populated in rep_summary yet")

    # Simple averages for other metrics
    for field in ("demo_rate", "post_demo_win_rate", "multi_thread_rate"):
        vals = [float(r[field]) for r in rep_rows if r.get(field) is not None]
        if vals:
            result[f"{field}_avg"] = round(mean(vals), 1)

    return result


def _load_team_targets(
    team_reps: dict[str, list[str]],
    period_type: str,
    period_start: date,
    period_end: date,
    email_to_name: dict[str, str],
) -> dict[str, dict]:
    """Load targets from ae_targets and compute team consecution.

    Returns {team_name: {team_target, mrr_closed_month, consecution_pct,
                         reps_with_target, reps_without_target}}
    Only for monthly period_type.
    """
    if period_type != "monthly":
        return {}

    month_str = period_start.strftime("%Y-%m-01")
    try:
        targets_resp = supabase.table("ae_targets").select(
            "email, target"
        ).eq("month", month_str).execute()
    except Exception:
        print("    ! ae_targets not found — skipping team targets")
        return {}

    target_by_email = {r["email"]: float(r["target"]) for r in (targets_resp.data or []) if r.get("target")}

    result = {}
    for team, emails in team_reps.items():
        with_target = [e for e in emails if e in target_by_email]
        without_target = [e for e in emails if e not in target_by_email]
        team_target = sum(target_by_email[e] for e in with_target) if with_target else None

        # Compute MRR won by this team in the period
        mrr_won = 0
        for email in emails:
            # deals.pae is a NAME field — reverse-lookup the rep's name
            rep_name = email_to_name.get(email)
            if not rep_name:
                continue
            try:
                deals_resp = supabase.table("deals").select(
                    "amount"
                ).eq("pae", rep_name).eq("is_closed_won", True).gte(
                    "close_date", period_start.isoformat()
                ).lt("close_date", period_end.isoformat()).execute()
                mrr_won += sum(float(d.get("amount") or 0) for d in (deals_resp.data or []))
            except Exception:
                pass

        consecution = round(mrr_won / team_target * 100, 1) if team_target and team_target > 0 else None

        result[team] = {
            "team_target": team_target,
            "mrr_closed_month": round(mrr_won, 2),
            "consecution_pct": consecution,
            "reps_with_target": len(with_target),
            "reps_without_target": len(without_target),
        }

    return result


def run(run_id: str | None = None, period_type: str | None = None) -> int:
    """Compute team-level aggregates from rep stats + orgchart."""
    today = date.today().isoformat()

    if run_id is None:
        run_id = str(uuid4())

    print("\n  TEAM STATS: computing team benchmarks...")

    # 1. Load orgchart (active reps only)
    org_resp = (
        supabase.table("orgchart")
        .select("email, full_name, team_name, is_active, role, reports_to")
        .eq("is_active", True)
        .execute()
    )
    org_rows = org_resp.data or []
    email_to_team: dict[str, str] = {r["email"]: r["team_name"] for r in org_rows}
    name_to_email: dict[str, str] = {}
    for row in org_rows:
        name = (row.get("full_name") or "").strip()
        if name and row.get("email"):
            name_to_email[name] = row["email"]
    # Reverse map for deals.pae lookup (name field, not email)
    email_to_name: dict[str, str] = {v: k for k, v in name_to_email.items()}
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
            if scope.startswith("rep:") and "@" in scope:
                email = scope[4:]
                slug = email.replace("@", "_").replace(".", "_")
            elif scope.startswith("rep:") or scope.startswith("rep_name:"):
                rep_name = scope.split(":", 1)[1]
                email = name_to_email.get(rep_name, "")
                slug = rep_name.replace("@", "_").replace(".", "_")
            else:
                continue
            if not email or email not in email_to_team:
                continue

            pk = r["pattern_key"]
            after_prefix = pk[len(prefix):]

            if after_prefix.endswith("_" + slug):
                stat_key = after_prefix[:-(len(slug) + 1)]
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

    # ── Dual-write: team_summary ──
    print("\n  TEAM SUMMARY: dual-writing to team_summary table...")
    summary_count = 0

    # Build team → rep emails map
    team_reps: dict[str, list[str]] = defaultdict(list)
    for email, team in email_to_team.items():
        team_reps[team].append(email)

    # Build team → tl_email and tl_name maps from orgchart hierarchy
    tl_map: dict[str, str] = {}
    tl_name_map: dict[str, str] = {}
    email_to_fullname: dict[str, str] = {
        r["email"]: r.get("full_name", "")
        for r in org_rows if r.get("email")
    }
    for r in org_rows:
        team = r.get("team_name")
        role = (r.get("role") or "").lower()
        email = r.get("email", "")
        # TL roles identify team leads
        if team and role in ("tl", "pae_tl", "pbd_tl"):
            tl_map[team] = email
            tl_name_map[team] = r.get("full_name") or ""
    # Fallback: for teams without an explicit TL, use reports_to of first rep
    for r in org_rows:
        team = r.get("team_name")
        if team and team not in tl_map and r.get("reports_to"):
            tl_map[team] = r["reports_to"]
            tl_name_map[team] = email_to_fullname.get(r["reports_to"], "")

    for period in (PERIOD_TYPES if not period_type else [period_type]):
        p_start, p_end = period_window(period, date.today())

        # Load rep_summary rows for this run + period
        rep_rows_resp = supabase.table("rep_summary").select("*").eq(
            "run_id", run_id
        ).eq("period_type", period).execute()
        rep_rows = rep_rows_resp.data or []

        if not rep_rows:
            print(f"    [{period}] No rep_summary rows for run_id={run_id[:8]}... — skipping")
            continue

        # Group by team
        reps_by_team: dict[str, list[dict]] = defaultdict(list)
        for r in rep_rows:
            team = r.get("team")
            if team:
                reps_by_team[team].append(r)

        # Load targets for monthly
        targets = _load_team_targets(team_reps, period, p_start, p_end, email_to_name)

        for team, team_rep_rows in reps_by_team.items():
            pooled = _compute_pooled_metrics(team_rep_rows)
            distribution = _compute_distribution_metrics(team_rep_rows)
            target_data = targets.get(team, {})

            row = {
                "run_id": run_id,
                "team": team,
                "tl_email": tl_map.get(team, ""),
                "tl_name": tl_name_map.get(team),
                "rep_count": len(team_rep_rows),
                "period_type": period,
                "period_start": p_start.isoformat(),
                "period_end": p_end.isoformat(),
                **pooled,
                **distribution,
                **target_data,
            }
            row = {k: v for k, v in row.items() if v is not None}

            try:
                supabase.table("team_summary").upsert(
                    row, on_conflict="team,period_type,period_start"
                ).execute()
                summary_count += 1
            except Exception as e:
                print(f"    ! team_summary upsert failed ({team}, {period}): {e}")

        print(f"    [{period}] {len(reps_by_team)} teams upserted")

    print(f"    {summary_count} team_summary rows upserted total")
    return upserted
