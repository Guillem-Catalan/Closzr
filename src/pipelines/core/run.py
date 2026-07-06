"""
Core Run — orchestrator del CORE pipeline.

Entry point: run(full=False)

Phases:
  1. sync      — HubSpot → Supabase, marca stale    → parser.update_from_sync
  2. atlas     — company intelligence (si falta)     → parser.update_from_atlas
  3. intelligence — fetch comms + Claude → audits + snapshot + deal_context → parser.update_from_intelligence
  4. forecast  — Opus → timing + probability          → parser.update_from_forecast

Each phase updates its columns in deal_ui via parser.
Everything from config.
"""

import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.config import (
    INTELLIGENCE_CONFIG,
    ACTIVE_STAGES,
    MAX_DEALS_PER_CYCLE,
    CORE_TIMEOUT_MINUTES,
    CORE_WORKERS,
)
from src.db.client import supabase
from src.pipelines.core.sync import run as sync_run
from src.pipelines.core.atlas import generate as atlas_generate
from src.pipelines.core.intelligence import run as intelligence_run
from src.pipelines.core.forecast import run as forecast_run
from src.pipelines.core import parser

_I = INTELLIGENCE_CONFIG


def _fetch_stale_deals(limit: int) -> list[dict]:
    stages = list(ACTIVE_STAGES)
    resp = (
        supabase.table(_I["deals_table"])
        .select(f"{_I['deal_col_id']}, {_I['deal_col_deal_id']}, {_I['deal_col_deal_name']}, "
                f"{_I['deal_col_stage']}, {_I['deal_col_crm_id']}")
        .eq(_I["context_stale_col"], True)
        .in_(_I["deal_col_stage"], stages)
        .order("updated_at", desc=False)
        .limit(limit)
        .execute()
    )
    deals = resp.data or []

    exclude = _I.get("deal_name_exclude_patterns", [])
    return [d for d in deals if not any(pat in (d.get(_I["deal_col_deal_name"]) or "").lower() for pat in exclude)]


def _needs_atlas(deal: dict) -> bool:
    crm_id = deal.get(_I["deal_col_crm_id"])
    if not crm_id:
        return False
    resp = (
        supabase.table(_I["atlas_table"])
        .select("last_generated")
        .eq(_I["fk_crm_id"], crm_id)
        .maybe_single()
        .execute()
    )
    if not resp.data:
        return False
    return resp.data.get("last_generated") is None


def run(full: bool = False):
    print("=" * 60)
    print("CORE RUN")
    print("=" * 60)

    # ── Phase 1: Sync ──
    print("\n▸ SYNC")
    try:
        sync_result = sync_run(full=full)
        stale_count = sync_result.get("stale", 0) if isinstance(sync_result, dict) else 0
        print(f"  Sync done. {stale_count} stale deals.")
    except Exception as e:
        print(f"  Sync failed: {e} — continuing with existing data")
        traceback.print_exc()

    # ── Fetch stale deals ──
    stale_deals = _fetch_stale_deals(MAX_DEALS_PER_CYCLE)
    if not stale_deals:
        print("\n▸ No stale deals to process.")
        return

    total = len(stale_deals)
    print(f"\n▸ {total} stale deals (cap {MAX_DEALS_PER_CYCLE}, workers {CORE_WORKERS})")

    ok = 0
    failed = 0
    failures: list[str] = []
    start_time = time.time()
    timeout_seconds = CORE_TIMEOUT_MINUTES * 60

    def _process_deal(idx: int, deal: dict) -> str:
        """Process a single deal. Returns deal_name on success."""
        deal_uuid = deal[_I["deal_col_id"]]
        deal_name = deal.get(_I["deal_col_deal_name"]) or "?"
        crm_id = deal.get(_I["deal_col_crm_id"]) or ""

        print(f"\n{'─' * 50}")
        print(f"  [{idx}/{total}] {deal_name}")

        try:
            parser.update_from_sync(deal_uuid)
        except Exception as e:
            print(f"    Parser sync failed: {e}")

        if _needs_atlas(deal):
            print(f"  ▸ ATLAS")
            try:
                atlas_generate(
                    deal.get("atlas_id") or "", crm_id,
                    team=deal.get(_I["deal_col_team"]) or "",
                    owner_email=deal.get(_I["deal_col_pae"]) or deal.get(_I["deal_col_pbd"]) or "",
                )
                parser.update_from_atlas(deal_uuid)
            except Exception as e:
                print(f"    Atlas failed: {e}")

        print(f"  ▸ INTELLIGENCE")
        intel_result = intelligence_run(deal_uuid)

        if intel_result:
            try:
                parser.update_from_intelligence(deal_uuid)
            except Exception as e:
                print(f"    Parser intelligence failed: {e}")

            if intel_result.get("snapshot"):
                print(f"  ▸ FORECAST")
                try:
                    forecast_result = forecast_run(deal_uuid)
                    if forecast_result:
                        parser.update_from_forecast(deal_uuid)
                except Exception as e:
                    print(f"    Forecast failed: {e}")

        return deal_name

    with ThreadPoolExecutor(max_workers=CORE_WORKERS) as pool:
        active: dict = {}
        deal_iter = enumerate(stale_deals, 1)
        stopped = False

        def _submit_next():
            """Submit next deal if slot available and not timed out."""
            nonlocal stopped
            if stopped:
                return
            elapsed = time.time() - start_time
            if elapsed > timeout_seconds:
                remaining = total - ok - failed - len(active)
                print(f"\n  ⏱ Timeout ({CORE_TIMEOUT_MINUTES}min) — {ok + failed} done, {remaining} remaining for next run")
                stopped = True
                return
            try:
                i, deal = next(deal_iter)
                future = pool.submit(_process_deal, i, deal)
                active[future] = deal.get(_I["deal_col_deal_name"]) or "?"
            except StopIteration:
                stopped = True

        for _ in range(CORE_WORKERS):
            _submit_next()

        while active:
            done = next(as_completed(active))
            deal_name = active.pop(done)
            try:
                done.result()
                ok += 1
            except Exception as e:
                failed += 1
                failures.append(f"{deal_name}: {e}")
                print(f"  ✗ FAILED [{deal_name}]: {e}")
                traceback.print_exc()

            _submit_next()

    # ── Summary ──
    print(f"\n{'=' * 60}")
    print(f"CORE DONE: {ok} OK, {failed} failed (workers={CORE_WORKERS})")
    if failures:
        print("Failures:")
        for f in failures:
            print(f"  - {f}")
    print("=" * 60)
