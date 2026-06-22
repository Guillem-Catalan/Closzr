"""
Weekly Run — domingos 18:00 CEST.

Steps:
  1. Patterns — generate/update statistical + text patterns from trajectories

More steps to be added later (TL reports, pipeline review, etc.)
Everything from config.
"""

import traceback

from src.pipelines.weekly.patterns import run as patterns_run


def run():
    print("=" * 60)
    print("WEEKLY RUN")
    print("=" * 60)

    # ── 1. Patterns ──
    print("\n▸ PATTERNS")
    try:
        total = patterns_run()
        print(f"  {total} patterns generated/updated")
    except Exception as e:
        print(f"  ✗ Patterns failed: {e}")
        traceback.print_exc()

    print(f"\n{'=' * 60}")
    print(f"WEEKLY DONE")
    print("=" * 60)
