"""
Snapshot pipeline — Monday and Friday at 7:50 CEST.

Monday (snapshot_day=1): demos_booked, closing_expected, mr_expected, consecución, whales
Friday (snapshot_day=2): demos_held, mr_closed, lost_deals + postmortem, learnings, coaching_flags

Sources: deal_ui, deals (meetings), deal_analysis (postmortem), forecast_targets, orgchart
"""

import traceback
from datetime import date, timedelta

from src.config import STAGE_DEMO, STAGE_CLOSING
from src.db.client import supabase


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def _week_boundaries(today: date) -> tuple[date, date]:
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def _first_of_month(today: date) -> date:
    return today.replace(day=1)


def _resolve_teams() -> list[dict]:
    """
    Orgchart → list of {tl_email, team, ae_emails}.
    Includes TLs with direct AE reports and directors with recursive AE subtrees.
    """
    resp = supabase.table("orgchart").select(
        "email, full_name, role, team_name, reports_to"
    ).eq("is_active", True).execute()

    people = resp.data or []
    children_of: dict[str, list[dict]] = {}
    for p in people:
        parent = p.get("reports_to")
        if parent:
            children_of.setdefault(parent, []).append(p)

    ae_roles = {"ae", "pae", "pbd", "sdr", "pdm", "pre_sales"}

    def collect_ae_emails(email: str) -> list[str]:
        result = []
        for child in children_of.get(email, []):
            if (child.get("role") or "").lower() in ae_roles:
                result.append(child["email"])
            else:
                result.extend(collect_ae_emails(child["email"]))
        return result

    tl_roles = {"tl", "pae_tl", "pbd_tl", "director", "head", "country_manager"}
    teams = []
    seen = set()

    for p in people:
        email = p["email"]
        role = (p.get("role") or "").lower()
        if role not in tl_roles or email in seen:
            continue
        ae_emails = collect_ae_emails(email)
        if not ae_emails:
            continue
        seen.add(email)
        teams.append({
            "tl_email": email,
            "team": p.get("team_name") or p.get("full_name") or email,
            "ae_emails": ae_emails,
        })

    return teams


# ─────────────────────────────────────────────────────────────
# MONDAY
# ─────────────────────────────────────────────────────────────

def _build_monday(team_info: dict, today: date) -> dict:
    ae_emails = team_info["ae_emails"]
    monday, sunday = _week_boundaries(today)
    monday_utc = f"{monday.isoformat()}T00:00:00Z"
    sunday_utc = f"{sunday.isoformat()}T23:59:59Z"
    month_start = _first_of_month(today).isoformat()

    # ── demos_booked: deals in demo stages with meeting this week ──
    demos_booked = 0
    try:
        resp = (
            supabase.table("deals")
            .select("id, pae, pbd")
            .in_("deal_stage", list(STAGE_DEMO))
            .gte("hs_next_meeting_start_time", monday_utc)
            .lte("hs_next_meeting_start_time", sunday_utc)
            .execute()
        )
        for d in (resp.data or []):
            owner = d.get("pae") or d.get("pbd") or ""
            if owner in ae_emails:
                demos_booked += 1
    except Exception as e:
        print(f"    demos_booked failed: {e}")

    # ── closing_expected: closing stage deals with close_date_hs this week ──
    closing_expected = []
    mr_expected = 0.0
    try:
        resp = (
            supabase.table("deal_ui")
            .select("deal_id, deal_name_full, stage, mrr, close_probability, close_date_hs, pae, deal_momentum")
            .in_("stage", list(STAGE_CLOSING))
            .in_("pae", ae_emails)
            .gte("close_date_hs", monday.isoformat())
            .lte("close_date_hs", sunday.isoformat())
            .execute()
        )
        for d in (resp.data or []):
            mrr = float(d.get("mrr") or 0)
            prob = float(d.get("close_probability") or 0)
            closing_expected.append({
                "deal_name": d.get("deal_name_full") or "?",
                "deal_id": str(d.get("deal_id") or ""),
                "mrr": mrr,
                "prob": prob,
                "close_date": d.get("close_date_hs"),
                "ae": d.get("pae") or "",
                "stage": d.get("stage") or "",
                "momentum": d.get("deal_momentum") or "",
            })
            mr_expected += mrr * prob / 100
    except Exception as e:
        print(f"    closing_expected failed: {e}")

    # ── consecucion: won MRR this month / target ──
    won_mrr = 0.0
    try:
        resp = (
            supabase.table("deal_ui")
            .select("mrr")
            .eq("outcome", "won")
            .in_("pae", ae_emails)
            .gte("close_date_hs", month_start)
            .execute()
        )
        for d in (resp.data or []):
            won_mrr += float(d.get("mrr") or 0)
    except Exception:
        pass

    target_mrr = 0.0
    try:
        resp = (
            supabase.table("forecast_targets")
            .select("monthly_target")
            .eq("team", team_info["team"])
            .eq("month", today.strftime("%Y-%m"))
            .maybe_single()
            .execute()
        )
        if resp.data:
            target_mrr = float(resp.data.get("monthly_target") or 0)
    except Exception:
        pass

    consecucion = round(won_mrr / target_mrr * 100, 1) if target_mrr > 0 else 0

    # ── whales: top 5 active deals by MRR ──
    whales = []
    try:
        resp = (
            supabase.table("deal_ui")
            .select("deal_name_full, mrr, action_signal, pae, deal_momentum")
            .in_("pae", ae_emails)
            .is_("outcome", "null")
            .order("mrr", desc=True)
            .limit(5)
            .execute()
        )
        for d in (resp.data or []):
            mrr = float(d.get("mrr") or 0)
            if mrr > 0:
                whales.append({
                    "deal_name": d.get("deal_name_full") or "?",
                    "mrr": mrr,
                    "signal": d.get("action_signal") or "",
                    "ae": d.get("pae") or "",
                    "momentum": d.get("deal_momentum") or "",
                })
    except Exception:
        pass

    return {
        "demos_booked": demos_booked,
        "demos_held": 0,
        "mr_closed": 0,
        "mr_expected": round(mr_expected, 2),
        "consecucion_pct": consecucion,
        "data": {
            "closing_expected": closing_expected,
            "whales": whales,
        },
    }


# ─────────────────────────────────────────────────────────────
# FRIDAY
# ─────────────────────────────────────────────────────────────

def _build_friday(team_info: dict, today: date) -> dict:
    ae_emails = team_info["ae_emails"]
    monday, _ = _week_boundaries(today)
    monday_ts = f"{monday.isoformat()}T00:00:00"
    friday_ts = f"{today.isoformat()}T23:59:59"
    month_start = _first_of_month(today).isoformat()

    # ── demos_held: deals with after_demo_date this week ──
    demos_held = 0
    try:
        resp = (
            supabase.table("deal_ui")
            .select("deal_id")
            .in_("pae", ae_emails)
            .gte("after_demo_date", monday_ts)
            .lte("after_demo_date", friday_ts)
            .execute()
        )
        demos_held = len(resp.data or [])
    except Exception as e:
        print(f"    demos_held failed: {e}")

    # ── mr_closed: deals won this week (via deal_analysis.created_at) ──
    mr_closed = 0.0
    try:
        analysis_resp = (
            supabase.table("deal_analysis")
            .select("deal_id")
            .eq("outcome", "won")
            .gte("created_at", monday_ts)
            .execute()
        )
        won_candidates = [a["deal_id"] for a in (analysis_resp.data or [])]
        if won_candidates:
            ui_resp = (
                supabase.table("deal_ui")
                .select("deal_id, mrr, pae")
                .in_("deal_id", won_candidates)
                .in_("pae", ae_emails)
                .execute()
            )
            for d in (ui_resp.data or []):
                mr_closed += float(d.get("mrr") or 0)
    except Exception as e:
        print(f"    mr_closed failed: {e}")

    # ── consecucion: won MRR this month / target ──
    total_won_month = 0.0
    try:
        resp = (
            supabase.table("deal_ui")
            .select("mrr")
            .eq("outcome", "won")
            .in_("pae", ae_emails)
            .gte("close_date_hs", month_start)
            .execute()
        )
        for d in (resp.data or []):
            total_won_month += float(d.get("mrr") or 0)
    except Exception:
        pass

    target_mrr = 0.0
    try:
        resp = (
            supabase.table("forecast_targets")
            .select("monthly_target")
            .eq("team", team_info["team"])
            .eq("month", today.strftime("%Y-%m"))
            .maybe_single()
            .execute()
        )
        if resp.data:
            target_mrr = float(resp.data.get("monthly_target") or 0)
    except Exception:
        pass

    consecucion = round(total_won_month / target_mrr * 100, 1) if target_mrr > 0 else 0

    # ── lost_deals: deals lost this week with postmortem ──
    lost_deals = []
    learnings = []
    try:
        analysis_resp = (
            supabase.table("deal_analysis")
            .select("deal_id, outcome_summary, what_failed")
            .eq("outcome", "lost")
            .gte("created_at", monday_ts)
            .execute()
        )
        lost_candidates = {a["deal_id"]: a for a in (analysis_resp.data or [])}
        if lost_candidates:
            ui_resp = (
                supabase.table("deal_ui")
                .select("deal_id, deal_name_full, mrr, pae")
                .in_("deal_id", list(lost_candidates.keys()))
                .in_("pae", ae_emails)
                .execute()
            )
            for d in (ui_resp.data or []):
                did = d["deal_id"]
                analysis = lost_candidates.get(did, {})
                postmortem = analysis.get("outcome_summary") or ""
                what_failed = analysis.get("what_failed") or ""
                lost_deals.append({
                    "deal_name": d.get("deal_name_full") or "?",
                    "mrr": float(d.get("mrr") or 0),
                    "ae": d.get("pae") or "",
                    "postmortem": postmortem,
                    "what_failed": what_failed,
                })
                if what_failed:
                    learnings.append({
                        "deal_name": d.get("deal_name_full") or "?",
                        "text": what_failed,
                    })
    except Exception as e:
        print(f"    lost_deals failed: {e}")

    # ── coaching_flags: from pae_audits this week for team's deals ──
    coaching_flags = []
    try:
        ae_deals_resp = (
            supabase.table("deal_ui")
            .select("deal_id")
            .in_("pae", ae_emails)
            .is_("outcome", "null")
            .execute()
        )
        ae_deal_ids = [d["deal_id"] for d in (ae_deals_resp.data or [])]
        if ae_deal_ids:
            for i in range(0, len(ae_deal_ids), 200):
                batch = ae_deal_ids[i:i + 200]
                audits_resp = (
                    supabase.table("pae_audits")
                    .select("owner_name, top_coaching_flag, deal_ref")
                    .in_("deal_ref", batch)
                    .gte("created_at", monday_ts)
                    .not_.is_("top_coaching_flag", "null")
                    .execute()
                )
                for a in (audits_resp.data or []):
                    coaching_flags.append({
                        "ae": a.get("owner_name") or "",
                        "flag": a.get("top_coaching_flag") or "",
                    })
    except Exception as e:
        print(f"    coaching_flags failed: {e}")

    return {
        "demos_booked": 0,
        "demos_held": demos_held,
        "mr_closed": round(mr_closed, 2),
        "mr_expected": 0,
        "consecucion_pct": consecucion,
        "data": {
            "lost_deals": lost_deals,
            "learnings": learnings,
            "coaching_flags": coaching_flags,
        },
    }


# ─────────────────────────────────────────────────────────────
# ORCHESTRATOR
# ─────────────────────────────────────────────────────────────

def run():
    today = date.today()
    weekday = today.weekday()

    if weekday == 0:
        snapshot_day = 1
    elif weekday == 4:
        snapshot_day = 2
    else:
        print(f"  Not Monday or Friday (weekday={weekday}), skipping")
        return

    iso_week = f"W{today.isocalendar().week}"
    day_label = "MONDAY" if snapshot_day == 1 else "FRIDAY"

    print("=" * 60)
    print(f"SNAPSHOT — {day_label} {iso_week}")
    print("=" * 60)

    # ── Resolve teams ──
    print("\n▸ RESOLVE TEAMS")
    try:
        teams = _resolve_teams()
        print(f"  {len(teams)} teams found")
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        traceback.print_exc()
        return

    # ── Build + upsert snapshots ──
    print(f"\n▸ BUILD SNAPSHOTS")
    generated = 0

    for team_info in teams:
        tl = team_info["tl_email"]
        team_name = team_info["team"]
        n_aes = len(team_info["ae_emails"])

        try:
            if snapshot_day == 1:
                metrics = _build_monday(team_info, today)
            else:
                metrics = _build_friday(team_info, today)

            row = {
                "team": team_name,
                "tl_email": tl,
                "iso_week": iso_week,
                "snapshot_day": snapshot_day,
                "snapshot_date": today.isoformat(),
                "demos_booked": metrics["demos_booked"],
                "demos_held": metrics["demos_held"],
                "mr_closed": metrics["mr_closed"],
                "mr_expected": metrics["mr_expected"],
                "consecucion_pct": metrics["consecucion_pct"],
                "data": metrics["data"],
            }

            supabase.table("team_snapshots").upsert(
                row, on_conflict="team,iso_week,snapshot_day"
            ).execute()

            print(f"  ✓ {team_name} ({n_aes} AEs, TL: {tl})")
            generated += 1

        except Exception as e:
            print(f"  ✗ {team_name}: {e}")
            traceback.print_exc()

    print(f"\n{'=' * 60}")
    print(f"SNAPSHOT DONE: {generated}/{len(teams)} teams")
    print("=" * 60)
