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
)
from src.db.client import supabase
from src.pipelines.core.sync import run as sync_run
from src.pipelines.core import parser
from src.pipelines.daily.trajectories import run as trajectories_run
from src.pipelines.daily.deal_analysis import run as deal_analysis_run

_I = INTELLIGENCE_CONFIG
_D = DAILY_CONFIG


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

    # ── 2. Trajectories ──
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
