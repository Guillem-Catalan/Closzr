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

import traceback

from src.config import (
    INTELLIGENCE_CONFIG,
    ACTIVE_STAGES,
    STAGE_CLOSING,
    STAGE_EVALUATION,
    STAGE_DEMO,
    STAGE_PROSPECTING,
    ALL_PARTNER_DOMAINS,
    PARTNERS_ORGCHART,
)
from src.db.client import supabase
from src.pipelines.core.sync import run as sync_run
from src.pipelines.core.atlas import generate as atlas_generate
from src.pipelines.core.intelligence import run as intelligence_run
from src.pipelines.core.forecast import run as forecast_run
from src.pipelines.core import parser

_I = INTELLIGENCE_CONFIG

STAGE_PRIORITY = {s: 1 for s in STAGE_CLOSING}
STAGE_PRIORITY.update({s: 2 for s in STAGE_EVALUATION})
STAGE_PRIORITY.update({s: 3 for s in STAGE_DEMO})
STAGE_PRIORITY.update({s: 4 for s in STAGE_PROSPECTING})


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

    # ── 1. Full sync ──
    print(f"\n▸ SYNC")
    try:
        sync_run(full=True)
    except Exception as e:
        print(f"  Sync failed: {e} — continuing with existing data")
        traceback.print_exc()

    # ── 2. Fetch team deals ──
    deals = _fetch_team_deals(team)
    if not deals:
        print(f"\n  No active deals for {team}")
        return

    deals = deals[:limit]
    print(f"\n▸ {len(deals)} deals to process")

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
                    atlas_generate("", crm_id)
                except Exception as e:
                    print(f"    Atlas failed: {e}")

            # Intelligence
            print(f"  ▸ INTELLIGENCE")
            intel_result = intelligence_run(deal_uuid)

            if intel_result:
                # Parser: intelligence
                try:
                    parser.update_from_intelligence(deal_uuid)
                except Exception as e:
                    print(f"    Parser intelligence failed: {e}")

                # Forecast
                if intel_result.get("snapshot"):
                    print(f"  ▸ FORECAST")
                    try:
                        forecast_run(deal_uuid)
                        parser.update_from_forecast(deal_uuid)
                    except Exception as e:
                        print(f"    Forecast failed: {e}")

                # Parser: sync metadata
                try:
                    parser.update_from_sync(deal_uuid)
                except Exception as e:
                    print(f"    Parser sync failed: {e}")

                # Parser: atlas
                try:
                    parser.update_from_atlas(deal_uuid)
                except Exception as e:
                    print(f"    Parser atlas failed: {e}")

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
