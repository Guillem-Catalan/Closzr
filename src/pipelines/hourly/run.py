"""
Hourly Run — pre-CORE, runs at :30 every hour.

Steps:
  1. Detect meetings today per-team timezone (zero Claude, Supabase queries)
  2. Generate briefings for deals with meetings today (Claude Sonnet, only new ones)
  3. Generate email drafts for deals with EMAIL action (Claude Sonnet, only where needed)

Designed to be fast — only generates what doesn't exist yet.
"""

import traceback

from src.db.client import supabase
from src.pipelines.hourly.meetings import detect_today
from src.pipelines.hourly.briefings import run as briefings_run
from src.pipelines.hourly.email_drafts import run as email_drafts_run


def _sync_meeting_flags(deal_uuids: set[str]):
    """Set has_meeting_today=true for deals with meetings, false for stale ones."""
    # Reset yesterday's flags
    supabase.table("deal_ui").update({"has_meeting_today": False}).eq("has_meeting_today", True).execute()

    # Set today's flags
    uuids = list(deal_uuids)
    for i in range(0, len(uuids), 200):
        batch = [{"deal_id": uid, "has_meeting_today": True} for uid in uuids[i:i + 200]]
        supabase.table("deal_ui").upsert(batch, on_conflict="deal_id").execute()


def run():
    print("=" * 60)
    print("HOURLY RUN")
    print("=" * 60)

    # ── 1. Detect meetings today (timezone-aware per team) ──
    print("\n▸ MEETINGS TODAY")
    try:
        meetings_map = detect_today()
        print(f"  {len(meetings_map)} deals with meetings today")
        _sync_meeting_flags(set(meetings_map.keys()))
        print(f"  ✓ deal_ui flags synced")
    except Exception as e:
        print(f"  ✗ Meeting detection failed: {e}")
        traceback.print_exc()
        meetings_map = {}

    # ── 2. Briefings ──
    print("\n▸ BRIEFINGS")
    try:
        briefings_generated = briefings_run(meetings_map)
        print(f"  {briefings_generated} briefings generated")
    except Exception as e:
        print(f"  ✗ Briefings failed: {e}")
        traceback.print_exc()

    # ── 3. Email drafts ──
    print("\n▸ EMAIL DRAFTS")
    try:
        drafts_generated = email_drafts_run()
        print(f"  {drafts_generated} email drafts generated")
    except Exception as e:
        print(f"  ✗ Email drafts failed: {e}")
        traceback.print_exc()

    print(f"\n{'=' * 60}")
    print(f"HOURLY DONE")
    print("=" * 60)
