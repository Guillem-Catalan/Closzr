"""
Reassign Deals — processes pending reassignment jobs from the UI wizard.

Reads from the reassignment_jobs table, applies changes to deals + deal_ui,
patches HubSpot owner when applicable, and marks jobs as done.

Flow:
  1. Fetch jobs with status='pending'
  2. For each job, iterate through job_data items
  3. Look up the new person in orgchart → full_name, team_name, hs_owner_id
  4. Update deals table (pae/pbd = display name, team)
  5. Update deal_ui table (pae/pbd = display name, team)
  6. If role=pae and hs_owner_id exists → PATCH HubSpot deal owner
  7. Mark job as done with per-deal results
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from src.db.client import supabase
from src.integrations import hubspot


def _fetch_pending_jobs() -> list[dict]:
    resp = (
        supabase.table("reassignment_jobs")
        .select("*")
        .eq("status", "pending")
        .order("requested_at")
        .execute()
    )
    return resp.data or []


def _lock_job(job_id: str):
    supabase.table("reassignment_jobs").update({
        "status": "processing",
        "started_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", job_id).execute()


def _complete_job(job_id: str, results: list[dict], error: str | None = None):
    status = "failed" if error else "done"
    supabase.table("reassignment_jobs").update({
        "status": status,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "results": results,
        "error_message": error,
    }).eq("id", job_id).execute()


def _lookup_person(email: str) -> dict | None:
    resp = (
        supabase.table("orgchart")
        .select("email, full_name, team_name, hs_owner_id")
        .eq("email", email)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return rows[0] if rows else None


def _get_hs_deal_id(deal_id: str) -> str | None:
    resp = (
        supabase.table("deal_ui")
        .select("hs_deal_id")
        .eq("deal_id", deal_id)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return rows[0]["hs_deal_id"] if rows and rows[0].get("hs_deal_id") else None


def _reassign_one(item: dict) -> dict:
    """Process a single deal reassignment. Returns {deal_id, ok, error?}."""
    deal_id = item["deal_id"]
    new_email = item["new_email"]
    role = item["role"]

    person = _lookup_person(new_email)
    if not person:
        return {"deal_id": deal_id, "ok": False, "error": f"{new_email} not found in orgchart"}

    display_name = person["full_name"]
    new_team = person.get("team_name") or ""
    hs_owner_id = person.get("hs_owner_id")

    col = "pae" if role == "pae" else "pbd"
    update_payload = {col: display_name, "team": new_team}

    # Update deals table
    resp = supabase.table("deals").update(update_payload).eq("id", deal_id).execute()
    if hasattr(resp, "error") and resp.error:
        return {"deal_id": deal_id, "ok": False, "error": f"deals update: {resp.error.message}"}

    # Update deal_ui table
    resp = supabase.table("deal_ui").update(update_payload).eq("deal_id", deal_id).execute()
    if hasattr(resp, "error") and resp.error:
        return {"deal_id": deal_id, "ok": False, "error": f"deal_ui update: {resp.error.message}"}

    # Patch HubSpot owner (only for PAE role with hs_owner_id)
    hs_updated = False
    if role == "pae" and hs_owner_id:
        hs_deal_id = _get_hs_deal_id(deal_id)
        if hs_deal_id:
            try:
                hubspot.patch(
                    f"/crm/v3/objects/deals/{hs_deal_id}",
                    {"properties": {"hubspot_owner_id": str(hs_owner_id)}},
                )
                hs_updated = True
            except Exception as e:
                return {
                    "deal_id": deal_id,
                    "ok": True,
                    "hs_updated": False,
                    "hs_error": str(e),
                }

    return {"deal_id": deal_id, "ok": True, "hs_updated": hs_updated}


def process_job(job: dict) -> dict:
    """Process one reassignment job."""
    job_id = job["id"]
    items = job.get("job_data") or []

    if not items:
        _complete_job(job_id, [], "Empty job_data")
        return {"job_id": job_id, "status": "failed", "error": "empty"}

    _lock_job(job_id)

    results = []
    for item in items:
        try:
            result = _reassign_one(item)
        except Exception as e:
            result = {"deal_id": item.get("deal_id", "?"), "ok": False, "error": str(e)}
        results.append(result)

    ok_count = sum(1 for r in results if r["ok"])
    fail_count = len(results) - ok_count
    error_msg = f"{fail_count} deals failed" if fail_count > 0 else None

    _complete_job(job_id, results, error_msg)

    return {
        "job_id": job_id,
        "status": "done",
        "total": len(results),
        "ok": ok_count,
        "failed": fail_count,
    }


def run() -> dict:
    jobs = _fetch_pending_jobs()
    if not jobs:
        return {"status": "ok", "message": "No pending jobs", "processed": 0}

    print(f"Found {len(jobs)} pending reassignment job(s)")

    summaries = []
    for job in jobs:
        print(f"\n  Processing job {job['id']} ({len(job.get('job_data', []))} deals)...")
        summary = process_job(job)
        summaries.append(summary)
        print(f"  → {summary['ok']}/{summary['total']} OK")

    total_ok = sum(s["ok"] for s in summaries)
    total_fail = sum(s["failed"] for s in summaries)
    print(f"\nDone: {total_ok} reassigned, {total_fail} failed across {len(jobs)} job(s)")

    return {
        "status": "ok",
        "processed": len(jobs),
        "total_ok": total_ok,
        "total_failed": total_fail,
    }


if __name__ == "__main__":
    result = run()
    print(result)
