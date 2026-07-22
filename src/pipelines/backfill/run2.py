"""
Backfill v2 — process deals for a team or individual through the full v2 pipeline.

Usage:
    from src.pipelines.backfill.run2 import run
    run(team="DS Rubén")                    # backfill all deals for a team
    run(email="camila.vento@factorial.co")  # backfill one person's deals
    run(team="TIM")                         # works with partner teams too

Runs the full CORE v2 pipeline (sync2 → atlas2 → intelligence2 → forecast2 → parser2)
for every active deal. Includes retrospective BANT for deals past evaluation.
All v2 — zero v1 imports.

Ordered by stage priority (closing first) then MRR (highest first).
Does NOT mark context_stale — won't interfere with hourly CORE runs.
"""

import json
import re
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from src import org, schema
from src.config2 import (
    DEAL_NAME_EXCLUDE_PATTERNS,
    MODEL_DEFAULT,
    get_display_name,
    get_owner_ids_for_team,
)
from src.db.client import supabase
from src.integrations import claude, hubspot
from src.pipelines.core.atlas2 import generate as atlas_generate
from src.pipelines.core.forecast2 import run as forecast_run
from src.pipelines.core.intelligence2 import (
    run as intelligence_run,
    _write_pbd_snapshot,
    _fetch_previous_pbd_snapshot,
)
from src.pipelines.core import parser2
from src.pipelines.core.sync2 import (
    _ACTIVE_PIPELINE_FILTER,
    _HS_OWNER,
    _NOT_CLOSED,
    _batch_read_deals,
    _fetch_company_associations,
    _fetch_owners,
    _fetch_partner_associations,
    _resolve_deal,
    _search_all,
    _upsert_deals,
)


# ═══════════════════════════════════════════════════════════════════════════
# RESOLVED CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════

_TBL_DEALS = schema.tbl("deals")
_TBL_ATLAS = schema.tbl("atlas")

_D_UUID     = schema.col("deal_uuid")
_D_ID       = schema.col("deal_id")
_D_NAME     = schema.col("deal_name")
_D_STAGE    = schema.col("stage")
_D_CRM_ID   = schema.col("crm_id")
_D_TEAM     = schema.col("team")
_D_PAE      = schema.col("pae")
_D_PBD      = schema.col("pbd")
_D_AMOUNT   = schema.col("amount")
_D_ATLAS_ID = schema.col("atlas_ref")
_D_PIPELINE = schema.col("pipeline")
_D_CONTEXT  = schema.col("deal_context")

_A_FK_CRM   = schema.upsert_key("atlas")
_A_LAST_GEN = schema.ATLAS_COLS["last_generated"]

_ACTIVE_STAGES = list(schema.ACTIVE)
_SKIP_STAGES = schema.stages_for("prospecting") | schema.stages_for("nurturing")

_SELECT_COLS = ", ".join([
    _D_UUID, _D_ID, _D_NAME, _D_STAGE, _D_CRM_ID,
    _D_TEAM, _D_PAE, _D_PBD, _D_ATLAS_ID, _D_PIPELINE, _D_AMOUNT, _D_CONTEXT,
])

_STAGE_TO_CATEGORY: dict[str, str] = {}
for _internal, _meta in schema.STAGES.items():
    _STAGE_TO_CATEGORY[_internal] = _meta["category"]
for _label, _internal in org.CRM_STAGE_LABEL_TO_INTERNAL.items():
    _cat = schema.STAGES.get(_internal, {}).get("category")
    if _cat:
        _STAGE_TO_CATEGORY[_label] = _cat

BACKFILL_WORKERS = 2

# Pipeline name → stage date columns for evaluation entry (earliest = BANT cutoff)
_PIPELINE_EVAL_COLS: dict[str, list[str]] = {}
for _pid, _pinfo in org.CRM_PIPELINE_MAP.items():
    _prefix = _pinfo.get("prefix")
    if not _prefix:
        continue
    _cols = [
        f"{_prefix}_{stage}_entered"
        for stage in schema.EVALUATION
        if f"{_prefix}_{stage}_entered" in schema.STAGE_DATE_FIELDS
    ]
    if _cols:
        _PIPELINE_EVAL_COLS[_pinfo["name"]] = _cols

_BANT_PROMPT = """You are a sales qualification analyst. Evaluate the BANT qualification state of this deal based ONLY on the communications shown below. These are all communications that happened BEFORE the deal entered the evaluation stage.

Your job: assess how well the lead was qualified before the AE took over.

Cutoff date (deal entered evaluation): {cutoff_date}

Pre-evaluation communications:
{pre_eval_context}

Respond with ONLY this JSON — no other text:
{{
  "bant_b_status": "confirmed|partially_confirmed|not_confirmed|not_discussed",
  "bant_b_evidence": "1 short sentence",
  "bant_a_status": "confirmed|partially_confirmed|not_confirmed|not_discussed",
  "bant_a_evidence": "1 short sentence",
  "bant_n_status": "confirmed|partially_confirmed|not_confirmed|not_discussed",
  "bant_n_evidence": "1 short sentence",
  "bant_t_status": "confirmed|partially_confirmed|not_confirmed|not_discussed",
  "bant_t_evidence": "1 short sentence",
  "pbd_summary": "2-3 sentences summarizing the qualification state at handover"
}}"""


# ═══════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _deal_priority(deal: dict) -> int:
    cat = _STAGE_TO_CATEGORY.get(deal.get(_D_STAGE) or "", "")
    if cat == "closing":    return 0
    if cat == "evaluation": return 1
    if cat == "demo":       return 2
    return 3


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


def _sync_deals(owner_ids: list[str]) -> tuple[int, set[str]]:
    """Sync deals from HubSpot for given owner IDs. Returns (count_synced, deal_ids)."""
    deal_ids: set[str] = set()
    for i in range(0, len(owner_ids), 4):
        batch = owner_ids[i:i + 4]
        filter_groups = [{"filters": [
            {"propertyName": _HS_OWNER, "operator": "EQ", "value": oid},
            _NOT_CLOSED,
            _ACTIVE_PIPELINE_FILTER,
        ]} for oid in batch]
        deal_ids |= _search_all(filter_groups)

    if not deal_ids:
        return 0, set()

    deal_id_list = sorted(deal_ids)
    owners = _fetch_owners()
    hs_deals = _batch_read_deals(deal_id_list)
    company_map = _fetch_company_associations(deal_id_list)
    partner_map = _fetch_partner_associations(deal_id_list)

    rows = []
    for hd in hs_deals:
        row = _resolve_deal(hd, owners, company_map, partner_map)
        if row:
            rows.append(row)

    written = _upsert_deals(rows)
    return written, deal_ids


def _fetch_deals(deal_ids: set[str]) -> list[dict]:
    """Fetch deals from Supabase by deal_id, filtered to active stages."""
    all_deals: list[dict] = []
    id_list = sorted(deal_ids)
    for i in range(0, len(id_list), 500):
        batch = id_list[i:i + 500]
        resp = (
            supabase.table(_TBL_DEALS)
            .select(_SELECT_COLS)
            .in_(_D_ID, batch)
            .in_(_D_STAGE, _ACTIVE_STAGES)
            .execute()
        )
        all_deals.extend(resp.data or [])

    all_deals = [
        d for d in all_deals
        if not any(pat in (d.get(_D_NAME) or "").lower() for pat in DEAL_NAME_EXCLUDE_PATTERNS)
    ]

    return all_deals


# ═══════════════════════════════════════════════════════════════════════════
# RETROSPECTIVE BANT
# ═══════════════════════════════════════════════════════════════════════════

def _find_evaluation_cutoff(deal_uuid: str, pipeline_name: str) -> str | None:
    """Find when the deal first entered an evaluation stage. Returns ISO date or None."""
    eval_cols = _PIPELINE_EVAL_COLS.get(pipeline_name)
    if not eval_cols:
        return None

    select = ", ".join(eval_cols)
    resp = (
        supabase.table(_TBL_DEALS)
        .select(select)
        .eq(_D_UUID, deal_uuid)
        .limit(1)
        .execute()
    )
    if not resp.data:
        return None

    row = resp.data[0]
    dates = [row[c][:10] for c in eval_cols if row.get(c)]
    return min(dates) if dates else None


def _find_first_meeting_date(deal_context: str) -> str | None:
    """Fallback: find earliest meeting/demo date in deal_context."""
    matches = re.findall(r'\[(\d{4}-\d{2}-\d{2})\].*(?:MEETING|DEMO|Demo|CALL)', deal_context)
    return min(matches) if matches else None


def _generate_retrospective_bant(deal_uuid: str, deal: dict) -> bool:
    """Generate BANT for deals already past PBD/evaluation stage."""
    stage = deal.get(_D_STAGE) or ""
    if stage in schema.PBD_STAGES:
        return False

    hs_deal_id = deal.get(_D_ID) or ""
    existing = _fetch_previous_pbd_snapshot(hs_deal_id)
    if existing:
        return False

    deal_context = deal.get(_D_CONTEXT) or ""
    if not deal_context.strip():
        # Re-read from DB in case intelligence just wrote it
        resp = (
            supabase.table(_TBL_DEALS)
            .select(_D_CONTEXT)
            .eq(_D_UUID, deal_uuid)
            .limit(1)
            .execute()
        )
        if resp.data:
            deal_context = resp.data[0].get(_D_CONTEXT) or ""
    if not deal_context.strip():
        return False

    pipeline_name = deal.get(_D_PIPELINE) or ""
    cutoff = _find_evaluation_cutoff(deal_uuid, pipeline_name)
    if not cutoff:
        cutoff = _find_first_meeting_date(deal_context)
    if not cutoff:
        print(f"    BANT: no cutoff date found — skipping")
        return False

    pre_eval_lines = []
    for line in deal_context.split('\n'):
        date_match = re.match(r'\[(\d{4}-\d{2}-\d{2})\]', line)
        if date_match and date_match.group(1) >= cutoff:
            break
        pre_eval_lines.append(line)

    pre_eval_context = '\n'.join(pre_eval_lines).strip()
    if not pre_eval_context:
        print(f"    BANT: no pre-evaluation comms found — skipping")
        return False

    print(f"  ▸ BANT (retrospective, cutoff={cutoff}, {len(pre_eval_lines)} lines)")
    try:
        prompt = _BANT_PROMPT.format(cutoff_date=cutoff, pre_eval_context=pre_eval_context)
        response = claude.analyze("", prompt, model=MODEL_DEFAULT, max_tokens=2000)
        raw = response.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0]
        bant = json.loads(raw)
        today_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        ok = _write_pbd_snapshot(deal, bant, today_iso)
        if ok:
            print(f"    ✓ BANT done")
        return ok
    except Exception as e:
        print(f"    ✗ BANT failed: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def run(team: str | None = None, email: str | None = None, limit: int = 500):
    if bool(team) == bool(email):
        print("Provide exactly one of team= or email=")
        return

    # ── Resolve owner IDs ──
    if email:
        if email not in org.CRM_OWNER_MAP:
            print(f"  ✗ {email} not in CRM_OWNER_MAP — add it to org.py first")
            return
        owner_ids = [org.CRM_OWNER_MAP[email]["id"]]
        label = get_display_name(email)
        print("=" * 60)
        print(f"BACKFILL v2 — {label} ({email}) — limit={limit}")
        print("=" * 60)
    else:
        owner_ids = get_owner_ids_for_team(team)
        if not owner_ids:
            print(f"  ✗ No owner IDs for team '{team}' — check org.py + CRM_OWNER_MAP")
            return
        label = team
        print("=" * 60)
        print(f"BACKFILL v2 — {team} ({len(owner_ids)} owners) — limit={limit}")
        print("=" * 60)

    # ── 1. Sync from HubSpot ──
    print(f"\n▸ SYNC")
    hubspot.reset_counter()
    written, deal_ids = _sync_deals(owner_ids)
    print(f"  {len(deal_ids)} deals found, {written} synced to Supabase")
    print(f"  HubSpot API calls: {hubspot.total_requests()}")

    if not deal_ids:
        print(f"\n  No active deals for {label}")
        return

    # ── 2. Fetch + filter deals ──
    all_deals = _fetch_deals(deal_ids)
    demo_plus = [d for d in all_deals if d.get(_D_STAGE) not in _SKIP_STAGES]
    already_done = [d for d in demo_plus if (d.get(_D_CONTEXT) or "").strip()]
    deals = [d for d in demo_plus if not (d.get(_D_CONTEXT) or "").strip()][:limit]
    skipped_pre = len(all_deals) - len(demo_plus)

    deals.sort(key=lambda d: (
        _deal_priority(d),
        -(d.get(_D_AMOUNT) or 0),
    ))

    print(f"\n▸ {len(deals)} deals to process | {len(already_done)} already done | {skipped_pre} prospecting/nurturing skipped")

    if not deals:
        print(f"\n  Nothing to process for {label}")
        return

    # ── 3. Process deals ──
    ok = 0
    failed = 0
    skipped = 0
    failures: list[str] = []
    total = len(deals)

    def _process_deal(idx: int, deal: dict) -> str:
        deal_uuid = deal[_D_UUID]
        deal_name = deal.get(_D_NAME) or "?"
        crm_id = deal.get(_D_CRM_ID) or ""
        stage = deal.get(_D_STAGE) or "?"
        mrr = deal.get(_D_AMOUNT) or 0

        print(f"\n{'─' * 50}")
        print(f"  [{idx}/{total}] {deal_name[:50]}")
        print(f"  Stage: {stage} | MRR: €{mrr}", flush=True)

        try:
            # Parser sync
            try:
                parser2.update_from_sync(deal_uuid)
            except Exception as e:
                print(f"    Parser sync failed: {e}")

            # Atlas
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

            # Intelligence — loop until all comms processed
            print(f"  ▸ INTELLIGENCE")
            intel_result = None
            pass_num = 0
            while True:
                pass_num += 1
                result = intelligence_run(deal_uuid, max_comms=30, full_context=True)
                if not result:
                    break
                intel_result = result
                if not result.get("has_pending"):
                    break
                print(f"    pass {pass_num} done (more pending)")

            if intel_result:
                try:
                    parser2.update_from_intelligence(deal_uuid)
                except Exception as e:
                    print(f"    Parser intelligence failed: {e}")

                # Forecast
                if intel_result.get("snapshot"):
                    print(f"  ▸ FORECAST")
                    try:
                        forecast_result = forecast_run(deal_uuid)
                        if forecast_result:
                            parser2.update_from_forecast(deal_uuid)
                    except Exception as e:
                        print(f"    Forecast failed: {e}")

                # Retrospective BANT — only for deals past PBD that don't have one yet
                if not intel_result.get("pbd_snapshot"):
                    _generate_retrospective_bant(deal_uuid, deal)

                print(f"  ✓ Done", flush=True)
                return "ok"
            else:
                print(f"  ⏳ Skipped (no new comms)", flush=True)
                return "skipped"

        except Exception as e:
            print(f"  ✗ FAILED: {e}")
            traceback.print_exc()
            return f"failed:{deal_name[:30]}: {e}"

    with ThreadPoolExecutor(max_workers=BACKFILL_WORKERS) as pool:
        futures = {pool.submit(_process_deal, i, deal): deal for i, deal in enumerate(deals, 1)}
        for future in as_completed(futures):
            result = future.result()
            if result == "ok":
                ok += 1
            elif result == "skipped":
                skipped += 1
            elif result.startswith("failed:"):
                failed += 1
                failures.append(result[7:])

    print(f"\n{'=' * 60}")
    print(f"BACKFILL v2 {label}: {ok} OK, {skipped} skipped, {failed} failed")
    if failures:
        print("Failures:")
        for f in failures:
            print(f"  - {f}")
    print("=" * 60)
