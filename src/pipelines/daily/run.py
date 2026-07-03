"""
Daily Run — morning safety net + closed deal processing.

Runs once per day. Dispatched by pg_cron via GitHub Actions.

Steps:
  1. Sync — refresh metadata from HubSpot for all open deals
  2. Forecast refresh — new snapshot + forecast for deals with imminent/past close date
  3. Closed deal detection — find HubSpot closed transitions, run final snapshot + trajectory + analysis
  4. Parser — update deal_ui for all deals touched in steps 1-3

Everything from config.
"""

import traceback
from datetime import date, timedelta

from src.config import (
    INTELLIGENCE_CONFIG,
    DAILY_CONFIG,
    STAGE_ID_TO_LABEL,
    ACTIVE_STAGES,
    CLOSED_ALL,
    HS_ALL_DEAL_PROPS,
    SYNC_CONFIG,
    UPSERT_BATCH_SIZE,
)
from src.db.client import supabase
from src.integrations import hubspot
from src.pipelines.core.sync import (
    run as sync_run,
    _resolve_deal,
    _fetch_owners,
    _fetch_company_associations,
    _fetch_partner_associations,
)
from src.pipelines.core.intelligence import run as intelligence_run
from src.pipelines.core.forecast import run_refresh as forecast_refresh
from src.pipelines.core import parser
from src.pipelines.daily.trajectories import compile_trajectory
from src.pipelines.daily.deal_analysis import analyze_deal

_I = INTELLIGENCE_CONFIG
_D = DAILY_CONFIG
_SC = SYNC_CONFIG
_CLOSED_LOWER = frozenset(s.lower() for s in CLOSED_ALL)

FORECAST_REFRESH_DAYS = _D.get("forecast_refresh_days", 5)
REFRESH_COOLDOWN_DAYS = 3


# ─────────────────────────────────────────────────────────────
# STEP 2 — Forecast refresh
# ─────────────────────────────────────────────────────────────

def _refresh_imminent_forecasts() -> list[str]:
    """Re-snapshot + re-forecast deals with close date within N days or past due.
    Skips deals already refreshed in the last REFRESH_COOLDOWN_DAYS.
    Returns list of deal_uuids processed."""

    today = date.today()
    threshold = (today + timedelta(days=FORECAST_REFRESH_DAYS)).isoformat()
    cooldown = (today - timedelta(days=REFRESH_COOLDOWN_DAYS)).isoformat()

    resp = (
        supabase.table("deal_ui")
        .select("deal_id, deal_name_full, estimated_close_date, snapshot_date")
        .is_("outcome", "null")
        .not_.is_("estimated_close_date", "null")
        .lte("estimated_close_date", threshold)
        .execute()
    )

    candidates = [
        d for d in (resp.data or [])
        if not d.get("snapshot_date") or d["snapshot_date"] < cooldown
    ]

    if not candidates:
        print("  No deals need forecast refresh")
        return []

    print(f"  {len(candidates)} deals to refresh (close date <= {threshold}, snapshot older than {cooldown})")

    refreshed_ids = []
    for d in candidates:
        deal_uuid = d["deal_id"]
        deal_name = (d.get("deal_name_full") or "?")[:50]
        old_date = d.get("estimated_close_date") or "?"

        try:
            intelligence_run(deal_uuid)
            result = forecast_refresh(deal_uuid)
            new_date = result.get("estimated_close_date", "?") if result else "unchanged"
            print(f"    ✓ {deal_name} ({old_date} → {new_date})")
            refreshed_ids.append(deal_uuid)
        except Exception as e:
            print(f"    ✗ {deal_name}: {e}")

    return refreshed_ids


# ─────────────────────────────────────────────────────────────
# STEP 3 — Closed deal detection
# ─────────────────────────────────────────────────────────────

def _detect_and_process_closed() -> list[str]:
    """Find deals that transitioned to closed in HubSpot.
    Re-syncs properties, runs final snapshot + trajectory + analysis.
    Returns list of deal_uuids processed."""

    active_stages = list(ACTIVE_STAGES)
    active_deals = []
    offset = 0
    while True:
        resp = (
            supabase.table(_I["deals_table"])
            .select(f"{_I['deal_col_id']}, {_I['deal_col_deal_id']}, {_I['deal_col_deal_name']}, {_I['deal_col_stage']}")
            .in_(_I["deal_col_stage"], active_stages)
            .range(offset, offset + 999)
            .execute()
        )
        batch = resp.data or []
        active_deals.extend(batch)
        if len(batch) < 1000:
            break
        offset += 1000

    if not active_deals:
        return []

    seen = set()
    unique = []
    for d in active_deals:
        did = d[_I["deal_col_id"]]
        if did not in seen:
            seen.add(did)
            unique.append(d)
    active_deals = unique
    print(f"  {len(active_deals)} active deals in Supabase")

    hs_ids = [d[_I["deal_col_deal_id"]] for d in active_deals if d.get(_I["deal_col_deal_id"])]
    hs_stages: dict[str, str] = {}
    for i in range(0, len(hs_ids), 100):
        batch = hs_ids[i:i + 100]
        try:
            data = hubspot.post(
                "/crm/v3/objects/deals/batch/read",
                {"inputs": [{"id": did} for did in batch], "properties": [_D["hs_dealstage_prop"]]},
            )
            for obj in data.get("results", []):
                raw = obj.get("properties", {}).get(_D["hs_dealstage_prop"], "")
                stage = STAGE_ID_TO_LABEL.get(raw, raw)
                hs_stages[obj["id"]] = stage
        except Exception as e:
            print(f"    Batch read failed: {e}")

    transitions = [
        d for d in active_deals
        if hs_stages.get(d.get(_I["deal_col_deal_id"], ""), "").lower() in _CLOSED_LOWER
    ]

    if not transitions:
        return []

    print(f"  {len(transitions)} deals transitioned to closed")

    transition_hs_ids = [d[_I["deal_col_deal_id"]] for d in transitions if d.get(_I["deal_col_deal_id"])]
    owners = _fetch_owners()
    company_map = _fetch_company_associations(transition_hs_ids)
    partner_map = _fetch_partner_associations(transition_hs_ids)

    hs_full: list[dict] = []
    for i in range(0, len(transition_hs_ids), 100):
        batch = transition_hs_ids[i:i + 100]
        try:
            data = hubspot.post(
                "/crm/v3/objects/deals/batch/read",
                {"inputs": [{"id": did} for did in batch], "properties": HS_ALL_DEAL_PROPS},
            )
            hs_full.extend(data.get("results", []))
        except Exception as e:
            print(f"    Full property batch read failed: {e}")

    resolved_by_uuid: dict[str, dict] = {}
    for hd in hs_full:
        row = _resolve_deal(hd, owners, company_map, partner_map, allow_closed=True)
        if row:
            deal_uuid = row.get(_SC["col_deal_id"])
            if deal_uuid:
                resolved_by_uuid[deal_uuid] = row

    if resolved_by_uuid:
        rows_to_upsert = list(resolved_by_uuid.values())
        for i in range(0, len(rows_to_upsert), UPSERT_BATCH_SIZE):
            batch = rows_to_upsert[i:i + UPSERT_BATCH_SIZE]
            supabase.table(_SC["deals_table"]).upsert(batch, on_conflict=_SC["deals_upsert_key"]).execute()
        print(f"  ✓ {len(resolved_by_uuid)} deals re-synced from HubSpot")

    closed_ids = []
    for deal in transitions:
        deal_uuid = deal[_I["deal_col_id"]]
        deal_name = deal.get(_I["deal_col_deal_name"]) or "?"
        hs_id = deal.get(_I["deal_col_deal_id"], "")
        new_stage = hs_stages.get(hs_id, "?")
        print(f"\n    [{deal_name[:40]}] {deal.get(_I['deal_col_stage'])} → {new_stage}")

        try:
            intelligence_run(deal_uuid)
            print(f"    ✓ Final snapshot")

            deal_fresh = (
                supabase.table(_I["deals_table"])
                .select("*")
                .eq(_I["deal_col_id"], deal_uuid)
                .limit(1)
                .execute()
            )
            if deal_fresh.data:
                d = deal_fresh.data[0]
                try:
                    traj = compile_trajectory(d)
                    if traj:
                        print(f"    ✓ Trajectory ({traj.get('outcome', '?')})")
                except Exception as e:
                    print(f"    ✗ Trajectory failed: {e}")

                try:
                    analysis = analyze_deal(d)
                    if analysis:
                        print(f"    ✓ Analysis done")
                except Exception as e:
                    print(f"    ✗ Analysis failed: {e}")

            closed_ids.append(deal_uuid)
        except Exception as e:
            print(f"    ✗ Failed: {e}")

    return closed_ids


# ─────────────────────────────────────────────────────────────
# STEP 4 — Parser (deal_ui refresh for touched deals only)
# ─────────────────────────────────────────────────────────────

def _run_parser(sync_ids: list[str], refresh_ids: list[str], closed_ids: list[str]) -> int:
    """Update deal_ui for deals touched during the daily run.
    - sync_ids: metadata only (update_from_sync)
    - refresh_ids: snapshot + forecast (sync + intelligence + forecast)
    - closed_ids: full (all 5 entry points)
    """
    refresh_set = set(refresh_ids)
    closed_set = set(closed_ids)
    all_ids = list(dict.fromkeys(sync_ids + refresh_ids + closed_ids))

    updated = 0
    errors = 0

    for deal_uuid in all_ids:
        try:
            parser.update_from_sync(deal_uuid)

            if deal_uuid in closed_set:
                parser.update_from_atlas(deal_uuid)
                parser.update_from_intelligence(deal_uuid)
                parser.update_from_forecast(deal_uuid)
                parser.update_from_daily(deal_uuid)
            elif deal_uuid in refresh_set:
                parser.update_from_intelligence(deal_uuid)
                parser.update_from_forecast(deal_uuid)

            updated += 1
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"    Parser error ({deal_uuid}): {e}")

    return updated


# ─────────────────────────────────────────────────────────────
# ORCHESTRATOR
# ─────────────────────────────────────────────────────────────

def run():
    print("=" * 60)
    print("DAILY RUN")
    print("=" * 60)

    sync_ids: list[str] = []
    refresh_ids: list[str] = []
    closed_ids: list[str] = []

    # ── 1. Sync — metadata from HubSpot ──
    print("\n▸ STEP 1: SYNC")
    try:
        result = sync_run(full=True)
        sync_ids = result.get("deal_ids", []) if isinstance(result, dict) else []
        synced = result.get("synced", 0) if isinstance(result, dict) else 0
        stale = result.get("stale", 0) if isinstance(result, dict) else 0
        print(f"  {synced} deals synced, {stale} marked stale")
    except Exception as e:
        print(f"  ✗ Sync failed: {e}")
        traceback.print_exc()

    # ── 2. Forecast refresh — imminent/past close dates ──
    print("\n▸ STEP 2: FORECAST REFRESH")
    try:
        refresh_ids = _refresh_imminent_forecasts()
        print(f"  {len(refresh_ids)} forecasts refreshed")
    except Exception as e:
        print(f"  ✗ Forecast refresh failed: {e}")
        traceback.print_exc()

    # ── 3. Closed deal detection ──
    print("\n▸ STEP 3: CLOSED DEAL DETECTION")
    try:
        closed_ids = _detect_and_process_closed()
        print(f"  {len(closed_ids)} closed deals processed")
    except Exception as e:
        print(f"  ✗ Closed detection failed: {e}")
        traceback.print_exc()

    # ── 4. Parser — deal_ui refresh for touched deals ──
    total_unique = len(set(sync_ids + refresh_ids + closed_ids))
    print(f"\n▸ STEP 4: PARSER ({total_unique} deals)")
    try:
        updated = _run_parser(sync_ids, refresh_ids, closed_ids)
        print(f"  {updated} deals updated in deal_ui")
    except Exception as e:
        print(f"  ✗ Parser failed: {e}")
        traceback.print_exc()

    # ── Summary ──
    print(f"\n{'=' * 60}")
    print(f"DAILY DONE: {len(sync_ids)} synced, {len(refresh_ids)} refreshed, {len(closed_ids)} closed")
    print("=" * 60)
