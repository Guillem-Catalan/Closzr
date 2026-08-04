"""
Sync AE targets from data lake (Starburst/Trino) → Supabase ae_targets.

Source: data_lake_gold.sales_rpt_individual_goals (variable_name = 'New MRR | By AE')
Destination: ae_targets (email, month, monthly_target)

Runs weekly via GitHub Actions. Idempotent — upserts on (email, month).
Rows with source='manual' are never overwritten.
"""

import os
import traceback
from datetime import datetime, timezone

from src.db.client import supabase

TRINO_HOST = "factorial-aws-prod-data-query-galaxy.trino.galaxy.starburst.io"
TRINO_USER = "loveable-parterns@factorial.galaxy.starburst.io"
TRINO_CATALOG = "aws_prod_data_glue_catalog"
TRINO_SCHEMA = "data_lake_gold"
TRINO_TABLE = "sales_rpt_individual_goals"

QUERY = f"""
    SELECT user_email, period_month, value
    FROM {TRINO_CATALOG}.{TRINO_SCHEMA}.{TRINO_TABLE}
    WHERE variable_name = 'New MRR | By AE'
    ORDER BY period_month, user_email
"""

BATCH_SIZE = 100


def _connect_trino():
    from trino.dbapi import connect
    from trino.auth import BasicAuthentication

    api_key = os.environ.get("TRINO_API_KEY", "")
    if not api_key:
        raise RuntimeError("TRINO_API_KEY not set")

    return connect(
        host=TRINO_HOST,
        port=443,
        user=TRINO_USER,
        auth=BasicAuthentication(TRINO_USER, api_key),
        http_scheme="https",
    )


def _fetch_targets() -> list[dict]:
    conn = _connect_trino()
    cur = conn.cursor()
    cur.execute(QUERY)

    rows = []
    for user_email, period_month, value in cur.fetchall():
        if not user_email:
            continue
        month_str = str(period_month)[:7]  # '2026-07-01' → '2026-07'
        rows.append({
            "email": user_email.strip(),
            "month": month_str,
            "monthly_target": round(float(value or 0), 2),
        })

    cur.close()
    conn.close()
    return rows


def _get_manual_keys() -> set[tuple[str, str]]:
    """Return (email, month) pairs with source='manual' — these are never overwritten."""
    resp = (
        supabase.table("ae_targets")
        .select("email, month")
        .eq("source", "manual")
        .execute()
    )
    return {(r["email"], r["month"]) for r in (resp.data or [])}


def _upsert_batch(batch: list[dict]) -> int:
    supabase.table("ae_targets").upsert(
        batch, on_conflict="email,month"
    ).execute()
    return len(batch)


def run():
    print("=" * 60)
    print("SYNC TARGETS — data lake → ae_targets")
    print("=" * 60)

    # 1. Fetch from data lake
    print("\n▸ FETCH FROM DATA LAKE")
    try:
        dl_rows = _fetch_targets()
        print(f"  {len(dl_rows)} rows fetched")
    except Exception as e:
        print(f"  ✗ Failed to connect to data lake: {e}")
        traceback.print_exc()
        return

    if not dl_rows:
        print("  No data returned — aborting (ae_targets unchanged)")
        return

    # 2. Get manual overrides to protect
    print("\n▸ CHECK MANUAL OVERRIDES")
    try:
        manual_keys = _get_manual_keys()
        print(f"  {len(manual_keys)} manual entries (will not overwrite)")
    except Exception as e:
        print(f"  ✗ Failed to read manual keys: {e}")
        traceback.print_exc()
        return

    # 3. Filter out manual overrides and prepare upsert
    now = datetime.now(timezone.utc).isoformat()
    to_upsert = []
    skipped = 0

    for row in dl_rows:
        key = (row["email"], row["month"])
        if key in manual_keys:
            skipped += 1
            continue

        to_upsert.append({
            "email": row["email"],
            "month": row["month"],
            "monthly_target": row["monthly_target"],
            "source": "data_lake",
            "synced_at": now,
            "updated_at": now,
        })

    print(f"\n▸ UPSERT ({len(to_upsert)} rows, {skipped} manual-skipped)")
    upserted = 0
    errors = 0

    for i in range(0, len(to_upsert), BATCH_SIZE):
        batch = to_upsert[i : i + BATCH_SIZE]
        try:
            upserted += _upsert_batch(batch)
        except Exception as e:
            errors += 1
            print(f"  ✗ Batch {i}-{i + len(batch)}: {e}")
            traceback.print_exc()

    # 4. Summary
    print(f"\n{'=' * 60}")
    print(f"SYNC DONE: {upserted} upserted, {skipped} manual-skipped, {errors} errors")
    print("=" * 60)

    if errors > 0:
        raise RuntimeError(f"Sync completed with {errors} batch errors")
