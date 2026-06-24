"""
One-time script: populate all new deal columns without triggering stale.

What it does:
  1. Full HubSpot search (all active teams, no date filter)
  2. Fetch all deal properties (229 columns)
  3. Resolve team, PAE, PBD
  4. Upsert to Supabase WITHOUT touching context_stale
  5. For deals with context_stale=False: set last_activity_hs to current HubSpot value
  6. For deals with context_stale=True: leave last_activity_hs untouched

Run once: python scripts/populate_deals.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.config import (
    ACTIVE_TEAMS,
    SYNC_CONFIG,
    CORE_TRIGGER,
    UPSERT_BATCH_SIZE,
)
from src.db.client import supabase
from src.integrations import hubspot

_SC = SYNC_CONFIG
_CT = CORE_TRIGGER


def run():
    print("=" * 60)
    print("POPULATE DEALS — one-time, no stale marking")
    print("=" * 60)

    hubspot.reset_counter()

    # ── 1. Import sync internals ──
    from src.pipelines.core.sync import (
        _find_deal_ids,
        _fetch_owners,
        _batch_read_deals,
        _fetch_company_associations,
        _fetch_partner_associations,
        _resolve_deal,
    )

    # ── 2. Search all deals ──
    print("\n1. Searching HubSpot (full, no cutoff)...")
    deal_ids = _find_deal_ids(since_ms=None)
    if not deal_ids:
        print("   No deals found.")
        return
    print(f"   {len(deal_ids)} deals found")

    # ── 3. Fetch properties ──
    deal_id_list = sorted(deal_ids)
    print("\n2. Fetching owners...")
    owners = _fetch_owners()
    print(f"   {len(owners)} owners")

    print(f"\n3. Fetching properties for {len(deal_id_list)} deals...")
    hs_deals = _batch_read_deals(deal_id_list)
    print(f"   {len(hs_deals)} deals read")

    print("\n4. Fetching company associations...")
    company_map = _fetch_company_associations(deal_id_list)
    print(f"   {len(company_map)} company links")

    print("   Fetching partner associations...")
    partner_map = _fetch_partner_associations(deal_id_list)
    print(f"   {len(partner_map)} partner links")

    # ── 4. Resolve deals ──
    print("\n5. Resolving deals...")
    rows = []
    skipped = 0
    for hd in hs_deals:
        row = _resolve_deal(hd, owners, company_map, partner_map)
        if row:
            rows.append(row)
        else:
            skipped += 1
    print(f"   {len(rows)} resolved, {skipped} excluded")

    # ── 5. Get current stale status BEFORE upsert ──
    print("\n6. Reading current context_stale status...")
    stale_deal_ids = set()
    offset = 0
    while True:
        resp = (
            supabase.table(_SC["deals_table"])
            .select(f"{_SC['col_deal_id']}")
            .eq(_SC["col_context_stale"], True)
            .range(offset, offset + 999)
            .execute()
        )
        batch = resp.data or []
        stale_deal_ids |= {r[_SC["col_deal_id"]] for r in batch}
        if len(batch) < 1000:
            break
        offset += 1000
    print(f"   {len(stale_deal_ids)} deals currently stale (will preserve)")

    # ── 6. Remove context_stale and conditionally remove last_activity_hs ──
    activity_col = _CT["supabase_column"]

    for row in rows:
        # Never touch context_stale
        row.pop(_SC["col_context_stale"], None)

        # For stale deals: don't set last_activity_hs (leave NULL so CORE catches it)
        deal_id = row.get(_SC["col_deal_id"])
        if deal_id in stale_deal_ids:
            row.pop(activity_col, None)

    # ── 7. Upsert ──
    print(f"\n7. Upserting {len(rows)} deals...")
    written = 0
    for i in range(0, len(rows), UPSERT_BATCH_SIZE):
        batch = rows[i:i + UPSERT_BATCH_SIZE]
        result = (
            supabase.table(_SC["deals_table"])
            .upsert(batch, on_conflict=_SC["deals_upsert_key"])
            .execute()
        )
        written += len(result.data or [])
        if (i + UPSERT_BATCH_SIZE) % 1000 < UPSERT_BATCH_SIZE:
            print(f"   {written} deals upserted...")
    print(f"   {written} total deals upserted")

    # ── 8. Verify ──
    print(f"\n9. Verifying...")
    verify_stale = (
        supabase.table(_SC["deals_table"])
        .select("id", count="exact")
        .eq(_SC["col_context_stale"], True)
        .execute()
    )
    stale_after = verify_stale.count or 0
    print(f"   Stale deals before: {len(stale_deal_ids)}")
    print(f"   Stale deals after:  {stale_after}")

    team_check = (
        supabase.table(_SC["deals_table"])
        .select("id", count="exact")
        .not_.is_("team", "null")
        .execute()
    )
    print(f"   Deals with team:    {team_check.count or 0}")

    print(f"\n   HubSpot API requests: {hubspot.total_requests()}")
    print("=" * 60)
    print("DONE")
    print("=" * 60)


if __name__ == "__main__":
    run()
