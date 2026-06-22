"""
Monthly Run — day 1 of each month.

Steps:
  1. Calibration — compare last month's forecast predictions vs actual results

Everything from config.
"""

import traceback

from src.pipelines.monthly.calibration import run as calibration_run


def run(target_month: str | None = None):
    print("=" * 60)
    print("MONTHLY RUN")
    print("=" * 60)

    # ── 1. Calibration ──
    print("\n▸ CALIBRATION")
    try:
        entries = calibration_run(target_month)
        print(f"  {entries} calibration entries written")
    except Exception as e:
        print(f"  ✗ Calibration failed: {e}")
        traceback.print_exc()

    print(f"\n{'=' * 60}")
    print(f"MONTHLY DONE")
    print("=" * 60)
