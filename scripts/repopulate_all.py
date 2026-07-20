"""
Repopulate all deals (v2) — re-fetch properties from HubSpot + re-parse deal_ui.

Source: deals already in Supabase (~32K).
Does NOT search HubSpot for new deals — only refreshes what we already track.

Phase 1 (sync):
  - Reads all deal_id (HS IDs) from Supabase
  - Batch-reads ALL 226 properties from HubSpot for each deal
  - Resolves via v2: team, pipeline, owner, amount, after_demo_date, stage dates, etc.
  - Runs _detect_stale ONLY on open deals (not in schema.CLOSED)
  - Closed deals get properties updated but no stale marking
  - Upserts everything back to Supabase

Phase 2 (parse):
  - Re-parses ALL deals → deal_ui via parser2.update_batch_from_sync()

Usage:
  python scripts/repopulate_all.py              # both phases
  python scripts/repopulate_all.py --sync-only   # phase 1 only
  python scripts/repopulate_all.py --parse-only  # phase 2 only
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from src import schema
from src.config2 import ACTIVE_TEAMS
from src.db.client import supabase
from src.integrations import hubspot
from src.pipelines.core.sync2 import (
    DEALS_TABLE,
    COL_DEAL_ID,
    COL_STAGE,
    COL_STALE,
    COL_STALE_CHECKED,
    COL_TEAM,
    _fetch_owners,
    _batch_read_deals,
    _fetch_company_associations,
    _fetch_partner_associations,
    _resolve_deal,
    _upsert_deals,
)


def _read_all_deal_ids() -> list[str]:
    """Read all HS deal IDs from Supabase."""
    all_ids = []
    offset = 0
    while True:
        resp = (
            supabase.table(DEALS_TABLE)
            .select(COL_DEAL_ID)
            .range(offset, offset + 999)
            .execute()
        )
        batch = resp.data or []
        all_ids.extend(r[COL_DEAL_ID] for r in batch if r.get(COL_DEAL_ID))
        if len(batch) < 1000:
            break
        offset += 1000
    return all_ids


def phase_sync():
    print("=" * 60)
    print("PHASE 1: SYNC ALL DEALS FROM SUPABASE (v2)")
    print("=" * 60)

    hubspot.reset_counter()

    # 1. Read deal IDs from Supabase
    print("\n1. Reading deal IDs from Supabase...")
    deal_ids = _read_all_deal_ids()
    if not deal_ids:
        print("   No deals found in Supabase.")
        return
    print(f"   {len(deal_ids)} deals to refresh")

    # 2. Fetch owners
    print("\n2. Fetching HubSpot owners...")
    owners = _fetch_owners()
    print(f"   {len(owners)} owners loaded")

    # 3. Batch read ALL properties from HubSpot
    deal_id_list = sorted(set(deal_ids))
    print(f"\n3. Fetching {len(deal_id_list)} deals from HubSpot (226 properties each)...")
    hs_deals = _batch_read_deals(deal_id_list)
    print(f"   {len(hs_deals)} deals read")

    # 4. Fetch associations
    print("\n4. Fetching associations...")
    print("   Company associations...")
    company_map = _fetch_company_associations(deal_id_list)
    print(f"   {len(company_map)} company links")
    print("   Partner associations...")
    partner_map = _fetch_partner_associations(deal_id_list)
    print(f"   {len(partner_map)} partner links")

    # 5. Resolve ALL deals (allow_closed=True so closed deals get properties too)
    print("\n5. Resolving deals (allow_closed=True)...")
    rows = []
    skipped = 0
    for hd in hs_deals:
        row = _resolve_deal(hd, owners, company_map, partner_map, allow_closed=True)
        if row:
            rows.append(row)
        else:
            skipped += 1
    print(f"   {len(rows)} resolved, {skipped} excluded (bad pipeline/stage)")

    # 6. Strip stale columns — repopulate never touches stale
    for row in rows:
        row.pop(COL_STALE, None)
        row.pop(COL_STALE_CHECKED, None)

    # 7. Upsert all
    print(f"\n6. Upserting {len(rows)} deals...")
    written = _upsert_deals(rows)
    print(f"   {written} deals upserted")

    print(f"\n   HubSpot API requests: {hubspot.total_requests()}")
    print("=" * 60)


def phase_parse():
    from src.pipelines.core.parser2 import update_batch_from_sync

    print("=" * 60)
    print("PHASE 2: RE-PARSE ALL DEALS → deal_ui")
    print("=" * 60)

    col_uuid = schema.col("deal_uuid")

    print("\n1. Fetching all deal UUIDs from Supabase...")
    all_uuids = []
    offset = 0
    while True:
        resp = (
            supabase.table(DEALS_TABLE)
            .select(col_uuid)
            .range(offset, offset + 999)
            .execute()
        )
        batch = resp.data or []
        all_uuids.extend(r[col_uuid] for r in batch if r.get(col_uuid))
        if len(batch) < 1000:
            break
        offset += 1000
    print(f"   {len(all_uuids)} deals to parse")

    if not all_uuids:
        print("   Nothing to parse.")
        return

    print("\n2. Running update_batch_from_sync...")
    written = update_batch_from_sync(all_uuids)
    print(f"   {written} deal_ui rows written")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Repopulate all deals (v2)")
    parser.add_argument("--sync-only", action="store_true", help="Run only Phase 1 (sync)")
    parser.add_argument("--parse-only", action="store_true", help="Run only Phase 2 (parse)")
    args = parser.parse_args()

    if args.parse_only:
        phase_parse()
    elif args.sync_only:
        phase_sync()
    else:
        phase_sync()
        phase_parse()

    print("\nDONE")


if __name__ == "__main__":
    main()
