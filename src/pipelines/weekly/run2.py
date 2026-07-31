"""
Weekly Run v2 — domingos 18:00 CEST.

Steps:
  1. Patterns — generate/update statistical + text patterns from trajectories
  2. Rep Stats — per-rep performance metrics (segments A-H)
  3. Team Stats — per-team benchmark aggregates from rep stats
  4. Coaching Alerts — per-rep alerts comparing vs team benchmarks

Internal names everywhere: schema.tbl(), schema.col(), config2.*.
"""

import traceback

from src.pipelines.weekly.patterns2 import run as patterns_run
from src.pipelines.weekly.rep_stats import run as rep_stats_run
from src.pipelines.weekly.rep_stats import run_alerts as rep_alerts_run
from src.pipelines.weekly.team_stats import run as team_stats_run


def run():
    print("=" * 60)
    print("WEEKLY RUN v2")
    print("=" * 60)

    # ── 1. Patterns ──
    print("\n▸ PATTERNS")
    try:
        total = patterns_run()
        print(f"  {total} patterns generated/updated")
    except Exception as e:
        print(f"  ✗ Patterns failed: {e}")
        traceback.print_exc()

    # ── 2. Rep Stats ──
    print("\n▸ REP STATS")
    try:
        total = rep_stats_run()
        print(f"  {total} rep patterns generated/updated")
    except Exception as e:
        print(f"  ✗ Rep Stats failed: {e}")
        traceback.print_exc()

    # ── 3. Team Stats ──
    print("\n▸ TEAM STATS")
    try:
        total = team_stats_run()
        print(f"  {total} team patterns generated/updated")
    except Exception as e:
        print(f"  ✗ Team Stats failed: {e}")
        traceback.print_exc()

    # ── 4. Coaching Alerts ──
    print("\n▸ COACHING ALERTS")
    try:
        total = rep_alerts_run()
        print(f"  {total} alerts generated/updated")
    except Exception as e:
        print(f"  ✗ Coaching Alerts failed: {e}")
        traceback.print_exc()

    print(f"\n{'=' * 60}")
    print("WEEKLY v2 DONE")
    print("=" * 60)
