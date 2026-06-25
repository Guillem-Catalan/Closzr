"""
Daily Run — morning safety net + closed deal processing.

Runs once per day at 03:00. Dispatched by pg_cron via GitHub Actions.

Steps:
  1. Full sync — all active deals from HubSpot (catches metadata changes CORE missed)
  2. Trajectories — compile newly closed deals for forecast benchmark
  3. Deal analysis — post-mortem for TLs/UI
  4. Parser — update deal_ui metadata for all active deals + analysis for closed ones

No CORE activation — if sync detects new activity, it marks context_stale=True
and the next CORE run picks it up.

Everything from config.
"""

import traceback

from src.config import (
    INTELLIGENCE_CONFIG,
    DAILY_CONFIG,
    ACTIVE_STAGES,
    STAGE_ID_TO_LABEL,
    CLOSED_ALL,
)
from src.db.client import supabase
from src.integrations import hubspot
from src.pipelines.core.sync import run as sync_run
from src.pipelines.core.intelligence import run as intelligence_run
from src.pipelines.core import parser
from src.pipelines.daily.trajectories import run as trajectories_run, compile_trajectory
from src.pipelines.daily.deal_analysis import run as deal_analysis_run, analyze_deal

_I = INTELLIGENCE_CONFIG
_D = DAILY_CONFIG
_CLOSED_LOWER = frozenset(s.lower() for s in CLOSED_ALL)


def _detect_and_process_closed() -> int:
    """Find deals that transitioned to closed in HubSpot but Supabase still shows active.
    Process final snapshot + update stage. Returns count processed."""

    # 1. Get deals with active stage + snapshot (deals we're tracking)
    active_stages = list(ACTIVE_STAGES)
    tracked = []
    offset = 0
    while True:
        resp = (
            supabase.table(_I["deals_table"])
            .select(f"{_I['deal_col_id']}, {_I['deal_col_deal_id']}, {_I['deal_col_deal_name']}, {_I['deal_col_stage']}")
            .in_(_I["deal_col_stage"], active_stages)
            .not_.is_(_I["deal_context_col"], "null")
            .range(offset, offset + 999)
            .execute()
        )
        batch = resp.data or []
        tracked.extend(batch)
        if len(batch) < 1000:
            break
        offset += 1000

    if not tracked:
        return 0

    # 2. Batch read dealstage from HubSpot
    hs_ids = [d[_I["deal_col_deal_id"]] for d in tracked if d.get(_I["deal_col_deal_id"])]
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
    for d in tracked:
        hs_id = d.get(_I["deal_col_deal_id"], "")
        hs_stage = hs_stages.get(hs_id, "")
        if hs_stage.lower() in _CLOSED_LOWER:
            transitions.append((d, hs_stage))

    if not transitions:
        return 0

    print(f"    {len(transitions)} deals transitioned to closed")

    # 4. Process each: update stage + snapshot + trajectory + analysis
    processed = 0
    for deal, new_stage in transitions:
        deal_uuid = deal[_I["deal_col_id"]]
        deal_name = deal.get(_I["deal_col_deal_name"]) or "?"
        print(f"\n    [{deal_name[:40]}] {deal.get(_I['deal_col_stage'])} → {new_stage}")

        try:
            # Update stage
            supabase.table(_I["deals_table"]).update(
                {_I["deal_col_stage"]: new_stage}
            ).eq(_I["deal_col_id"], deal_uuid).execute()

            # Final snapshot (no forecast — deal is closed)
            result = intelligence_run(deal_uuid)
            if result:
                parser.update_from_sync(deal_uuid)
                parser.update_from_intelligence(deal_uuid)
                print(f"    ✓ Final snapshot")
            else:
                parser.update_from_sync(deal_uuid)

            # Re-fetch deal with updated stage for trajectory + analysis
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

    compiled = 0
    analyzed = 0

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

    # ── 2. Detect closed deals ──
    print("\n▸ CLOSED DEAL DETECTION")
    try:
        closed = _detect_and_process_closed()
        print(f"  {closed} closed deals processed")
    except Exception as e:
        print(f"  ✗ Closed detection failed: {e}")
        traceback.print_exc()

    # ── 3. Trajectories ──
    print("\n▸ TRAJECTORIES")
    try:
        compiled = trajectories_run()
        print(f"  {compiled} trajectories compiled")
    except Exception as e:
        print(f"  ✗ Trajectories failed: {e}")
        traceback.print_exc()

    # ── 3. Deal analysis ──
    print("\n▸ DEAL ANALYSIS")
    try:
        analyzed = deal_analysis_run()
        print(f"  {analyzed} analyses completed")
    except Exception as e:
        print(f"  ✗ Deal analysis failed: {e}")
        traceback.print_exc()

    # ── 4. Parser — metadata for all active deals ──
    print("\n▸ PARSER — metadata update")
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
                updated += 1
            except Exception as e:
                errors += 1
                if errors <= 3:
                    print(f"    Parser error: {e}")

        if len(deals) < page_size:
            break
        offset += page_size

    print(f"  {updated} deals metadata updated, {errors} errors")

    # ── 4b. Parser — analysis for closed deals ──
    print("\n▸ PARSER — deal analysis update")
    closed_stages = _D["closed_stages"] + _D["on_hold_stages"]
    analysis_updated = 0

    resp = (
        supabase.table(_D["analysis_table"])
        .select("deal_id")
        .execute()
    )
    analysis_ids = [r["deal_id"] for r in (resp.data or [])]

    for deal_uuid in analysis_ids:
        try:
            parser.update_from_daily(deal_uuid)
            analysis_updated += 1
        except Exception as e:
            if errors <= 3:
                print(f"    Parser daily error: {e}")

    print(f"  {analysis_updated} deal analyses synced to deal_ui")

    # ── Summary ──
    print(f"\n{'=' * 60}")
    print(f"DAILY DONE: {updated} metadata + {compiled} trajectories + {analyzed} analyses")
    print("=" * 60)
