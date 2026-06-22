"""
Detect deals with meetings today, timezone-aware per team.
Source 1: deals.hs_next_meeting_start_time (HubSpot property)
Source 2: deal_meetings table (HubSpot meeting engagements)
Source 3: Google Calendar API → resolve attendee domains to deals
Everything from config.
"""

from datetime import datetime, timezone

from src.config import (
    INTELLIGENCE_CONFIG,
    HOURLY_CONFIG,
    ACTIVE_TEAMS,
    CALENDAR_ACTIVE_REPS,
    ALL_PARTNER_DOMAINS,
    FACTORIAL_DOMAINS,
    GENERIC_EMAIL_DOMAINS,
    MAX_DEALS_PER_DOMAIN,
    get_tz,
)
from src.db.client import supabase
from src.integrations import gcal

_I = INTELLIGENCE_CONFIG
_H = HOURLY_CONFIG

_IGNORE_DOMAINS = FACTORIAL_DOMAINS | ALL_PARTNER_DOMAINS | GENERIC_EMAIL_DOMAINS


def _today_range_for_team(team: str) -> tuple[str, str]:
    """Return (start_utc, end_utc) ISO strings for 'today' in the team's timezone."""
    tz = get_tz(team)
    now_local = datetime.now(tz)
    start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    end = now_local.replace(hour=23, minute=59, second=59, microsecond=0)
    return start.astimezone(timezone.utc).isoformat(), end.astimezone(timezone.utc).isoformat()


def _broadest_range() -> tuple[str, str]:
    """Get the broadest UTC range across all team timezones."""
    ranges = [_today_range_for_team(t) for t in ACTIVE_TEAMS]
    if not ranges:
        now = datetime.now(timezone.utc)
        start = now.replace(hour=0, minute=0, second=0).isoformat()
        end = now.replace(hour=23, minute=59, second=59).isoformat()
        return start, end
    return min(r[0] for r in ranges), max(r[1] for r in ranges)


def _get_deal_team_map() -> dict[str, str]:
    """Build deal_id → team map for all deals."""
    resp = (
        supabase.table(_I["deals_table"])
        .select(f"{_I['deal_col_id']}, {_I['deal_col_team']}")
        .execute()
    )
    return {d[_I["deal_col_id"]]: d.get(_I["deal_col_team"]) or "" for d in (resp.data or [])}


def _get_deal_owner_map() -> dict[str, str]:
    """Build deal_id → owner (PAE or PBD) map for all deals."""
    resp = (
        supabase.table(_I["deals_table"])
        .select(f"{_I['deal_col_id']}, {_I['deal_col_pae']}, {_I['deal_col_pbd']}")
        .execute()
    )
    return {d[_I["deal_col_id"]]: d.get(_I["deal_col_pae"]) or d.get(_I["deal_col_pbd"]) or "" for d in (resp.data or [])}


def _is_today_for_team(meeting_time: str, team: str) -> bool:
    """Check if a meeting timestamp falls within 'today' for the team's timezone."""
    if not meeting_time or not team:
        return False
    start_utc, end_utc = _today_range_for_team(team)
    return start_utc <= meeting_time < end_utc


# ── Source 3: Calendar resolver ─────────────────────────────────────────

def _extract_domain(email: str) -> str:
    return email.split("@")[-1].lower() if "@" in email else ""


def _prospect_domains(attendees: list[dict]) -> set[str]:
    domains = set()
    for att in attendees:
        domain = _extract_domain(att.get("email", ""))
        if domain and domain not in _IGNORE_DOMAINS:
            domains.add(domain)
    return domains


_domain_cache: dict[str, list[str]] = {}


def _resolve_domain_to_deal_ids(domain: str) -> list[str]:
    """Find open deal UUIDs matching a prospect domain."""
    if domain in _domain_cache:
        return _domain_cache[domain]

    deal_ids = []

    # Strategy 1: deals.contacts_info contains @domain
    try:
        resp = (
            supabase.table(_I["deals_table"])
            .select(_I["deal_col_id"])
            .ilike("contacts_info", f"%@{domain}%")
            .execute()
        )
        deal_ids = [r[_I["deal_col_id"]] for r in (resp.data or [])]
    except Exception:
        pass

    # Strategy 2: atlas.website contains domain → crm_id → deals
    if not deal_ids:
        try:
            atlas_resp = (
                supabase.table(_I["atlas_table"])
                .select("crm_id")
                .ilike("website", f"%{domain}%")
                .execute()
            )
            for a in (atlas_resp.data or []):
                crm_id = a.get("crm_id")
                if crm_id:
                    deals_resp = (
                        supabase.table(_I["deals_table"])
                        .select(_I["deal_col_id"])
                        .eq(_I["fk_crm_id"], crm_id)
                        .execute()
                    )
                    deal_ids.extend(r[_I["deal_col_id"]] for r in (deals_resp.data or []))
        except Exception:
            pass

    if len(deal_ids) > MAX_DEALS_PER_DOMAIN:
        deal_ids = []

    _domain_cache[domain] = deal_ids
    return deal_ids


def _resolve_event_to_deal_ids(attendees: list[dict]) -> list[str]:
    """Resolve a calendar event to deal IDs via attendee domains."""
    domains = _prospect_domains(attendees)
    if not domains:
        return []
    seen = set()
    result = []
    for domain in domains:
        for did in _resolve_domain_to_deal_ids(domain):
            if did not in seen:
                result.append(did)
                seen.add(did)
    return result


# ── Main ────────────────────────────────────────────────────────────────

def detect_today() -> dict[str, dict]:
    """Return dict of {deal_uuid: {team}} for deals with meetings today.
    Checks per-team timezone. 3 sources: HubSpot property, deal_meetings, Google Calendar."""

    results: dict[str, dict] = {}
    deal_team_map = _get_deal_team_map()
    deal_owner_map = _get_deal_owner_map()
    earliest, latest = _broadest_range()

    # ── Source 1: deals.hs_next_meeting_start_time ──
    for team in ACTIVE_TEAMS:
        start_utc, end_utc = _today_range_for_team(team)
        try:
            r1 = (
                supabase.table(_I["deals_table"])
                .select(f"{_I['deal_col_id']}, {_I['deal_col_team']}, {_I['deal_col_pae']}, {_I['deal_col_pbd']}")
                .eq(_I["deal_col_team"], team)
                .gte(_H["deals_meeting_col"], start_utc)
                .lt(_H["deals_meeting_col"], end_utc)
                .execute()
            )
            for d in (r1.data or []):
                did = d[_I["deal_col_id"]]
                results[did] = {"team": team, "rep": d.get(_I["deal_col_pae"]) or d.get(_I["deal_col_pbd"]) or ""}
        except Exception as e:
            print(f"    Source 1 ({team}): {e}")

    # ── Source 2: deal_meetings ──
    try:
        r2 = (
            supabase.table(_H["deal_meetings_table"])
            .select(f"{_H['deal_meetings_deal_col']}, {_H['deal_meetings_start_col']}")
            .gte(_H["deal_meetings_start_col"], earliest)
            .lt(_H["deal_meetings_start_col"], latest)
            .not_.is_(_H["deal_meetings_deal_col"], "null")
            .execute()
        )
        for m in (r2.data or []):
            did = m[_H["deal_meetings_deal_col"]]
            team = deal_team_map.get(did, "")
            if team and _is_today_for_team(m.get(_H["deal_meetings_start_col"], ""), team):
                results[did] = {"team": team, "rep": deal_owner_map.get(did, "")}
    except Exception as e:
        print(f"    Source 2 (deal_meetings): {e}")

    # ── Source 3: Google Calendar → resolve to deals ──
    source1_2_ids = set(results.keys())

    try:
        for rep_email in CALENDAR_ACTIVE_REPS:
            events = gcal.fetch_events(rep_email, earliest, latest)
            for ev in events:
                deal_ids = _resolve_event_to_deal_ids(ev.get("attendees", []))
                for did in deal_ids:
                    if did in source1_2_ids:
                        continue
                    team = deal_team_map.get(did, "")
                    if team and _is_today_for_team(ev.get("meeting_start", ""), team):
                        results[did] = {"team": team, "rep": rep_email}
    except Exception as e:
        print(f"    Source 3 (calendar): {e}")

    _domain_cache.clear()
    return results
