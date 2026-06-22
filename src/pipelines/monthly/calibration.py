"""
Monthly Calibration — compare forecast predictions vs actual results.

Runs on day 1 of each month. Analyzes the previous month:
  - Deals predicted to close (closes_this_month=true) → did they?
  - Deals that closed but were NOT predicted → false negatives
  - Accuracy of estimated_close_date → how many days off?

Output goes to calibration_log. The forecast reads it to avoid repeating errors.
Zero Claude — pure data comparison.
Everything from config.
"""

from datetime import date, timedelta

from src.config import MONTHLY_CONFIG
from src.db.client import supabase

_M = MONTHLY_CONFIG


def _get_target_month(target_month: str | None = None) -> tuple[str, str, str]:
    """Return (month_key, month_start, month_end) for the target month."""
    if target_month:
        year, month = target_month.split("-")
    else:
        last_month = date.today().replace(day=1) - timedelta(days=1)
        year = str(last_month.year)
        month = f"{last_month.month:02d}"

    month_key = f"{year}-{month}"
    month_start = f"{month_key}-01"
    next_month = date(int(year), int(month), 1) + timedelta(days=32)
    month_end = next_month.replace(day=1).isoformat()

    return month_key, month_start, month_end


def run(target_month: str | None = None) -> int:
    """Run calibration for a month. Defaults to previous month."""

    month_key, month_start, month_end = _get_target_month(target_month)
    print(f"\n  CALIBRATION: analyzing {month_key}")

    # ── 1. Get all deals predicted to close this month ──
    predicted_resp = (
        supabase.table(_M["snapshot_table"])
        .select("deal_id, closes_this_month, forecast_confidence, claudio_close_date, snapshot_date")
        .eq("closes_this_month", True)
        .gte("snapshot_date", month_start)
        .lt("snapshot_date", month_end)
        .execute()
    )

    # Dedup by deal_id — take the latest prediction
    predicted_map: dict[str, dict] = {}
    for s in (predicted_resp.data or []):
        did = s.get("deal_id")
        if not did:
            continue
        existing = predicted_map.get(did)
        if not existing or (s.get("snapshot_date") or "") > (existing.get("snapshot_date") or ""):
            predicted_map[did] = s

    predicted_deal_ids = list(predicted_map.keys())
    print(f"    {len(predicted_deal_ids)} deals predicted to close in {month_key}")

    if not predicted_deal_ids:
        print("    No predictions to calibrate")
        return 0

    # ── 2. Get actual outcomes ──
    deal_resp = (
        supabase.table(_M["deals_table"])
        .select(f"{_M['deal_col_id']}, {_M['deal_col_deal_name']}, {_M['deal_col_stage']}, {_M['deal_col_close_date']}")
        .in_(_M["deal_col_id"], predicted_deal_ids)
        .execute()
    )
    deal_map = {d[_M["deal_col_id"]]: d for d in (deal_resp.data or [])}

    # ── 3. Compare predictions vs results ──
    entries = []

    for deal_id, prediction in predicted_map.items():
        d = deal_map.get(deal_id)
        if not d:
            continue

        stage = (d.get(_M["deal_col_stage"]) or "").strip()
        actual_close_date = d.get(_M["deal_col_close_date"]) or ""
        predicted_close_date = prediction.get("claudio_close_date") or ""
        confidence = prediction.get("forecast_confidence") or ""

        # Determine actual outcome
        if stage in _M["closed_won_stages"] and actual_close_date >= month_start and actual_close_date < month_end:
            actual = "closed_won_this_month"
            error_type = "correct"
        elif stage in _M["closed_won_stages"]:
            actual = "closed_won_other_month"
            error_type = "timing_late"
        elif stage in _M["closed_lost_stages"]:
            actual = "lost"
            error_type = "false_positive"
        else:
            actual = "still_open"
            error_type = "false_positive"

        # Calculate days off
        days_off = None
        if predicted_close_date and actual_close_date and actual in ("closed_won_this_month", "closed_won_other_month"):
            try:
                pred_d = date.fromisoformat(str(predicted_close_date)[:10])
                actual_d = date.fromisoformat(str(actual_close_date)[:10])
                days_off = (actual_d - pred_d).days
            except (ValueError, TypeError):
                pass

        # Build error analysis
        deal_name = d.get(_M["deal_col_deal_name"]) or "?"
        if error_type == "correct":
            analysis = "Correct prediction."
            if days_off is not None and abs(days_off) > 3:
                analysis = f"Correct month but date was {abs(days_off)} days {'late' if days_off > 0 else 'early'}."
        elif error_type == "timing_late":
            analysis = f"Deal closed but not this month — closed {actual_close_date[:10]}. Timing estimate was off."
        elif actual == "lost":
            analysis = f"Deal went to {stage}. Forecast was too optimistic — should not have predicted close."
        else:
            analysis = f"Deal still in {stage}. Hasn't closed — timing was wrong or deal stalled."

        entries.append({
            "month": month_key,
            "deal_id": deal_id,
            "deal_name": deal_name,
            "predicted_close_this_month": True,
            "predicted_close_date": predicted_close_date or None,
            "predicted_confidence": confidence,
            "actual_outcome": actual,
            "actual_close_date": actual_close_date or None,
            "days_off": days_off,
            "error_type": error_type,
            "error_analysis": analysis,
        })

    # ── 4. Find false negatives — deals that closed but were NOT predicted ──
    closed_resp = (
        supabase.table(_M["deals_table"])
        .select(f"{_M['deal_col_id']}, {_M['deal_col_deal_name']}, {_M['deal_col_close_date']}")
        .in_(_M["deal_col_stage"], _M["closed_won_stages"])
        .gte(_M["deal_col_close_date"], month_start)
        .lt(_M["deal_col_close_date"], month_end)
        .execute()
    )
    closed_ids = {d[_M["deal_col_id"]] for d in (closed_resp.data or [])}
    missed = closed_ids - set(predicted_deal_ids)

    for deal_id in list(missed)[:30]:
        d_resp = (
            supabase.table(_M["deals_table"])
            .select(f"{_M['deal_col_id']}, {_M['deal_col_deal_name']}, {_M['deal_col_close_date']}")
            .eq(_M["deal_col_id"], deal_id)
            .limit(1)
            .execute()
        )
        if d_resp.data:
            d = d_resp.data[0]
            entries.append({
                "month": month_key,
                "deal_id": deal_id,
                "deal_name": d.get(_M["deal_col_deal_name"]) or "?",
                "predicted_close_this_month": False,
                "predicted_close_date": None,
                "predicted_confidence": None,
                "actual_outcome": "closed_won_this_month",
                "actual_close_date": d.get(_M["deal_col_close_date"]),
                "days_off": None,
                "error_type": "false_negative",
                "error_analysis": "Deal closed but Closzr didn't predict it — what signal was missed?",
            })

    # ── 5. Write to calibration_log ──
    for e in entries:
        row = {k: v for k, v in e.items() if v is not None}
        try:
            supabase.table(_M["calibration_table"]).insert(row).execute()
        except Exception as err:
            print(f"    ✗ Insert failed for {e.get('deal_name', '?')}: {err}")

    # ── 6. Summary ──
    correct = sum(1 for e in entries if e["error_type"] == "correct")
    false_pos = sum(1 for e in entries if e["error_type"] == "false_positive")
    timing = sum(1 for e in entries if e["error_type"] == "timing_late")
    false_neg = sum(1 for e in entries if e["error_type"] == "false_negative")

    print(f"    Results for {month_key}:")
    print(f"      ✓ Correct: {correct}")
    print(f"      ✗ False positive (predicted close, didn't): {false_pos}")
    print(f"      ⏳ Timing late (closed but different month): {timing}")
    print(f"      ⚠ False negative (closed but not predicted): {false_neg}")
    print(f"      Total entries: {len(entries)}")

    return len(entries)
