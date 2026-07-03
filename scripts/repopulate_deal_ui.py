"""
Repopulate deal_ui for all active deals.

Runs all 5 parser entry points per deal:
  1. update_from_sync      — HubSpot metadata (stage, dates, owner)
  2. update_from_atlas     — company card
  3. update_from_intelligence — deal_context, assessment, signals
  4. update_from_forecast  — forecast, close dates, momentum
  5. update_from_daily     — deal_analysis, trajectories, lessons

Run: python scripts/repopulate_deal_ui.py
"""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.db.client import supabase
from src.pipelines.core.parser import (
    update_from_sync,
    update_from_atlas,
    update_from_intelligence,
    update_from_forecast,
    update_from_daily,
)

BATCH = 500


def fetch_all_deal_ids():
    ids = []
    offset = 0
    while True:
        resp = (
            supabase.table("deals")
            .select("id")
            .not_.in_("macro_stage", ["closed_won", "closed_lost"])
            .range(offset, offset + BATCH - 1)
            .execute()
        )
        batch = resp.data or []
        ids.extend(r["id"] for r in batch)
        if len(batch) < BATCH:
            break
        offset += BATCH
    return ids


def run():
    print("=" * 60)
    print("REPOPULATE DEAL_UI — all 5 parser entry points")
    print("=" * 60)

    deal_ids = fetch_all_deal_ids()
    print(f"\n{len(deal_ids)} active deals to process\n")

    steps = [
        ("sync", update_from_sync),
        ("atlas", update_from_atlas),
        ("intelligence", update_from_intelligence),
        ("forecast", update_from_forecast),
        ("daily", update_from_daily),
    ]

    errors = []
    t0 = time.time()

    for i, deal_id in enumerate(deal_ids, 1):
        for name, fn in steps:
            try:
                fn(deal_id)
            except Exception as e:
                errors.append((deal_id, name, str(e)))

        if i % 50 == 0:
            elapsed = time.time() - t0
            rate = i / elapsed
            eta = (len(deal_ids) - i) / rate if rate > 0 else 0
            print(f"  {i}/{len(deal_ids)} deals  ({rate:.1f}/s, ETA {eta:.0f}s)  errors: {len(errors)}")

    elapsed = time.time() - t0
    print(f"\nDone: {len(deal_ids)} deals in {elapsed:.0f}s")
    if errors:
        print(f"\n{len(errors)} errors:")
        for did, step, msg in errors[:20]:
            print(f"  {did} [{step}]: {msg}")
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more")
    print("=" * 60)


if __name__ == "__main__":
    run()
