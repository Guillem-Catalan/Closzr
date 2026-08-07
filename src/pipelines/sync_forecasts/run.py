"""
Sync Forecasts — HubSpot forecast submissions → Supabase.

Reads HubSpot forecast objects (rep + team submissions) and upserts them
into forecast_submissions / forecast_submissions_history tables.

Flow:
  1. Load owner map from orgchart  (hs_owner_id → email, team_name)
  2. Build team-ID map via majority-vote + dedup  (hs_team_id → closzr_team)
  3. For each (month, pipeline), fetch HubSpot forecasts and parse into rows
  4. Clean stale team submissions, upsert to forecast_submissions,
     append to forecast_submissions_history

Zero Claude calls. Pure HubSpot → Supabase sync.
"""

from __future__ import annotations

import os
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta

import requests
from supabase import create_client, Client

# ── Constants ────────────────────────────────────────────────────────────────

BATCH_SIZE = 500
PIPELINES = ["default", "11834984"]

HS_FORECAST_PROPERTIES = [
    "hs_amount",
    "hubspot_owner_id",
    "hubspot_team_id",
    "hs_team_id",
    "hs_forecast_month",
    "hs_year",
    "hs_deal_pipeline_id",
    "hs_submission_notes",
    "hs_lastmodifieddate",
    "hs_milestone",
    "hs_forecast_type",
]

HS_BASE_URL = "https://api.hubapi.com"


# ── Clients ──────────────────────────────────────────────────────────────────

def _supabase() -> Client:
    """Create a Supabase client from env vars."""
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_KEY") or os.environ.get("CLAUDIO_SUPABASE_ANON_KEY", "")
    if not url or not key:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_KEY / CLAUDIO_SUPABASE_ANON_KEY")
    return create_client(url, key)


def _hs_headers() -> dict:
    """Return HubSpot API headers."""
    token = os.environ.get("HUBSPOT_TOKEN", "")
    if not token:
        raise RuntimeError("Missing HUBSPOT_TOKEN")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


# ── Owner / Team map ────────────────────────────────────────────────────────

def _load_owner_map(sb: Client) -> tuple[dict, dict]:
    """
    Build two maps:
      owner_map:   {hs_owner_id: (email, team_name)}
      team_id_map: {hs_team_id: closzr_team}

    Steps:
      1. Query orgchart for active members with hs_owner_id
      2. Fetch all HubSpot owners (paginated)
      3. Majority-vote: for each HubSpot team ID, count which Closzr team
         its members belong to
      4. Dedup: for each Closzr team, keep only the HubSpot team ID with
         the highest vote count
    """
    # 1. Orgchart → owner_map + email_to_team
    rows = (
        sb.table("orgchart")
        .select("email,hs_owner_id,team_name")
        .eq("is_active", True)
        .not_.is_("hs_owner_id", "null")
        .execute()
        .data or []
    )

    owner_map: dict[str, tuple[str, str]] = {}
    email_to_team: dict[str, str] = {}

    for r in rows:
        oid = r.get("hs_owner_id")
        email = r.get("email")
        if not oid or not email:
            continue
        team = r.get("team_name", "")
        owner_map[str(oid)] = (email, team)
        email_to_team[email.lower()] = team

    print(f"  orgchart: {len(owner_map)} owners with hs_owner_id")

    # 2. Fetch all HubSpot owners (paginated)
    headers = _hs_headers()
    hs_owners: list[dict] = []
    after: str | None = None

    while True:
        params: dict = {"limit": 500}
        if after:
            params["after"] = after
        resp = requests.get(
            f"{HS_BASE_URL}/crm/v3/owners",
            headers=headers,
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        hs_owners.extend(data.get("results", []))
        paging = data.get("paging", {}).get("next", {})
        after = paging.get("after")
        if not after:
            break

    print(f"  hubspot owners: {len(hs_owners)} total")

    # 3. Majority-vote: hs_team_id → closzr_team
    team_votes: dict[str, Counter] = defaultdict(Counter)

    for owner in hs_owners:
        email = (owner.get("email") or "").lower()
        closzr_team = email_to_team.get(email)
        if not closzr_team:
            continue

        # An owner can have multiple team memberships in HubSpot
        teams = owner.get("teams", [])
        for t in teams:
            tid = str(t.get("id", ""))
            if tid:
                team_votes[tid][closzr_team] += 1

    # 4. Dedup: for each Closzr team, keep only the HS team ID with highest votes
    # First, get the winning Closzr team for each HS team ID
    hs_to_closzr: dict[str, tuple[str, int]] = {}
    for tid, votes in team_votes.items():
        winner, count = votes.most_common(1)[0]
        hs_to_closzr[tid] = (winner, count)

    # Then, for each Closzr team, keep only the HS team ID with the most votes
    closzr_best: dict[str, tuple[str, int]] = {}  # closzr_team → (hs_team_id, count)
    for tid, (closzr_team, count) in hs_to_closzr.items():
        if closzr_team not in closzr_best or count > closzr_best[closzr_team][1]:
            closzr_best[closzr_team] = (tid, count)

    # Build final 1:1 map
    team_id_map: dict[str, str] = {}
    for closzr_team, (tid, _count) in closzr_best.items():
        team_id_map[tid] = closzr_team

    print(f"  team map: {len(team_votes)} raw HS team IDs → {len(team_id_map)} clean 1:1 mappings")

    return owner_map, team_id_map


# ── HubSpot forecast fetch ──────────────────────────────────────────────────

def _fetch_forecasts(year: int, month: int, pipeline_id: str) -> list[dict]:
    """Fetch all forecast objects for a given year/month/pipeline via search API."""
    headers = _hs_headers()
    url = f"{HS_BASE_URL}/crm/v3/objects/forecasts/search"

    filters = [
        {"propertyName": "hs_year", "operator": "EQ", "value": str(year)},
        {"propertyName": "hs_forecast_month", "operator": "EQ", "value": str(month)},
        {"propertyName": "hs_deal_pipeline_id", "operator": "EQ", "value": pipeline_id},
        {"propertyName": "hs_milestone", "operator": "EQ", "value": "monthly"},
    ]

    results: list[dict] = []
    after: str | None = None

    while True:
        body: dict = {
            "filterGroups": [{"filters": filters}],
            "properties": HS_FORECAST_PROPERTIES,
            "limit": 100,
        }
        if after:
            body["after"] = after

        resp = requests.post(url, headers=headers, json=body, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        results.extend(data.get("results", []))

        paging = data.get("paging", {}).get("next", {})
        after = paging.get("after")
        if not after:
            break

    return results


# ── Parse forecast records into rows ─────────────────────────────────────────

def _parse_submissions(
    forecasts: list[dict],
    owner_map: dict[str, tuple[str, str]],
    team_id_map: dict[str, str],
    month_str: str,
    pipeline_id: str,
) -> list[dict]:
    """Convert HubSpot forecast records into upsert-ready rows."""
    now_iso = datetime.now(timezone.utc).isoformat()
    rows: list[dict] = []

    for fc in forecasts:
        props = fc.get("properties", {})
        amount_raw = props.get("hs_amount")
        try:
            amount = float(amount_raw) if amount_raw is not None else 0.0
        except (ValueError, TypeError):
            amount = 0.0

        hs_team_id = props.get("hs_team_id") or props.get("hubspot_team_id")
        hs_owner_id = props.get("hubspot_owner_id")
        notes = props.get("hs_submission_notes")
        last_mod = props.get("hs_lastmodifieddate")

        if hs_team_id:
            # Team submission (TL)
            tid = str(hs_team_id)
            closzr_team = team_id_map.get(tid)
            if not closzr_team:
                continue  # Unknown team — skip

            row = {
                "owner_id": f"team_{tid}",
                "owner_email": None,
                "team_id": tid,
                "team_name": closzr_team,
                "month": month_str,
                "pipeline_id": pipeline_id,
                "forecast_amount": amount,
                "submission_type": "team",
                "submission_notes": notes,
                "last_modified": last_mod,
                "synced_at": now_iso,
                "updated_at": now_iso,
            }
            rows.append(row)

        elif hs_owner_id:
            # Rep submission
            oid = str(hs_owner_id)
            email, team = owner_map.get(oid, (None, None))

            row = {
                "owner_id": oid,
                "owner_email": email,
                "team_id": None,
                "team_name": team,
                "month": month_str,
                "pipeline_id": pipeline_id,
                "forecast_amount": amount,
                "submission_type": "rep",
                "submission_notes": notes,
                "last_modified": last_mod,
                "synced_at": now_iso,
                "updated_at": now_iso,
            }
            rows.append(row)

    return rows


# ── Supabase write operations ───────────────────────────────────────────────

def _upsert_batch(sb: Client, rows: list[dict]) -> int:
    """Upsert rows into forecast_submissions in batches."""
    if not rows:
        return 0

    total = 0
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i : i + BATCH_SIZE]
        sb.table("forecast_submissions").upsert(
            batch,
            on_conflict="owner_id,month,pipeline_id,submission_type",
        ).execute()
        total += len(batch)

    return total


def _insert_history(sb: Client, rows: list[dict]) -> int:
    """Insert rows into forecast_submissions_history (strip created_at/updated_at)."""
    if not rows:
        return 0

    history_rows = []
    for r in rows:
        hr = {k: v for k, v in r.items() if k not in ("created_at", "updated_at")}
        history_rows.append(hr)

    total = 0
    for i in range(0, len(history_rows), BATCH_SIZE):
        batch = history_rows[i : i + BATCH_SIZE]
        sb.table("forecast_submissions_history").insert(batch).execute()
        total += len(batch)

    return total


# ── Main orchestrator ────────────────────────────────────────────────────────

def run(months: list[str] | None = None) -> dict:
    """
    Sync HubSpot forecasts to Supabase.

    Args:
        months: list of "YYYY-MM" strings. Defaults to [previous_month, current_month].

    Returns:
        Summary dict with counts.
    """
    t0 = time.time()
    print("=" * 60)
    print("sync_forecasts: start")
    print("=" * 60)

    # 1. Default months: previous + current
    if not months:
        now = datetime.now(timezone.utc)
        current = now.strftime("%Y-%m")
        prev_month = (now.replace(day=1) - timedelta(days=1))
        previous = prev_month.strftime("%Y-%m")
        months = [previous, current]

    print(f"  target months: {months}")
    print(f"  pipelines: {PIPELINES}")

    # 2. Supabase client + load maps
    sb = _supabase()
    print("\nloading owner/team maps...")
    owner_map, team_id_map = _load_owner_map(sb)

    # 3. Fetch + parse for each (month, pipeline)
    all_rows: list[dict] = []
    team_rows: list[dict] = []
    fetch_count = 0

    for month_str in months:
        parts = month_str.split("-")
        year = int(parts[0])
        month_num = int(parts[1])

        for pipeline_id in PIPELINES:
            print(f"\n  fetching: {month_str} / pipeline={pipeline_id}")
            forecasts = _fetch_forecasts(year, month_num, pipeline_id)
            fetch_count += len(forecasts)
            print(f"    → {len(forecasts)} forecast records")

            rows = _parse_submissions(forecasts, owner_map, team_id_map, month_str, pipeline_id)
            print(f"    → {len(rows)} parsed rows")

            for r in rows:
                all_rows.append(r)
                if r["submission_type"] == "team":
                    team_rows.append(r)

    rep_count = sum(1 for r in all_rows if r["submission_type"] == "rep")
    team_count = sum(1 for r in all_rows if r["submission_type"] == "team")
    print(f"\ntotal: {len(all_rows)} rows ({rep_count} rep + {team_count} team)")

    # 4. Delete existing team submissions for target months (prevents orphaned TL submissions)
    if team_rows:
        print("\ncleaning stale team submissions...")
        for month_str in months:
            for pipeline_id in PIPELINES:
                sb.table("forecast_submissions") \
                    .delete() \
                    .eq("submission_type", "team") \
                    .eq("month", month_str) \
                    .eq("pipeline_id", pipeline_id) \
                    .execute()
        print("  done")

    # 5. Upsert all rows
    if all_rows:
        print("\nupserting to forecast_submissions...")
        upserted = _upsert_batch(sb, all_rows)
        print(f"  upserted: {upserted} rows")

    # 6. Insert history
    if all_rows:
        print("\ninserting to forecast_submissions_history...")
        inserted = _insert_history(sb, all_rows)
        print(f"  inserted: {inserted} history rows")

    elapsed = time.time() - t0
    summary = {
        "months": months,
        "pipelines": PIPELINES,
        "fetched": fetch_count,
        "parsed": len(all_rows),
        "rep_submissions": rep_count,
        "team_submissions": team_count,
        "elapsed_seconds": round(elapsed, 1),
    }

    print("\n" + "=" * 60)
    print(f"sync_forecasts: done in {summary['elapsed_seconds']}s")
    print(f"  fetched: {fetch_count} | parsed: {len(all_rows)} | rep: {rep_count} | team: {team_count}")
    print("=" * 60)

    return summary


# ── CLI entrypoint ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    target_months = sys.argv[1:] if len(sys.argv) > 1 else None
    run(months=target_months)
