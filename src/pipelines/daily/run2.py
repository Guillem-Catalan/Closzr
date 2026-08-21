"""
Daily Run v2 — morning safety net + closed deal processing.

Runs once per day. Dispatched by pg_cron via GitHub Actions.

Steps:
  1. Sync — refresh all open deals from HubSpot (sync2, full=True)
  2. Parser batch — update deal_ui for ALL synced deals (batch, ~10 queries)
  3. Closed detection — find HubSpot closed transitions → last snapshot + trajectory + analysis + parser
  4. Reforecast — deals with imminent close date → intelligence + forecast + parser

Steps 3 and 4 run with parallel workers (ThreadPoolExecutor) to stay within
the 360-minute GitHub Actions timeout. Same pattern as core/run2.py.

Internal names everywhere: schema.tbl(), schema.col(), config2.*.
"""

import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta

from src import schema, org
from src.config2 import DAILY, UPSERT_BATCH_SIZE, DAILY_WORKERS, DAILY_TIMEOUT_MINUTES
from src.db.client import supabase
from src.integrations import hubspot
from src.pipelines.core.sync2 import (
    run as sync_run,
    _resolve_deal,
    _fetch_owners,
    _fetch_company_associations,
    _fetch_partner_associations,
    DEALS_TABLE,
    DEALS_UPSERT_KEY,
)
from src.pipelines.core.intelligence2 import run as intelligence_run
from src.pipelines.core.forecast2 import run as forecast_run
from src.pipelines.core import parser2
from src.pipelines.daily.trajectories2 import compile_trajectory
from src.pipelines.daily.deal_analysis2 import analyze_deal


# ═══════════════════════════════════════════════════════════════════════════
# RESOLVED CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════

_TBL_DEALS   = schema.tbl("deals")
_TBL_DEAL_UI = schema.tbl("deal_ui")

_D_UUID  = schema.col("deal_uuid")
_D_ID    = schema.col("deal_id")
_D_NAME  = schema.col("deal_name")
_D_STAGE = schema.col("stage")

_ACTIVE_STAGES = list(schema.ACTIVE)

_HS_STAGE_PROP     = org.crm_prop("stage")
_HS_STAGE_MAP      = org.CRM_STAGE_MAP
_HS_STAGE_TO_INT   = org.CRM_STAGE_LABEL_TO_INTERNAL
_HS_ALL_DEAL_PROPS = org.CRM_ALL_DEAL_PROPS

_FORECAST_DAYS    = DAILY["forecast_refresh_days"]
_FORECAST_COOLDOWN = DAILY["forecast_refresh_cooldown"]


# ═══════════════════════════════════════════════════════════════════════════
# STEP 2 — Parser batch (all synced deals → deal_ui)
# ═══════════════════════════════════════════════════════════════════════════

def _parser_batch_sync() -> int:
    """Batch update deal_ui for ALL deals in Supabase.
    Uses parser2.update_batch_from_sync() — ~10 queries instead of 6000+."""
    return parser2.update_batch_from_sync()


# ═══════════════════════════════════════════════════════════════════════════
# STEP 3 — Closed deal detection
# ═══════════════════════════════════════════════════════════════════════════

def _detect_and_process_closed(start_time: float) -> tuple[list[str], int]:
    """Find deals that transitioned to closed in HubSpot.
    Re-syncs properties, runs final snapshot + trajectory + analysis + parser.
    Returns (closed_ids, failed_count)."""

    active_deals = []
    offset = 0
    while True:
        resp = (
            supabase.table(_TBL_DEALS)
            .select(f"{_D_UUID}, {_D_ID}, {_D_NAME}, {_D_STAGE}")
            .in_(_D_STAGE, _ACTIVE_STAGES)
            .range(offset, offset + 999)
            .execute()
        )
        batch = resp.data or []
        active_deals.extend(batch)
        if len(batch) < 1000:
            break
        offset += 1000

    if not active_deals:
        return [], 0

    seen = set()
    unique = []
    for d in active_deals:
        did = d[_D_UUID]
        if did not in seen:
            seen.add(did)
            unique.append(d)
    active_deals = unique
    print(f"  {len(active_deals)} active deals in Supabase")

    hs_ids = [d[_D_ID] for d in active_deals if d.get(_D_ID)]
    hs_stages: dict[str, str] = {}
    for i in range(0, len(hs_ids), 100):
        batch = hs_ids[i:i + 100]
        try:
            data = hubspot.post(
                "/crm/v3/objects/deals/batch/read",
                {"inputs": [{"id": did} for did in batch], "properties": [_HS_STAGE_PROP]},
            )
            for obj in data.get("results", []):
                raw = obj.get("properties", {}).get(_HS_STAGE_PROP, "")
                label = _HS_STAGE_MAP.get(raw, raw)
                internal = _HS_STAGE_TO_INT.get(label, label)
                hs_stages[obj["id"]] = internal
        except Exception as e:
            print(f"    Batch read failed: {e}")

    transitions = [
        d for d in active_deals
        if hs_stages.get(d.get(_D_ID, ""), "") in schema.CLOSED
    ]

    if not transitions:
        return [], 0

    print(f"  {len(transitions)} deals transitioned to closed")

    transition_hs_ids = [d[_D_ID] for d in transitions if d.get(_D_ID)]
    owners = _fetch_owners()
    company_map = _fetch_company_associations(transition_hs_ids)
    partner_map = _fetch_partner_associations(transition_hs_ids)

    hs_full: list[dict] = []
    for i in range(0, len(transition_hs_ids), 100):
        batch = transition_hs_ids[i:i + 100]
        try:
            data = hubspot.post(
                "/crm/v3/objects/deals/batch/read",
                {"inputs": [{"id": did} for did in batch], "properties": _HS_ALL_DEAL_PROPS},
            )
            hs_full.extend(data.get("results", []))
        except Exception as e:
            print(f"    Full property batch read failed: {e}")

    resolved_by_uuid: dict[str, dict] = {}
    for hd in hs_full:
        row = _resolve_deal(hd, owners, company_map, partner_map, allow_closed=True)
        if row:
            deal_id = row.get(_D_ID)
            if deal_id:
                resolved_by_uuid[deal_id] = row

    if resolved_by_uuid:
        rows_to_upsert = list(resolved_by_uuid.values())
        for i in range(0, len(rows_to_upsert), UPSERT_BATCH_SIZE):
            batch = rows_to_upsert[i:i + UPSERT_BATCH_SIZE]
            supabase.table(DEALS_TABLE).upsert(batch, on_conflict=DEALS_UPSERT_KEY).execute()
        print(f"  ✓ {len(resolved_by_uuid)} deals re-synced from HubSpot")

    # ── Worker function ──
    total = len(transitions)

    def _process_closed_deal(idx: int, deal: dict) -> str:
        deal_uuid = deal[_D_UUID]
        deal_name = deal.get(_D_NAME) or "?"
        hs_id = deal.get(_D_ID, "")
        new_stage = hs_stages.get(hs_id, "?")
        print(f"\n    [{idx}/{total}] [{deal_name[:40]}] {deal.get(_D_STAGE)} → {new_stage}", flush=True)

        for attempt in range(3):
            try:
                intelligence_run(deal_uuid)
                print(f"    ✓ Final snapshot: {deal_name[:40]}", flush=True)

                deal_fresh = (
                    supabase.table(_TBL_DEALS)
                    .select("*")
                    .eq(_D_UUID, deal_uuid)
                    .limit(1)
                    .execute()
                )
                if deal_fresh.data:
                    d = deal_fresh.data[0]
                    try:
                        traj = compile_trajectory(d)
                        if traj:
                            print(f"    ✓ Trajectory ({traj.get('outcome', '?')}): {deal_name[:40]}", flush=True)
                    except Exception as e:
                        print(f"    ✗ Trajectory failed: {deal_name[:40]}: {e}", flush=True)

                    try:
                        analysis = analyze_deal(d)
                        if analysis:
                            print(f"    ✓ Analysis done: {deal_name[:40]}", flush=True)
                    except Exception as e:
                        print(f"    ✗ Analysis failed: {deal_name[:40]}: {e}", flush=True)

                try:
                    parser2.update_from_sync(deal_uuid)
                    parser2.update_from_intelligence(deal_uuid)
                    parser2.update_from_forecast(deal_uuid)
                    parser2.update_from_daily(deal_uuid)
                except Exception as e:
                    print(f"    ✗ Parser failed: {deal_name[:40]}: {e}", flush=True)

                return deal_uuid
            except OSError as e:
                if e.errno == 11 and attempt < 2:
                    wait = 5 * (attempt + 1)
                    print(f"    ⟳ EAGAIN retry {attempt + 1}/2 for {deal_name[:40]} (waiting {wait}s)", flush=True)
                    time.sleep(wait)
                    continue
                raise

    # ── Parallel execution (bounded-submit, same pattern as core/run2.py) ──
    ok = 0
    fail = 0
    failures: list[str] = []
    closed_ids: list[str] = []
    timeout_seconds = DAILY_TIMEOUT_MINUTES * 60

    print(f"  Processing {total} closed deals (workers={DAILY_WORKERS})")

    with ThreadPoolExecutor(max_workers=DAILY_WORKERS) as pool:
        active: dict = {}
        deal_iter = enumerate(transitions, 1)
        stopped = False

        def _submit_next():
            nonlocal stopped
            if stopped:
                return
            elapsed = time.time() - start_time
            if elapsed > timeout_seconds:
                remaining = total - ok - fail - len(active)
                print(f"\n  ⏱ Timeout ({DAILY_TIMEOUT_MINUTES}min) — {ok + fail} done, {remaining} remaining for next run")
                stopped = True
                return
            try:
                i, deal = next(deal_iter)
                future = pool.submit(_process_closed_deal, i, deal)
                active[future] = deal.get(_D_NAME) or "?"
            except StopIteration:
                stopped = True

        for _ in range(DAILY_WORKERS):
            _submit_next()

        while active:
            done = next(as_completed(active))
            deal_name = active.pop(done)
            try:
                deal_uuid = done.result()
                ok += 1
                closed_ids.append(deal_uuid)
            except Exception as e:
                fail += 1
                failures.append(f"{deal_name}: {e}")
                print(f"  ✗ FAILED [{deal_name}]: {e}", flush=True)
                traceback.print_exc()

            _submit_next()

    if failures:
        print(f"  Closed failures ({fail}):")
        for f in failures:
            print(f"    - {f}")

    return closed_ids, fail


# ═══════════════════════════════════════════════════════════════════════════
# STEP 4 — Forecast refresh (imminent close dates)
# ═══════════════════════════════════════════════════════════════════════════

def _refresh_imminent_forecasts(start_time: float) -> tuple[list[str], int]:
    """Re-snapshot + re-forecast deals with close date within N days or past due.
    Returns (refreshed_ids, failed_count)."""

    today = date.today()
    threshold = (today + timedelta(days=_FORECAST_DAYS)).isoformat()
    cooldown = (today - timedelta(days=_FORECAST_COOLDOWN)).isoformat()

    resp = (
        supabase.table(_TBL_DEAL_UI)
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
        return [], 0

    total = len(candidates)
    print(f"  {total} deals to refresh (close date <= {threshold}, snapshot older than {cooldown})")

    # ── Worker function ──
    def _process_forecast_refresh(idx: int, deal_candidate: dict) -> str:
        deal_uuid = deal_candidate["deal_id"]
        deal_name = (deal_candidate.get("deal_name_full") or "?")[:50]
        old_date = deal_candidate.get("estimated_close_date") or "?"

        for attempt in range(3):
            try:
                intelligence_run(deal_uuid)
                result = forecast_run(deal_uuid, use_latest=True)
                new_date = result.get("estimated_close_date", "?") if result else "unchanged"
                print(f"    ✓ {deal_name} ({old_date} → {new_date})", flush=True)

                try:
                    parser2.update_from_intelligence(deal_uuid)
                    parser2.update_from_forecast(deal_uuid)
                except Exception as e:
                    print(f"    ✗ Parser failed for {deal_name}: {e}", flush=True)

                return deal_uuid
            except OSError as e:
                if e.errno == 11 and attempt < 2:
                    wait = 5 * (attempt + 1)
                    print(f"    ⟳ EAGAIN retry {attempt + 1}/2 for {deal_name} (waiting {wait}s)", flush=True)
                    time.sleep(wait)
                    continue
                raise

    # ── Parallel execution ──
    ok = 0
    fail = 0
    failures: list[str] = []
    refreshed_ids: list[str] = []
    timeout_seconds = DAILY_TIMEOUT_MINUTES * 60

    print(f"  Processing {total} forecast refreshes (workers={DAILY_WORKERS})")

    with ThreadPoolExecutor(max_workers=DAILY_WORKERS) as pool:
        active: dict = {}
        deal_iter = enumerate(candidates, 1)
        stopped = False

        def _submit_next():
            nonlocal stopped
            if stopped:
                return
            elapsed = time.time() - start_time
            if elapsed > timeout_seconds:
                remaining = total - ok - fail - len(active)
                print(f"\n  ⏱ Timeout ({DAILY_TIMEOUT_MINUTES}min) — {ok + fail} done, {remaining} remaining for next run")
                stopped = True
                return
            try:
                i, deal = next(deal_iter)
                future = pool.submit(_process_forecast_refresh, i, deal)
                active[future] = (deal.get("deal_name_full") or "?")[:50]
            except StopIteration:
                stopped = True

        for _ in range(DAILY_WORKERS):
            _submit_next()

        while active:
            done = next(as_completed(active))
            deal_name = active.pop(done)
            try:
                deal_uuid = done.result()
                ok += 1
                refreshed_ids.append(deal_uuid)
            except Exception as e:
                fail += 1
                failures.append(f"{deal_name}: {e}")
                print(f"  ✗ FAILED [{deal_name}]: {e}", flush=True)
                traceback.print_exc()

            _submit_next()

    if failures:
        print(f"  Forecast failures ({fail}):")
        for f in failures:
            print(f"    - {f}")

    return refreshed_ids, fail


# ═══════════════════════════════════════════════════════════════════════════
# ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════

def run():
    print("=" * 60)
    print("DAILY RUN v2")
    print(f"  workers={DAILY_WORKERS}, timeout={DAILY_TIMEOUT_MINUTES}min")
    print("=" * 60)

    start_time = time.time()

    # ── 1. Sync — full metadata refresh from HubSpot ──
    print("\n▸ STEP 1: SYNC")
    try:
        result = sync_run(full=True)
        synced = result.get("synced", 0) if isinstance(result, dict) else 0
        stale = result.get("stale", 0) if isinstance(result, dict) else 0
        print(f"  {synced} deals synced, {stale} marked stale")
    except Exception as e:
        print(f"  ✗ Sync failed: {e}")
        traceback.print_exc()

    # ── 2. Parser batch — deal_ui for ALL deals ──
    print("\n▸ STEP 2: PARSER BATCH")
    try:
        updated = _parser_batch_sync()
        print(f"  {updated} deals updated in deal_ui")
    except Exception as e:
        print(f"  ✗ Parser batch failed: {e}")
        traceback.print_exc()

    # ── 3. Closed deal detection ──
    closed_ids: list[str] = []
    closed_failed = 0
    print("\n▸ STEP 3: CLOSED DEAL DETECTION")
    try:
        closed_ids, closed_failed = _detect_and_process_closed(start_time)
        print(f"  {len(closed_ids)} closed deals processed, {closed_failed} failed")
    except Exception as e:
        print(f"  ✗ Closed detection failed: {e}")
        traceback.print_exc()

    # ── 4. Forecast refresh — imminent/past close dates ──
    refresh_ids: list[str] = []
    refresh_failed = 0
    print("\n▸ STEP 4: FORECAST REFRESH")
    try:
        refresh_ids, refresh_failed = _refresh_imminent_forecasts(start_time)
        print(f"  {len(refresh_ids)} forecasts refreshed, {refresh_failed} failed")
    except Exception as e:
        print(f"  ✗ Forecast refresh failed: {e}")
        traceback.print_exc()

    # ── Summary ──
    elapsed_min = round((time.time() - start_time) / 60, 1)
    print(f"\n{'=' * 60}")
    print(f"DAILY v2 DONE: {len(closed_ids)} closed, {len(refresh_ids)} refreshed ({elapsed_min}min)")
    if closed_failed or refresh_failed:
        print(f"  Failures: {closed_failed} closed, {refresh_failed} forecast")
    print("=" * 60)
