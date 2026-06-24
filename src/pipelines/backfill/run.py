"""
Backfill Team — process all deals for a team from scratch.

Usage:
    from src.pipelines.backfill.run import run
    run("TIM")          # backfill TIM
    run("TELEKOM")      # backfill TELEKOM
    run("Santander")    # any team name from config

Runs the full CORE pipeline (sync → atlas → intelligence → forecast → parser)
for every active deal of the team. 2 Claude calls per deal (Sonnet + Opus).

Ordered by stage priority (advanced first) then MRR (highest first).
Does NOT mark context_stale — won't interfere with hourly CORE runs.
Everything from config.
"""

import json
import re
import traceback
from datetime import date

from src.config import (
    INTELLIGENCE_CONFIG,
    ACTIVE_STAGES,
    STAGE_CLOSING,
    STAGE_EVALUATION,
    STAGE_DEMO,
    STAGE_PROSPECTING,
    PBD_STAGES,
    ALL_PARTNER_DOMAINS,
    PARTNERS_ORGCHART,
    PARTNER_OBJECT_TYPE_ID,
    SYNC_CONFIG,
    CORE_TRIGGER,
    HS_DEAL_PROPS,
    HS_PIPELINE_DATE_MAP,
    HS_ALL_DEAL_PROPS,
    HUBSPOT_PIPELINE_IDS,
    EXCLUDE_PIPELINE_IDS,
    STAGE_ID_TO_LABEL,
    STAGES_EXCLUDE_FROM_SYNC_LOWER,
    UPSERT_BATCH_SIZE,
    ATLAS_CONFIG,
    MODEL_DEFAULT,
    get_deal_team,
    get_email_by_owner_id,
    get_display_name,
    get_owner_ids_for_team,
)
from src.db.client import supabase
from src.integrations import hubspot
from src.integrations import claude
from src.pipelines.core.sync import (
    _search_all,
    _NOT_CLOSED,
    _fetch_owners,
    _batch_read_deals,
    _fetch_company_associations,
    _fetch_partner_associations,
    _resolve_deal,
    _upsert_deals,
)
from src.pipelines.core.atlas import generate as atlas_generate
from src.pipelines.core.intelligence import run as intelligence_run, _write_pbd_snapshot
from src.pipelines.core.forecast import run as forecast_run
from src.pipelines.core import parser

_I = INTELLIGENCE_CONFIG

STAGE_PRIORITY = {s: 1 for s in STAGE_CLOSING}
STAGE_PRIORITY.update({s: 2 for s in STAGE_EVALUATION})
STAGE_PRIORITY.update({s: 3 for s in STAGE_DEMO})
STAGE_PRIORITY.update({s: 4 for s in STAGE_PROSPECTING})

_BANT_PROMPT = """You are a sales qualification analyst. Evaluate the BANT qualification state of this deal based ONLY on interactions that happened BEFORE the first demo/meeting date shown below.

The deal is now past the PBD/qualification stage, but we need a retrospective BANT analysis of how well the lead was qualified before handover to the AE.

BANT cutoff date (first meeting): {cutoff_date}
Only consider interactions BEFORE this date for your BANT evaluation.

Deal context (full history):
{deal_context}

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


def _find_first_meeting_date(deal_context: str) -> str | None:
    """Find the date of the first meeting in deal_context."""
    matches = re.findall(r'\[(\d{4}-\d{2}-\d{2})\].*(?:MEETING|DEMO|Demo)', deal_context)
    return min(matches) if matches else None


def _generate_retrospective_bant(deal: dict):
    """Generate BANT for deals already past PBD stage."""
    stage = deal.get(_I["deal_col_stage"]) or ""
    if stage in PBD_STAGES:
        return

    existing = (
        supabase.table(_I["pbd_snapshot_table"])
        .select("id")
        .eq(_I["fk_hs_deal_id"], deal.get(_I["deal_col_deal_id"]))
        .limit(1)
        .execute()
    )
    if existing.data:
        return

    deal_context = deal.get(_I["deal_context_col"]) or ""
    if not deal_context.strip():
        return

    cutoff = _find_first_meeting_date(deal_context)
    if not cutoff:
        return

    # Only send deal_context lines BEFORE the cutoff date
    pre_cutoff_lines = []
    for line in deal_context.split('\n'):
        date_match = re.match(r'\[(\d{4}-\d{2}-\d{2})\]', line)
        if date_match and date_match.group(1) >= cutoff:
            break
        pre_cutoff_lines.append(line)
    pre_cutoff_context = '\n'.join(pre_cutoff_lines).strip()
    if not pre_cutoff_context:
        return

    print(f"  ▸ BANT (retrospective, cutoff={cutoff}, {len(pre_cutoff_lines)} lines)")
    try:
        prompt = _BANT_PROMPT.format(cutoff_date=cutoff, deal_context=pre_cutoff_context)
        response = claude.analyze("", prompt, model=MODEL_DEFAULT, max_tokens=2000)
        raw = response.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0]
        bant = json.loads(raw)
        _write_pbd_snapshot(deal, bant)
        print(f"    ✓ BANT done")
    except Exception as e:
        print(f"    ✗ BANT failed: {e}")


def _fetch_team_deals(team: str) -> list[dict]:
    """Fetch all active deals for a team, ordered by stage priority + MRR."""
    stages = list(ACTIVE_STAGES)

    resp = (
        supabase.table(_I["deals_table"])
        .select("*")
        .eq(_I["deal_col_team"], team)
        .in_(_I["deal_col_stage"], stages)
        .execute()
    )
    deals = resp.data or []

    # Filter out partner company deals
    filtered = []
    for d in deals:
        deal_name = (d.get(_I["deal_col_deal_name"]) or "").lower()
        exclude = _I.get("deal_name_exclude_patterns", [])
        if any(pat in deal_name for pat in exclude):
            continue
        filtered.append(d)

    # Sort: advanced stages first, then highest MRR
    filtered.sort(key=lambda d: (
        STAGE_PRIORITY.get(d.get(_I["deal_col_stage"]) or "", 99),
        -(d.get(_I["deal_col_amount"]) or 0),
    ))

    return filtered


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


def run(team: str, limit: int = 500):
    """Backfill all deals for a team through the full CORE pipeline."""
    print("=" * 60)
    print(f"BACKFILL — {team} — limit={limit}")
    print("=" * 60)

    # Validate team exists
    from src.config import PARTNERS_ORGCHART, DIRECT_SALES_ES, XL_SALES
    valid_teams = set(PARTNERS_ORGCHART.keys())
    if DIRECT_SALES_ES:
        valid_teams |= set(DIRECT_SALES_ES.get("teams", {}).keys())
    valid_teams.add("XL")

    if team not in valid_teams:
        print(f"  Unknown team: {team}")
        print(f"  Available: {sorted(valid_teams)}")
        return

    # ── 1. Sync team deals (independent of ACTIVE_TEAMS) ──
    print(f"\n▸ SYNC {team}")
    hubspot.reset_counter()
    oids = get_owner_ids_for_team(team)
    if not oids:
        print(f"  No owner IDs for {team}")
        return
    print(f"  {len(oids)} owners")

    # Search by owner, NOT closed
    deal_ids: set[str] = set()
    _SC = SYNC_CONFIG
    for i in range(0, len(oids), 5):
        batch = oids[i:i + 5]
        filter_groups = [{"filters": [
            {"propertyName": _SC["hs_owner_id_prop"], "operator": "EQ", "value": oid},
            _NOT_CLOSED,
        ]} for oid in batch]
        deal_ids |= _search_all(filter_groups)
    print(f"  {len(deal_ids)} deals found")

    if deal_ids:
        deal_id_list = sorted(deal_ids)
        owners = _fetch_owners()
        hs_deals = _batch_read_deals(deal_id_list)
        company_map = _fetch_company_associations(deal_id_list)
        partner_map = _fetch_partner_associations(deal_id_list)
        print(f"  {len(hs_deals)} read, {len(company_map)} companies, {len(partner_map)} partners")

        rows = []
        for hd in hs_deals:
            row = _resolve_deal(hd, owners, company_map, partner_map)
            if row:
                row.pop("context_stale", None)
                rows.append(row)

        written = _upsert_deals(rows)
        print(f"  {written} deals synced to Supabase")
    print(f"  HubSpot API calls: {hubspot.total_requests()}")

    # ── 2. Fetch team deals ──
    all_deals = _fetch_team_deals(team)
    if not all_deals:
        print(f"\n  No active deals for {team}")
        return

    # Only process demo+ stages (Demo, Evaluation, Closing)
    # Prospecting + Nurturing are synced but wait for CORE on new activity
    skip_stages = STAGE_PROSPECTING | STAGE_NURTURING
    deals = [d for d in all_deals if d.get(_I["deal_col_stage"]) not in skip_stages][:limit]
    skipped_pbd = len(all_deals) - len([d for d in all_deals if d.get(_I["deal_col_stage"]) not in skip_stages])
    print(f"\n▸ {len(deals)} deals to process (demo+) | {skipped_pbd} prospecting/nurturing synced, waiting for CORE")

    ok = 0
    failed = 0
    skipped = 0
    failures: list[str] = []

    for i, deal in enumerate(deals, 1):
        deal_uuid = deal[_I["deal_col_id"]]
        deal_name = deal.get(_I["deal_col_deal_name"]) or "?"
        stage = deal.get(_I["deal_col_stage"]) or "?"
        mrr = deal.get(_I["deal_col_amount"]) or 0

        print(f"\n{'─' * 50}")
        print(f"  [{i}/{len(deals)}] {deal_name[:50]}")
        print(f"  Stage: {stage} | MRR: €{mrr}")

        try:
            # Atlas
            if _needs_atlas(deal):
                crm_id = deal.get(_I["deal_col_crm_id"])
                print(f"  ▸ ATLAS")
                try:
                    atlas_row = (
                        supabase.table(_I["atlas_table"])
                        .select("id")
                        .eq(_I["fk_crm_id"], crm_id)
                        .maybe_single()
                        .execute()
                    )
                    atlas_id = atlas_row.data["id"] if atlas_row.data else ""
                    if atlas_id:
                        atlas_generate(atlas_id, crm_id)
                except Exception as e:
                    print(f"    Atlas failed: {e}")

            # Intelligence — 50 comms per pass, loop until all processed
            print(f"  ▸ INTELLIGENCE")
            intel_result = None
            pass_num = 0
            while True:
                pass_num += 1
                result = intelligence_run(deal_uuid, max_comms=30, max_tokens=32000)
                if not result:
                    break
                intel_result = result
                if not result.get("has_pending"):
                    break
                print(f"    pass {pass_num} done (more pending)")

            if intel_result:
                # Forecast
                if intel_result.get("snapshot"):
                    print(f"  ▸ FORECAST")
                    try:
                        forecast_run(deal_uuid)
                    except Exception as e:
                        print(f"    Forecast failed: {e}")

                # Retrospective BANT (if deal past PBD and no BANT exists)
                _generate_retrospective_bant(deal)

                # Parser: all entry points
                try:
                    parser.update_from_sync(deal_uuid)
                    parser.update_from_atlas(deal_uuid)
                    parser.update_from_intelligence(deal_uuid)
                    parser.update_from_forecast(deal_uuid)
                except Exception as e:
                    print(f"    Parser failed: {e}")

                ok += 1
                print(f"  ✓ Done")
            else:
                skipped += 1
                print(f"  ⏳ Skipped (no new comms or pending)")

        except Exception as e:
            failed += 1
            failures.append(f"{deal_name[:30]}: {e}")
            print(f"  ✗ FAILED: {e}")
            traceback.print_exc()

    print(f"\n{'=' * 60}")
    print(f"BACKFILL {team}: {ok} OK, {skipped} skipped, {failed} failed")
    if failures:
        print("Failures:")
        for f in failures:
            print(f"  - {f}")
    print("=" * 60)
