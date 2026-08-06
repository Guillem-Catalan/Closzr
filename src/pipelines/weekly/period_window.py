"""
Period window computation for rep/team stats.

All windows are half-open: [period_start, period_end).
Pipeline filters: closed_at >= period_start AND closed_at < period_end.

Weekly:    trailing 7 days anchored to most recent Sunday.
Monthly:   previous complete calendar month (run on 7th).
Quarterly: previous complete calendar quarter (run on 7th of Jan/Apr/Jul/Oct).
"""

from datetime import date, timedelta


PERIOD_TYPES = ("weekly", "monthly", "quarterly")


def period_window(period_type: str, run_date: date) -> tuple[date, date]:
    """Return half-open [start, end) for a period type.

    Weekly re-runs on any day of the week always target the same row
    because the window is anchored to the most recent Sunday.
    """
    if period_type == "weekly":
        # Anchor to most recent Sunday.
        # weekday(): Mon=0..Sun=6, so (weekday+1)%7 = days since last Sunday.
        days_since_sunday = (run_date.weekday() + 1) % 7
        last_sunday = run_date - timedelta(days=days_since_sunday)
        return (last_sunday - timedelta(days=7), last_sunday)

    if period_type == "monthly":
        first_of_current = run_date.replace(day=1)
        first_of_prev = (first_of_current - timedelta(days=1)).replace(day=1)
        return (first_of_prev, first_of_current)

    if period_type == "quarterly":
        quarter_months = [1, 4, 7, 10]
        current_q_start = max(
            date(run_date.year, m, 1) for m in quarter_months
            if date(run_date.year, m, 1) <= run_date
        )
        prev_q_end = current_q_start
        prev_q_start_year = current_q_start.year if current_q_start.month > 1 else current_q_start.year - 1
        prev_q_start = max(
            date(prev_q_start_year, m, 1) for m in quarter_months
            if date(prev_q_start_year, m, 1) < current_q_start
        )
        return (prev_q_start, prev_q_end)

    raise ValueError(f"Unknown period_type: {period_type}")
