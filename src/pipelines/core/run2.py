"""
Core Run v2 — orchestrator del CORE pipeline.

Entry point: run(full=False)

Phases:
  1. sync2     — HubSpot → Supabase, marca stale    → parser2.update_from_sync
  2. atlas2    — company intelligence (si falta)     → parser2.update_from_atlas
  3. intelligence2 — comms + Claude → snapshot       → parser2.update_from_intelligence
  4. forecast2 — Opus → timing + probability         → parser2.update_from_forecast

Each phase updates its columns in deal_ui via parser2.
All references via schema + config2. Zero config (v1) imports.
"""

import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

from src import schema
from src.config2 import (
    MAX_DEALS_PER_CYCLE,
    CORE_TIMEOUT_MINUTES,
    CORE_WORKERS,
    DEAL_NAME_EXCLUDE_PATTERNS,
)
from src.db.client import supabase
from src.pipelines.core.sync2 import run as sync_run
from src.pipelines.core.atlas2 import generate as atlas_generate
from src.pipelines.core.intelligence2 import run as intelligence_run
from src.pipelines.core.forecast2 import run as forecast_run
from src.pipelines.core import parser2


# ═══════════════════════════════════════════════════════════════════════════
# RESOLVED CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════

_TBL_DEALS = schema.tbl("deals")
_TBL_ATLAS = schema.tbl("atlas")

_D_UUID       = schema.col("deal_uuid")        # "id"
_D_ID         = schema.col("deal_id")           # "deal_id"
_D_NAME       = schema.col("deal_name")         # "deal_name"
_D_STAGE      = schema.col("stage")             # "deal_stage"
_D_CRM_ID     = schema.col("crm_id")           # "crm_id"
_D_TEAM       = schema.col("team")              # "team"
_D_PAE        = schema.col("pae")               # "pae"
_D_PBD        = schema.col("pbd")               # "pbd"
_D_STALE      = schema.col("context_stale")     # "context_stale"
_D_ATLAS_ID   = schema.col("atlas_ref")         # "atlas_id"
_D_PIPELINE   = schema.col("pipeline")          # "pipeline_name"

_A_FK_CRM     = schema.upsert_key("atlas")           # "crm_id"
_A_LAST_GEN   = schema.ATLAS_COLS["last_generated"]  # "last_generated"

_D_UPDATED_AT = schema.SYSTEM_COLS["updated_at"]  # Supabase system column

_ACTIVE_STAGES = list(schema.ACTIVE)

_PRIORITY_PIPELINES = frozenset({"Sales Pipeline", "Partners Distribution"})

_SELECT_COLS = ", ".join([_D_UUID, _D_ID, _D_NAME, _D_STAGE, _D_CRM_ID, _D_TEAM, _D_PAE, _D_PBD, _D_ATLAS_ID, _D_PIPELINE])


# ═══════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _deal_priority(deal: dict) -> int:
    """Lower number = processed first.

    0  Sales/Partners + closing
    1  Sales/Partners + evaluation
    2  Sales/Partners + demo
    3  Sales/Partners + pre-demo (prospecting/nurturing)
    4  Other pipelines
    """
    pipeline = deal.get(_D_PIPELINE) or ""
    stage = deal.get(_D_STAGE) or ""
    cat = schema.stage_category(stage)

    if pipeline in _PRIORITY_PIPELINES:
        if cat == "closing":    return 0
        if cat == "evaluation": return 1
        if cat == "demo":       return 2
        return 3
    return 4


def _fetch_stale_deals(limit: int) -> list[dict]:
    all_deals: list[dict] = []
    offset = 0
    while True:
        resp = (
            supabase.table(_TBL_DEALS)
            .select(_SELECT_COLS)
            .eq(_D_STALE, True)
            .in_(_D_STAGE, _ACTIVE_STAGES)
            .range(offset, offset + 999)
            .execute()
        )
        batch = resp.data or []
        all_deals.extend(batch)
        if len(batch) < 1000:
            break
        offset += 1000

    all_deals = [
        d for d in all_deals
        if not any(pat in (d.get(_D_NAME) or "").lower() for pat in DEAL_NAME_EXCLUDE_PATTERNS)
    ]

    all_deals.sort(key=lambda d: (_deal_priority(d), d.get(_D_UPDATED_AT) or ""))

    return all_deals[:limit]


def _needs_atlas(deal: dict) -> bool:
    crm_id = deal.get(_D_CRM_ID)
    if not crm_id:
        return False
    resp = (
        supabase.table(_TBL_ATLAS)
        .select(_A_LAST_GEN)
        .eq(_A_FK_CRM, crm_id)
        .maybe_single()
        .execute()
    )
    if not resp.data:
        return False
    return resp.data.get(_A_LAST_GEN) is None


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def run(full: bool = False):
    print("=" * 60)
    print("CORE RUN v2")
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
        deal_uuid = deal[_D_UUID]
        deal_name = deal.get(_D_NAME) or "?"
        crm_id = deal.get(_D_CRM_ID) or ""

        print(f"\n{'─' * 50}")
        print(f"  [{idx}/{total}] {deal_name}")

        try:
            parser2.update_from_sync(deal_uuid)
        except Exception as e:
            print(f"    Parser sync failed: {e}")

        if _needs_atlas(deal):
            print(f"  ▸ ATLAS")
            try:
                atlas_generate(
                    deal.get(_D_ATLAS_ID) or "", crm_id,
                    team=deal.get(_D_TEAM) or "",
                    owner_email=deal.get(_D_PAE) or deal.get(_D_PBD) or "",
                )
                parser2.update_from_atlas(deal_uuid)
            except Exception as e:
                print(f"    Atlas failed: {e}")

        print(f"  ▸ INTELLIGENCE")
        intel_result = intelligence_run(deal_uuid)

        if intel_result:
            try:
                parser2.update_from_intelligence(deal_uuid)
            except Exception as e:
                print(f"    Parser intelligence failed: {e}")

            if intel_result.get("snapshot"):
                print(f"  ▸ FORECAST")
                try:
                    forecast_result = forecast_run(deal_uuid)
                    if forecast_result:
                        parser2.update_from_forecast(deal_uuid)
                except Exception as e:
                    print(f"    Forecast failed: {e}")

        return deal_name

    with ThreadPoolExecutor(max_workers=CORE_WORKERS) as pool:
        active: dict = {}
        deal_iter = enumerate(stale_deals, 1)
        stopped = False

        def _submit_next():
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
                active[future] = deal.get(_D_NAME) or "?"
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
    print(f"CORE v2 DONE: {ok} OK, {failed} failed (workers={CORE_WORKERS})")
    if failures:
        print("Failures:")
        for f in failures:
            print(f"  - {f}")
    print("=" * 60)
