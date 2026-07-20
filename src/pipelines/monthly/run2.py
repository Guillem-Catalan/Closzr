"""
Monthly Run v2 — día 1 de cada mes, 06:00 CEST.

Steps:
  1. Calibration — compare last month's forecasts vs actual results

Internal names everywhere: schema.tbl(), schema.col(), config2.*.
"""

import traceback

from src.pipelines.monthly.calibration2 import run as calibration_run


def run(target_month: str | None = None):
    print("=" * 60)
    print("MONTHLY RUN v2")
    print("=" * 60)

    # ── 1. Calibration ──
    print("\n▸ CALIBRATION")
    try:
        total = calibration_run(target_month)
        print(f"  {total} calibration entries written")
    except Exception as e:
        print(f"  ✗ Calibration failed: {e}")
        traceback.print_exc()

    print(f"\n{'=' * 60}")
    print("MONTHLY v2 DONE")
    print("=" * 60)
