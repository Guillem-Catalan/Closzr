"""
Daily Run — morning safety net + closed deal processing.

Runs once per day at 03:00. Dispatched by pg_cron via GitHub Actions.

Steps:
  1. Full sync — all active deals from HubSpot (catches metadata changes CORE missed)
  2. Forecast refresh — re-forecast deals with imminent Claudio close date
  3. Closed deal detection — detect HubSpot stage transitions to closed
  4. Parser — full deal_ui refresh (all 5 entry points for every deal)

No CORE activation — if sync detects new activity, it marks context_stale=True
and the next CORE run picks it up.

Everything from config.
"""

import traceback
from datetime import date, timedelta

from src.config import (
    INTELLIGENCE_CONFIG,
    DAILY_CONFIG,
    ACTIVE_STAGES,
    STAGE_ID_TO_LABEL,
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


def _refresh_imminent_forecasts() -> int:
    """Re-forecast deals whose Claudio close date is within N days."""
    threshold_days = _D.get("forecast_refresh_days", 5)
    threshold = (date.today() + timedelta(days=threshold_days)).isoformat()

    resp = (
        supabase.table("deal_ui")
        .select("deal_id, deal_name_full, estimated_close_date")
        .is_("outcome", "null")
        .not_.is_("estimated_close_date", "null")
        .lte("estimated_close_date", threshold)
        .execute()
    )
    deals = resp.data or []
    if not deals:
        return 0

    print(f"    {len(deals)} deals with close date <= {threshold}")

    refreshed = 0
    for d in deals:
        deal_uuid = d["deal_id"]
        deal_name = (d.get("deal_name_full") or "?")[:50]
        close_dt = d.get("estimated_close_date") or "?"

        try:
            result = forecast_refresh(deal_uuid)
            if result:
                parser.update_from_forecast(deal_uuid)
                refreshed += 1
                print(f"    ✓ {deal_name} ({close_dt} → {result.get('estimated_close_date', '?')})")
        except Exception as e:
            print(f"    ✗ {deal_name}: {e}")

    return refreshed


def _detect_and_process_closed() -> int:
    """Find deals that transitioned to closed in HubSpot but Supabase still shows active.
    Re-syncs ALL properties from HubSpot, then processes final snapshot + trajectory + analysis."""

    # 1. Get ALL deals with active stage in Supabase (no snapshot filter)
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
        return 0

    # Deduplicate by deal UUID
    seen = set()
    unique = []
    for d in active_deals:
        did = d[_I["deal_col_id"]]
        if did not in seen:
            seen.add(did)
            unique.append(d)
    active_deals = unique
    print(f"    {len(active_deals)} active deals in Supabase")

    # 2. Batch read dealstage from HubSpot
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

    # 3. Find transitions: Supabase active → HubSpot closed
    transitions = []
    for d in active_deals:
        hs_id = d.get(_I["deal_col_deal_id"], "")
        hs_stage = hs_stages.get(hs_id, "")
        if hs_stage.lower() in _CLOSED_LOWER:
            transitions.append(d)

    if not transitions:
        return 0

    print(f"    {len(transitions)} deals transitioned to closed")

    # 4. Re-sync full properties from HubSpot for transitioned deals
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

    # Resolve and upsert full deal data (allow_closed=True to not skip closed stages)
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
        print(f"    ✓ {len(resolved_by_uuid)} deals fully re-synced from HubSpot")

    # 5. Process each: snapshot + trajectory + analysis
    processed = 0
    for deal in transitions:
        deal_uuid = deal[_I["deal_col_id"]]
        deal_name = deal.get(_I["deal_col_deal_name"]) or "?"
        hs_id = deal.get(_I["deal_col_deal_id"], "")
        new_stage = hs_stages.get(hs_id, "?")
        print(f"\n    [{deal_name[:40]}] {deal.get(_I['deal_col_stage'])} → {new_stage}")

        try:
            # Final snapshot (no forecast — deal is closed)
            result = intelligence_run(deal_uuid)
            if result:
                parser.update_from_sync(deal_uuid)
                parser.update_from_intelligence(deal_uuid)
                print(f"    ✓ Final snapshot")
            else:
                parser.update_from_sync(deal_uuid)

            # Re-fetch deal with updated data for trajectory + analysis
            deal_fresh = supabase.table(_I["deals_table"]).select("*").eq(_I["deal_col_id"], deal_uuid).limit(1).execute()
            if deal_fresh.data:
                d = deal_fresh.data[0]

                # Trajectory
                try:
                    traj = compile_trajectory(d)
                    if traj:
                        print(f"    ✓ Trajectory ({traj.get('outcome', '?')})")
                except Exception as e:
                    print(f"    ✗ Trajectory failed: {e}")

                # Deal analysis
                try:
                    analysis = analyze_deal(d)
                    if analysis:
                        parser.update_from_daily(deal_uuid)
                        print(f"    ✓ Analysis done")
                except Exception as e:
                    print(f"    ✗ Analysis failed: {e}")

            processed += 1
        except Exception as e:
            print(f"    ✗ Failed: {e}")

    return processed


def run():
    print("=" * 60)
    print("DAILY RUN")
    print("=" * 60)

    # ── 1. Full sync ──
    print("\n▸ FULL SYNC")
    try:
        result = sync_run(full=True)
        synced = result.get("synced", 0) if isinstance(result, dict) else 0
        stale = result.get("stale", 0) if isinstance(result, dict) else 0
        print(f"  {synced} deals synced, {stale} marked stale for next CORE")
    except Exception as e:
        print(f"  ✗ Full sync failed: {e}")
        traceback.print_exc()

    # ── 2. Forecast refresh — deals with imminent close date ──
    print("\n▸ FORECAST REFRESH")
    try:
        refreshed = _refresh_imminent_forecasts()
        print(f"  {refreshed} forecasts refreshed")
    except Exception as e:
        print(f"  ✗ Forecast refresh failed: {e}")
        traceback.print_exc()

    # ── 3. Detect closed deals ──
    print("\n▸ CLOSED DEAL DETECTION")
    closed = 0
    try:
        closed = _detect_and_process_closed()
        print(f"  {closed} closed deals processed")
    except Exception as e:
        print(f"  ✗ Closed detection failed: {e}")
        traceback.print_exc()

    # ── 4. Parser — full deal_ui refresh ──
    print("\n▸ PARSER — full deal_ui refresh")
    stages = list(ACTIVE_STAGES) + _D["closed_stages"] + _D["on_hold_stages"]
    updated = 0
    errors = 0
    offset = 0
    page_size = 500

    while True:
        resp = (
            supabase.table(_I["deals_table"])
            .select(_I["deal_col_id"])
            .in_(_I["deal_col_stage"], stages)
            .range(offset, offset + page_size - 1)
            .execute()
        )
        deals = resp.data or []
        if not deals:
            break

        for d in deals:
            deal_uuid = d[_I["deal_col_id"]]
            try:
                parser.update_from_sync(deal_uuid)
                parser.update_from_atlas(deal_uuid)
                parser.update_from_intelligence(deal_uuid)
                parser.update_from_forecast(deal_uuid)
                parser.update_from_daily(deal_uuid)
                updated += 1
            except Exception as e:
                errors += 1
                if errors <= 3:
                    print(f"    Parser error ({deal_uuid}): {e}")

        if len(deals) < page_size:
            break
        offset += page_size

    print(f"  {updated} deals fully refreshed, {errors} errors")

    # ── Summary ──
    print(f"\n{'=' * 60}")
    print(f"DAILY DONE: {updated} deals refreshed, {closed} closed processed")
    print("=" * 60)
