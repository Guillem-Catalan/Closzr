"""
Snapshot pipeline — Monday and Friday at 7:50 CEST.

Monday (snapshot_day=1): demos_booked, closing_expected, mr_expected, consecución, whales
Friday (snapshot_day=2): demos_held, mr_closed, lost_deals + postmortem, learnings, coaching_flags

Sources: deal_ui, deals (meetings + closed_lost_reason), deal_analysis (postmortem),
         ae_targets (primary), forecast_targets (fallback), orgchart, pae_audits

Note: deal_ui.pae/pbd store NAMES (not emails). deal_ui.stage stores internal names
(from schema.py), deals.deal_stage stores a mix of internal and display labels.
"""
from __future__ import annotations

import traceback
from datetime import date, timedelta

from src.schema import CLOSING, DEMO, WON, LOST
from src.config import STAGE_WON, STAGE_LOST
from src.db.client import supabase

WON_ALL = list(STAGE_WON | WON)
LOST_ALL = list(STAGE_LOST | LOST)


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def _week_boundaries(today: date) -> tuple[date, date]:
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def _first_of_month(today: date) -> date:
    return today.replace(day=1)


def _won_deals(ae_names: list[str], date_from: str, date_to: str | None = None) -> tuple[int, float]:
    """Count and sum MRR of won deals in a date range. Returns (count, mrr)."""
    count = 0
    total = 0.0
    try:
        q = (
            supabase.table("deal_ui")
            .select("mrr")
            .in_("stage", WON_ALL)
            .in_("pae", ae_names)
            .gte("close_date_hs", date_from)
        )
        if date_to:
            q = q.lte("close_date_hs", date_to)
        resp = q.execute()
        for d in (resp.data or []):
            count += 1
            total += float(d.get("mrr") or 0)
    except Exception:
        pass
    return count, total


def _team_target(team: str, today: date, ae_emails: list[str] | None = None) -> float:
    month_str = today.strftime("%Y-%m")
    # ae_targets is the source of truth
    if ae_emails:
        try:
            total = 0.0
            for i in range(0, len(ae_emails), 200):
                batch = ae_emails[i:i + 200]
                resp = (
                    supabase.table("ae_targets")
                    .select("monthly_target")
                    .in_("email", batch)
                    .eq("month", month_str)
                    .execute()
                )
                for r in (resp.data or []):
                    total += float(r.get("monthly_target") or 0)
            if total > 0:
                return total
        except Exception:
            pass
    # Fallback: forecast_targets (legacy)
    try:
        resp = (
            supabase.table("forecast_targets")
            .select("monthly_target")
            .eq("team", team)
            .eq("month", month_str)
            .maybe_single()
            .execute()
        )
        if resp.data:
            val = float(resp.data.get("monthly_target") or 0)
            if val > 0:
                return val
    except Exception:
        pass
    return 0.0


def _resolve_teams() -> list[dict]:
    """
    Orgchart → list of {tl_email, team, ae_names, ae_emails}.
    deal_ui filters by NAME (pae/pbd), orgchart resolves email↔name.
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

    def collect_aes(email: str) -> list[dict]:
        result = []
        for child in children_of.get(email, []):
            if (child.get("role") or "").lower() in ae_roles:
                result.append({"name": child["full_name"], "email": child["email"]})
            else:
                result.extend(collect_aes(child["email"]))
        return result

    tl_roles = {"tl", "pae_tl", "pbd_tl", "director", "head", "country_manager"}
    teams = []
    seen = set()

    for p in people:
        email = p["email"]
        role = (p.get("role") or "").lower()
        if role not in tl_roles or email in seen:
            continue

        aes = collect_aes(email)
        if not aes:
            continue
        seen.add(email)

        # Include TL themselves (they can own deals too)
        tl_name = p.get("full_name") or ""
        ae_names = [a["name"] for a in aes] + ([tl_name] if tl_name else [])

        teams.append({
            "tl_email": email,
            "tl_name": tl_name,
            "team": p.get("team_name") or tl_name or email,
            "ae_names": ae_names,
            "ae_emails": [a["email"] for a in aes],
        })

    return teams


# ─────────────────────────────────────────────────────────────
# MONDAY
# ─────────────────────────────────────────────────────────────

def _build_monday(team_info: dict, today: date) -> dict:
    ae_names = team_info["ae_names"]
    ae_emails = team_info.get("ae_emails", [])
    monday, sunday = _week_boundaries(today)
    month_start = _first_of_month(today).isoformat()

    # ── demos_booked: deal_ui stage in DEMO, then check deals for meeting this week ──
    demos_booked = 0
    demos_booked_by_ae: dict[str, int] = {}
    try:
        demo_resp = (
            supabase.table("deal_ui")
            .select("deal_id, pae")
            .in_("stage", list(DEMO))
            .in_("pae", ae_names)
            .execute()
        )
        pae_map = {d["deal_id"]: d.get("pae") or "?" for d in (demo_resp.data or [])}
        demo_deal_ids = list(pae_map.keys())
        if demo_deal_ids:
            monday_utc = f"{monday.isoformat()}T00:00:00Z"
            sunday_utc = f"{sunday.isoformat()}T23:59:59Z"
            for i in range(0, len(demo_deal_ids), 200):
                batch = demo_deal_ids[i:i + 200]
                meetings_resp = (
                    supabase.table("deals")
                    .select("id")
                    .in_("id", batch)
                    .gte("hs_next_meeting_start_time", monday_utc)
                    .lte("hs_next_meeting_start_time", sunday_utc)
                    .execute()
                )
                for m in (meetings_resp.data or []):
                    demos_booked += 1
                    ae = pae_map.get(m["id"], "?")
                    demos_booked_by_ae[ae] = demos_booked_by_ae.get(ae, 0) + 1
    except Exception as e:
        print(f"    demos_booked failed: {e}")

    # ── wons: week + month cumulative ──
    wons_month, mr_month = _won_deals(ae_names, month_start)
    target_mrr = _team_target(team_info["team"], today, ae_emails)
    consecucion = round(mr_month / target_mrr * 100, 1) if target_mrr > 0 else 0

    # ── whales: closing + evaluating deals with MRR > 2000 ──
    whales = []
    try:
        resp = (
            supabase.table("deal_ui")
            .select("deal_name_full, mrr, action_signal, pae, deal_momentum, stage")
            .in_("pae", ae_names)
            .in_("macro_stage", ["closing", "evaluating"])
            .gt("mrr", 2000)
            .order("mrr", desc=True)
            .execute()
        )
        for d in (resp.data or []):
            whales.append({
                "deal_name": d.get("deal_name_full") or "?",
                "mrr": float(d.get("mrr") or 0),
                "signal": d.get("action_signal") or "",
                "ae": d.get("pae") or "",
                "stage": d.get("stage") or "",
                "momentum": d.get("deal_momentum") or "",
            })
    except Exception:
        pass

    # ── closing_this_week: deals in closing with close_date_hs this week ──
    closing_this_week = []
    mr_expected = 0.0
    try:
        resp = (
            supabase.table("deal_ui")
            .select("deal_name_full, deal_id, mrr, close_probability, close_date_hs, pae, stage, deal_momentum")
            .in_("stage", list(CLOSING))
            .in_("pae", ae_names)
            .gte("close_date_hs", monday.isoformat())
            .lte("close_date_hs", sunday.isoformat())
            .execute()
        )
        for d in (resp.data or []):
            mrr = float(d.get("mrr") or 0)
            prob = float(d.get("close_probability") or 0)
            closing_this_week.append({
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
    except Exception:
        pass

    return {
        "demos_booked": demos_booked,
        "demos_held": 0,
        "mr_closed": 0,
        "mr_expected": round(mr_expected, 2),
        "wons_week": 0,
        "wons_month": wons_month,
        "mr_closed_month": round(mr_month, 2),
        "consecucion_pct": consecucion,
        "target_mrr": round(target_mrr, 2),
        "data": {
            "demos_booked_by_ae": demos_booked_by_ae,
            "closing_this_week": closing_this_week,
            "whales": whales,
        },
    }


# ─────────────────────────────────────────────────────────────
# FRIDAY
# ─────────────────────────────────────────────────────────────

def _build_friday(team_info: dict, today: date) -> dict:
    ae_names = team_info["ae_names"]
    ae_emails = team_info.get("ae_emails", [])
    monday, _ = _week_boundaries(today)
    monday_ts = f"{monday.isoformat()}T00:00:00"
    friday_ts = f"{today.isoformat()}T23:59:59"
    month_start = _first_of_month(today).isoformat()

    # ── demos_held: deals with after_demo_date this week — by AE + MRR ──
    demos_held = 0
    demos_held_by_ae: dict[str, int] = {}
    demos_held_mrr = 0.0
    try:
        resp = (
            supabase.table("deal_ui")
            .select("deal_id, pae, mrr")
            .in_("pae", ae_names)
            .gte("after_demo_date", monday_ts)
            .lte("after_demo_date", friday_ts)
            .execute()
        )
        for d in (resp.data or []):
            demos_held += 1
            ae = d.get("pae") or "?"
            demos_held_by_ae[ae] = demos_held_by_ae.get(ae, 0) + 1
            demos_held_mrr += float(d.get("mrr") or 0)
    except Exception as e:
        print(f"    demos_held failed: {e}")

    # ── wons: week + month cumulative — per-deal detail ──
    wons_week, mr_closed = _won_deals(ae_names, monday.isoformat(), today.isoformat())
    wons_month, mr_month = _won_deals(ae_names, month_start)
    target_mrr = _team_target(team_info["team"], today, ae_emails)
    consecucion = round(mr_month / target_mrr * 100, 1) if target_mrr > 0 else 0

    won_deals = []
    try:
        won_resp = (
            supabase.table("deal_ui")
            .select("deal_name_full, mrr, pae")
            .in_("stage", WON_ALL)
            .in_("pae", ae_names)
            .gte("close_date_hs", monday.isoformat())
            .lte("close_date_hs", today.isoformat())
            .execute()
        )
        for d in (won_resp.data or []):
            won_deals.append({
                "deal_name": d.get("deal_name_full") or "?",
                "mrr": float(d.get("mrr") or 0),
                "ae": d.get("pae") or "",
            })
    except Exception as e:
        print(f"    won_deals failed: {e}")

    # ── lost_deals: deals lost this week, enrich with deal_analysis + closed_lost_reason ──
    lost_deals = []
    learnings = []
    red_flag = None
    try:
        lost_resp = (
            supabase.table("deal_ui")
            .select("deal_id, deal_name_full, mrr, pae")
            .in_("stage", LOST_ALL)
            .in_("pae", ae_names)
            .gte("close_date_hs", monday.isoformat())
            .lte("close_date_hs", today.isoformat())
            .execute()
        )
        lost_deal_ids = [d["deal_id"] for d in (lost_resp.data or [])]

        # Batch-fetch deal_analysis postmortems
        analysis_map = {}
        if lost_deal_ids:
            for i in range(0, len(lost_deal_ids), 200):
                batch = lost_deal_ids[i:i + 200]
                a_resp = (
                    supabase.table("deal_analysis")
                    .select("deal_id, outcome_summary, what_failed")
                    .in_("deal_id", batch)
                    .execute()
                )
                for a in (a_resp.data or []):
                    analysis_map[a["deal_id"]] = a

        # Batch-fetch closed_lost_reason from deals table
        reason_map = {}
        if lost_deal_ids:
            for i in range(0, len(lost_deal_ids), 200):
                batch = lost_deal_ids[i:i + 200]
                r_resp = (
                    supabase.table("deals")
                    .select("id, closed_lost_reason")
                    .in_("id", batch)
                    .execute()
                )
                for r in (r_resp.data or []):
                    reason_map[r["id"]] = r.get("closed_lost_reason") or ""

        for d in (lost_resp.data or []):
            did = d["deal_id"]
            analysis = analysis_map.get(did, {})
            postmortem = analysis.get("outcome_summary") or ""
            what_failed = analysis.get("what_failed") or ""
            lost_deals.append({
                "deal_name": d.get("deal_name_full") or "?",
                "mrr": float(d.get("mrr") or 0),
                "ae": d.get("pae") or "",
                "lost_reason": reason_map.get(did, ""),
                "postmortem": postmortem,
                "what_failed": what_failed,
            })
            if what_failed:
                learnings.append({
                    "deal_name": d.get("deal_name_full") or "?",
                    "text": what_failed,
                })

        # Red flag: highest-MRR lost deal this week
        if lost_deals:
            biggest = max(lost_deals, key=lambda x: x["mrr"])
            if biggest["mrr"] > 0:
                red_flag = {
                    "deal": biggest["deal_name"],
                    "amount": biggest["mrr"],
                    "reason": biggest["lost_reason"],
                    "pae": biggest["ae"],
                    "narrative": biggest["postmortem"],
                }
    except Exception as e:
        print(f"    lost_deals failed: {e}")

    # ── coaching_flags: from pae_audits this week, filtered to team members only ──
    coaching_flags = []
    ae_names_lower = [n.lower() for n in ae_names]
    try:
        ae_deals_resp = (
            supabase.table("deal_ui")
            .select("deal_id")
            .in_("pae", ae_names)
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
                    owner = (a.get("owner_name") or "").lower()
                    if not any(name in owner for name in ae_names_lower):
                        continue
                    coaching_flags.append({
                        "ae": a.get("owner_name") or "",
                        "flag": a.get("top_coaching_flag") or "",
                    })
    except Exception as e:
        print(f"    coaching_flags failed: {e}")

    return {
        "demos_booked": 0,
        "demos_held": demos_held,
        "demos_held_mrr": round(demos_held_mrr, 2),
        "mr_closed": round(mr_closed, 2),
        "mr_expected": 0,
        "wons_week": wons_week,
        "wons_month": wons_month,
        "mr_closed_month": round(mr_month, 2),
        "consecucion_pct": consecucion,
        "target_mrr": round(target_mrr, 2),
        "red_flag": red_flag,
        "data": {
            "demos_held_by_ae": demos_held_by_ae,
            "won_deals": won_deals,
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

    iso_cal = today.isocalendar()
    iso_week = f"{iso_cal.year}-W{iso_cal.week:02d}"
    day_label = "MONDAY" if snapshot_day == 1 else "FRIDAY"

    print("=" * 60)
    print(f"SNAPSHOT — {day_label} {iso_week}")
    print("=" * 60)

    print("\n▸ RESOLVE TEAMS")
    try:
        teams = _resolve_teams()
        print(f"  {len(teams)} teams found")
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        traceback.print_exc()
        return

    print(f"\n▸ BUILD SNAPSHOTS")
    generated = 0

    for team_info in teams:
        tl = team_info["tl_email"]
        team_name = team_info["team"]
        n_aes = len(team_info["ae_names"])

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
                "wons_week": metrics["wons_week"],
                "wons_month": metrics["wons_month"],
                "mr_closed_month": metrics["mr_closed_month"],
                "consecucion_pct": metrics["consecucion_pct"],
                "data": metrics["data"],
            }

            rf = metrics.get("red_flag")
            row["lost_red_flag_deal"] = rf["deal"] if rf else None
            row["lost_red_flag_amount"] = rf["amount"] if rf else None
            row["lost_red_flag_reason"] = rf["reason"] if rf else None
            row["lost_red_flag_pae"] = rf["pae"] if rf else None
            row["lost_red_flag_narrative"] = rf["narrative"] if rf else None

            supabase.table("team_snapshots").upsert(
                row, on_conflict="tl_email,iso_week,snapshot_day"
            ).execute()

            print(f"  ✓ {team_name} ({n_aes} AEs, TL: {tl})")
            generated += 1

        except Exception as e:
            print(f"  ✗ {team_name}: {e}")
            traceback.print_exc()

    print(f"\n{'=' * 60}")
    print(f"SNAPSHOT DONE: {generated}/{len(teams)} teams")
    print("=" * 60)
