"""
Weekly Run v2 — stats pipeline orchestrator.

Schedules:
  - Sunday 03:00 UTC (05:00 CEST / 04:00 CET): weekly stats
  - 7th of each month, 03:00 UTC: monthly stats
  - 7th of Jan/Apr/Jul/Oct, 03:00 UTC: quarterly stats

Steps:
  1. Patterns — generate/update statistical + text patterns from trajectories
  2. Rep Stats — per-rep performance metrics (segments A-H) → learned_patterns + rep_summary
  3. Team Stats — per-team benchmark aggregates → learned_patterns + team_summary
  4. Coaching Alerts — per-rep alerts comparing vs team benchmarks → learned_patterns + rep_summary.alerts

Internal names everywhere: schema.tbl(), schema.col(), config2.*.
"""

import traceback
from uuid import uuid4

from src.pipelines.weekly.patterns2 import run as patterns_run
from src.pipelines.weekly.rep_stats import run as rep_stats_run
from src.pipelines.weekly.rep_stats import run_alerts as rep_alerts_run
from src.pipelines.weekly.team_stats import run as team_stats_run


def run(period_type: str = "weekly"):
    run_id = str(uuid4())

    print("=" * 60)
    print(f"WEEKLY RUN v2 — period_type={period_type}, run_id={run_id[:8]}...")
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
        total = rep_stats_run(run_id=run_id, period_type=period_type)
        print(f"  {total} rep patterns generated/updated")
    except Exception as e:
        print(f"  ✗ Rep Stats failed: {e}")
        traceback.print_exc()

    # ── 3. Team Stats ──
    print("\n▸ TEAM STATS")
    try:
        total = team_stats_run(run_id=run_id, period_type=period_type)
        print(f"  {total} team patterns generated/updated")
    except Exception as e:
        print(f"  ✗ Team Stats failed: {e}")
        traceback.print_exc()

    # ── 4. Coaching Alerts ──
    print("\n▸ COACHING ALERTS")
    try:
        total = rep_alerts_run(run_id=run_id, period_type=period_type)
        print(f"  {total} alerts generated/updated")
    except Exception as e:
        print(f"  ✗ Coaching Alerts failed: {e}")
        traceback.print_exc()

    print(f"\n{'=' * 60}")
    print(f"WEEKLY v2 DONE — run_id={run_id[:8]}...")
    print("=" * 60)
