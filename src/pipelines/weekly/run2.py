"""
Weekly Run v2 — domingos 18:00 CEST.

Steps:
  1. Patterns — generate/update statistical + text patterns from trajectories

Internal names everywhere: schema.tbl(), schema.col(), config2.*.
"""

import traceback

from src.pipelines.weekly.patterns2 import run as patterns_run
from src.pipelines.weekly.rep_stats import run as rep_stats_run


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

    print(f"\n{'=' * 60}")
    print("WEEKLY v2 DONE")
    print("=" * 60)
