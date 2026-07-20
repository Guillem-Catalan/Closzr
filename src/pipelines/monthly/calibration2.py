"""
Monthly Calibration v2 — compare forecast predictions vs actual results.

Runs on day 1 of each month. Analyzes the previous month:
  - Deals with claudio_close_date in the month → did they actually close?
  - Deals that closed but were NOT predicted → false negatives
  - Accuracy of estimated_close_date → how many days off?

Output goes to calibration_log. The forecast reads it to avoid repeating errors.
Zero Claude — pure data comparison.
Internal names everywhere: schema.tbl(), schema.col(), config2.*.
"""

from datetime import date, timedelta

from src import schema
from src.db.client import supabase


# ═══════════════════════════════════════════════════════════════════════════
# RESOLVED CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════

_TBL_DEALS       = schema.tbl("deals")
_TBL_SNAPSHOTS   = schema.tbl("snapshots")
_TBL_CALIBRATION = schema.tbl("calibration")

_D_UUID  = schema.col("deal_uuid")
_D_NAME  = schema.col("deal_name")
_D_STAGE = schema.col("stage")
_D_CLOSE = schema.col("close_date")

_WON_STAGES  = list(schema.WON)
_LOST_STAGES = list(schema.LOST)

# ── Snapshot identity cols (from schema) ──
_SNAP_ID          = schema.SNAPSHOT_IDENTITY_COLS
_S_DEAL_ID        = _SNAP_ID["deal_id"]
_S_SNAPSHOT_DATE  = _SNAP_ID["snapshot_date"]

# ── Snapshot forecast cols (members of schema.FORECAST_CLAUDE_COLS — no dict mapping) ──
_S_FORECAST_CONF  = "forecast_confidence"
_S_CLAUDIO_CLOSE  = "claudio_close_date"

_C_MONTH             = "month"
_C_DEAL_ID           = "deal_id"
_C_DEAL_NAME         = "deal_name"
_C_PREDICTED_CLOSE   = "predicted_close_date"
_C_PREDICTED_CONF    = "predicted_confidence"
_C_ACTUAL_OUTCOME    = "actual_outcome"
_C_ACTUAL_CLOSE      = "actual_close_date"
_C_DAYS_OFF          = "days_off"
_C_ERROR_TYPE        = "error_type"
_C_ERROR_ANALYSIS    = "error_analysis"


# ═══════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _get_target_month(target_month: str | None = None) -> tuple[str, str, str]:
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


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def run(target_month: str | None = None) -> int:
    month_key, month_start, month_end = _get_target_month(target_month)
    print(f"\n  CALIBRATION: analyzing {month_key}")

    # ── 1. Get all deals with claudio_close_date in the target month ──
    predicted_resp = (
        supabase.table(_TBL_SNAPSHOTS)
        .select(f"{_S_DEAL_ID}, {_S_FORECAST_CONF}, {_S_CLAUDIO_CLOSE}, {_S_SNAPSHOT_DATE}")
        .gte(_S_CLAUDIO_CLOSE, month_start)
        .lt(_S_CLAUDIO_CLOSE, month_end)
        .gte(_S_SNAPSHOT_DATE, month_start)
        .lt(_S_SNAPSHOT_DATE, month_end)
        .execute()
    )

    predicted_map: dict[str, dict] = {}
    for s in (predicted_resp.data or []):
        did = s.get(_S_DEAL_ID)
        if not did:
            continue
        existing = predicted_map.get(did)
        if not existing or (s.get(_S_SNAPSHOT_DATE) or "") > (existing.get(_S_SNAPSHOT_DATE) or ""):
            predicted_map[did] = s

    predicted_deal_ids = list(predicted_map.keys())
    print(f"    {len(predicted_deal_ids)} deals predicted to close in {month_key}")

    if not predicted_deal_ids:
        print("    No predictions to calibrate")
        return 0

    # ── 2. Get actual outcomes ──
    deal_resp = (
        supabase.table(_TBL_DEALS)
        .select(f"{_D_UUID}, {_D_NAME}, {_D_STAGE}, {_D_CLOSE}")
        .in_(_D_UUID, predicted_deal_ids)
        .execute()
    )
    deal_map = {d[_D_UUID]: d for d in (deal_resp.data or [])}

    # ── 3. Compare predictions vs results ──
    entries = []

    for deal_id, prediction in predicted_map.items():
        d = deal_map.get(deal_id)
        if not d:
            continue

        stage = (d.get(_D_STAGE) or "").strip()
        actual_close_date = d.get(_D_CLOSE) or ""
        predicted_close_date = prediction.get(_S_CLAUDIO_CLOSE) or ""
        confidence = prediction.get(_S_FORECAST_CONF) or ""

        if stage in _WON_STAGES and actual_close_date >= month_start and actual_close_date < month_end:
            actual = "closed_won_this_month"
            error_type = "correct"
        elif stage in _WON_STAGES:
            actual = "closed_won_other_month"
            error_type = "timing_late"
        elif stage in _LOST_STAGES:
            actual = "lost"
            error_type = "false_positive"
        else:
            actual = "still_open"
            error_type = "false_positive"

        days_off = None
        if predicted_close_date and actual_close_date and actual in ("closed_won_this_month", "closed_won_other_month"):
            try:
                pred_d = date.fromisoformat(str(predicted_close_date)[:10])
                actual_d = date.fromisoformat(str(actual_close_date)[:10])
                days_off = (actual_d - pred_d).days
            except (ValueError, TypeError):
                pass

        deal_name = d.get(_D_NAME) or "?"
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
            _C_MONTH: month_key,
            _C_DEAL_ID: deal_id,
            _C_DEAL_NAME: deal_name,
            _C_PREDICTED_CLOSE: predicted_close_date or None,
            _C_PREDICTED_CONF: confidence,
            _C_ACTUAL_OUTCOME: actual,
            _C_ACTUAL_CLOSE: actual_close_date or None,
            _C_DAYS_OFF: days_off,
            _C_ERROR_TYPE: error_type,
            _C_ERROR_ANALYSIS: analysis,
        })

    # ── 4. Find false negatives — deals that closed but were NOT predicted ──
    closed_resp = (
        supabase.table(_TBL_DEALS)
        .select(f"{_D_UUID}, {_D_NAME}, {_D_CLOSE}")
        .in_(_D_STAGE, _WON_STAGES)
        .gte(_D_CLOSE, month_start)
        .lt(_D_CLOSE, month_end)
        .execute()
    )
    closed_ids = {d[_D_UUID] for d in (closed_resp.data or [])}
    missed = closed_ids - set(predicted_deal_ids)

    for deal_id in list(missed)[:30]:
        d_resp = (
            supabase.table(_TBL_DEALS)
            .select(f"{_D_UUID}, {_D_NAME}, {_D_CLOSE}")
            .eq(_D_UUID, deal_id)
            .limit(1)
            .execute()
        )
        if d_resp.data:
            d = d_resp.data[0]
            entries.append({
                _C_MONTH: month_key,
                _C_DEAL_ID: deal_id,
                _C_DEAL_NAME: d.get(_D_NAME) or "?",
                _C_PREDICTED_CLOSE: None,
                _C_PREDICTED_CONF: None,
                _C_ACTUAL_OUTCOME: "closed_won_this_month",
                _C_ACTUAL_CLOSE: d.get(_D_CLOSE),
                _C_DAYS_OFF: None,
                _C_ERROR_TYPE: "false_negative",
                _C_ERROR_ANALYSIS: "Deal closed but Closzr didn't predict it — what signal was missed?",
            })

    # ── 5. Write to calibration_log ──
    for e in entries:
        row = {k: v for k, v in e.items() if v is not None}
        try:
            supabase.table(_TBL_CALIBRATION).insert(row).execute()
        except Exception as err:
            print(f"    ✗ Insert failed for {e.get(_C_DEAL_NAME, '?')}: {err}")

    # ── 6. Summary ──
    correct = sum(1 for e in entries if e[_C_ERROR_TYPE] == "correct")
    false_pos = sum(1 for e in entries if e[_C_ERROR_TYPE] == "false_positive")
    timing = sum(1 for e in entries if e[_C_ERROR_TYPE] == "timing_late")
    false_neg = sum(1 for e in entries if e[_C_ERROR_TYPE] == "false_negative")

    print(f"    Results for {month_key}:")
    print(f"      ✓ Correct: {correct}")
    print(f"      ✗ False positive (predicted close, didn't): {false_pos}")
    print(f"      ⏳ Timing late (closed but different month): {timing}")
    print(f"      ⚠ False negative (closed but not predicted): {false_neg}")
    print(f"      Total entries: {len(entries)}")

    return len(entries)
