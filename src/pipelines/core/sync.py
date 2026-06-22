"""
Core Sync — Phase 1 of the CORE pipeline.

Finds deals that changed in HubSpot, fetches their properties,
resolves team/owner, and upserts to Supabase.
Marks context_stale=True if there's new activity (call/email/meeting/note).

Zero Claude calls. Pure HubSpot → Supabase sync.
Everything comes from config — this file only orchestrates.
"""

from datetime import datetime, timezone, timedelta

from src.config import (
    ACTIVE_TEAMS,
    ACTIVE_PIPELINE_IDS,
    PARTNER_SEARCH,
    TEAM_STRING_SEARCH,
    OWNER_SEARCH_PIPELINES,
    SYNC_STRATEGY,
    SYNC_CONFIG,
    CORE_TRIGGER,
    HS_DEAL_PROPS,
    HS_PIPELINE_DATE_MAP,
    HS_TO_SUPABASE,
    HS_ALL_DEAL_PROPS,
    HS_ALL_MEETING_SYNC_PROPS,
    HS_TO_SUPABASE_MEETINGS,
    HUBSPOT_PIPELINE_IDS,
    HUBSPOT_PIPELINE_NAMES,
    EXCLUDE_PIPELINE_IDS,
    PARTNER_NAME_MAP,
    STAGES_EXCLUDE_FROM_SYNC_LOWER,
    UPSERT_BATCH_SIZE,
    ATLAS_CONFIG,
    get_deal_team,
    get_email_by_owner_id,
    get_display_name,
    get_owner_ids_for_team,
)
from src.db.client import supabase
from src.integrations import hubspot

_SC = SYNC_CONFIG
_CT = CORE_TRIGGER
SEARCH_URL = "/crm/v3/objects/deals/search"


# ── Step 1: Determine what to search ────────────────────────────────────────

def _get_since_ms() -> int | None:
    result = (
        supabase.table(_SC["deals_table"])
        .select(_SC["col_last_synced"])
        .not_.is_(_SC["col_last_synced"], "null")
        .order(_SC["col_last_synced"], desc=True)
        .limit(1)
        .execute()
    )
    if result.data and result.data[0].get(_SC["col_last_synced"]):
        last = datetime.fromisoformat(result.data[0][_SC["col_last_synced"]])
        lookback = SYNC_STRATEGY["incremental_lookback_minutes"]
        return int((last - timedelta(minutes=lookback)).timestamp() * 1000)
    return None


# ── Step 2: Search HubSpot for deals (3 phases) ────────────────────────────

def _search_all(filter_groups: list[dict]) -> set[str]:
    ids: set[str] = set()
    after = None
    while True:
        body: dict = {
            "filterGroups": filter_groups,
            "properties": [_SC["hs_object_id_prop"]],
            "limit": 100,
        }
        if after:
            body["after"] = after
        data = hubspot.post(SEARCH_URL, body)
        for r in data.get("results", []):
            ids.add(r["id"])
        after = data.get("paging", {}).get("next", {}).get("after")
        if not after:
            break
    return ids


def _mod_filter(since_ms: int | None) -> dict | None:
    if since_ms is None:
        return None
    return {"propertyName": _CT["search_property"], "operator": "GTE", "value": str(since_ms)}


def _search_phase1(since_ms: int | None) -> set[str]:
    ids: set[str] = set()
    mf = _mod_filter(since_ms)
    filter_groups = []
    for team, search in PARTNER_SEARCH.items():
        if team not in ACTIVE_TEAMS:
            continue
        for pn in search.get("hs_partner_names", []):
            filters = [{"propertyName": _SC["hs_partner_name_prop"], "operator": "EQ", "value": pn}]
            if mf:
                filters.append(mf)
            filter_groups.append({"filters": filters})
    for i in range(0, len(filter_groups), 5):
        ids |= _search_all(filter_groups[i:i + 5])
    return ids


def _search_phase2(since_ms: int | None) -> set[str]:
    ids: set[str] = set()
    mf = _mod_filter(since_ms)
    for team_string, team_name in TEAM_STRING_SEARCH.items():
        if team_name not in ACTIVE_TEAMS:
            continue
        filters = [{"propertyName": _SC["hs_team_string_prop"], "operator": "EQ", "value": team_string}]
        if mf:
            filters.append(mf)
        ids |= _search_all([{"filters": filters}])
    return ids


def _search_phase3(since_ms: int | None) -> set[str]:
    ids: set[str] = set()
    mf = _mod_filter(since_ms)
    batch_size = SYNC_STRATEGY["batch_owner_ids_per_group"]
    for org_type, pipelines in OWNER_SEARCH_PIPELINES.items():
        if org_type == "DS":
            teams = [t for t in ACTIVE_TEAMS if t.startswith("DS ")]
        elif org_type == "XL":
            teams = ["XL"] if "XL" in ACTIVE_TEAMS else []
        elif org_type == "Partners":
            teams = [t for t in ACTIVE_TEAMS if t in PARTNER_SEARCH]
        else:
            continue
        all_oids = list({oid for t in teams for oid in get_owner_ids_for_team(t)})
        if not all_oids:
            continue
        pipeline_ids = [HUBSPOT_PIPELINE_NAMES.get(p, p) for p in pipelines]
        for pid in pipeline_ids:
            for i in range(0, len(all_oids), batch_size):
                batch_oids = all_oids[i:i + batch_size]
                filter_groups = []
                for oid in batch_oids:
                    filters = [
                        {"propertyName": _SC["hs_owner_id_prop"], "operator": "EQ", "value": oid},
                        {"propertyName": _SC["hs_pipeline_prop"], "operator": "EQ", "value": pid},
                    ]
                    if mf:
                        filters.append(mf)
                    filter_groups.append({"filters": filters})
                ids |= _search_all(filter_groups)
    return ids


def _find_deal_ids(since_ms: int | None) -> set[str]:
    print("  Phase 1: searching by partner_name ...")
    p1 = _search_phase1(since_ms)
    print(f"    {len(p1)} deals")
    print("  Phase 2: searching by team_string ...")
    p2 = _search_phase2(since_ms)
    print(f"    {len(p2)} deals")
    print("  Phase 3: searching by owner_id ...")
    p3 = _search_phase3(since_ms)
    print(f"    {len(p3)} deals")
    union = p1 | p2 | p3
    print(f"  Total unique: {len(union)} deals")
    return union


# ── Step 3: Fetch properties + associations from HubSpot ────────────────────

def _fetch_owners() -> dict[str, dict]:
    owners: dict[str, dict] = {}
    url = "/crm/v3/owners?limit=100"
    while url:
        data = hubspot.get(url)
        for o in data.get("results", []):
            first = o.get("firstName") or ""
            last = o.get("lastName") or ""
            name = f"{first} {last}".strip() or o.get("email", "")
            owners[o["id"]] = {"name": name, "email": o.get("email", "")}
        next_link = data.get("paging", {}).get("next", {}).get("link")
        from src.config import HUBSPOT_BASE_URL
        url = next_link.replace(HUBSPOT_BASE_URL, "") if next_link else ""
    return owners


def _batch_read_deals(deal_ids: list[str]) -> list[dict]:
    results = []
    for i in range(0, len(deal_ids), 100):
        batch = deal_ids[i:i + 100]
        data = hubspot.post(
            "/crm/v3/objects/deals/batch/read",
            {"inputs": [{"id": did} for did in batch], "properties": HS_ALL_DEAL_PROPS},
        )
        results.extend(data.get("results", []))
    return results


def _fetch_company_associations(deal_ids: list[str]) -> dict[str, str]:
    company_map: dict[str, str] = {}
    for i in range(0, len(deal_ids), 100):
        batch = deal_ids[i:i + 100]
        data = hubspot.post(
            "/crm/v4/associations/deals/companies/batch/read",
            {"inputs": [{"id": did} for did in batch]},
        )
        for result in data.get("results", []):
            did = str(result.get("from", {}).get("id", ""))
            to_list = result.get("to", [])
            if did and to_list:
                company_map[did] = str(to_list[0].get("toObjectId", ""))
    return company_map


# ── Step 4: Resolve each deal ────────────────────────────────────────────────

def _resolve_deal(hs_deal: dict, owners: dict, company_map: dict) -> dict | None:
    props = hs_deal.get("properties", {})

    # Pipeline filter
    pipeline_id = props.get(_SC["hs_pipeline_prop"]) or ""
    if pipeline_id in EXCLUDE_PIPELINE_IDS:
        return None
    pipeline_name = HUBSPOT_PIPELINE_IDS.get(pipeline_id, pipeline_id)

    # Stage filter
    stage = props.get(_SC["hs_dealstage_prop"]) or ""
    if stage.lower() in STAGES_EXCLUDE_FROM_SYNC_LOWER:
        return None

    # Map HS properties → Supabase columns
    row = {}
    for hs_prop, info in HS_DEAL_PROPS.items():
        val = props.get(hs_prop)
        if val is not None and val != "":
            row[info["column"]] = val

    # Map stage date properties
    for hs_prop, info in HS_PIPELINE_DATE_MAP.items():
        val = props.get(hs_prop)
        if val is not None and val != "":
            row[info["column"]] = val

    # Override pipeline_name
    row[HS_DEAL_PROPS[_SC["hs_pipeline_prop"]]["column"]] = pipeline_name

    # Resolve PAE/PBD names
    owner_id = props.get(_SC["hs_owner_id_prop"]) or ""
    creator_id = props.get(_SC["hs_created_by_prop"]) or ""
    owner_email = get_email_by_owner_id(str(owner_id))
    creator_email = get_email_by_owner_id(str(creator_id))

    row[_SC["col_pae"]] = get_display_name(owner_email) if owner_email else ""
    row[_SC["col_pbd"]] = get_display_name(creator_email) if creator_email else ""

    if not row[_SC["col_pae"]] and owner_id in owners:
        row[_SC["col_pae"]] = owners[owner_id].get("name", "")
    if not row[_SC["col_pbd"]] and creator_id in owners:
        row[_SC["col_pbd"]] = owners[creator_id].get("name", "")

    # Resolve team
    team_string = props.get(_SC["hs_team_string_prop"]) or ""
    partner_name = props.get(_SC["hs_partner_name_prop"]) or ""
    row[_SC["col_team"]] = get_deal_team(pipeline_name, partner_name, owner_email, team_string)

    # Company association → crm_id
    deal_id = row.get(_SC["col_deal_id"], "")
    row[ATLAS_CONFIG["deal_column"]] = company_map.get(deal_id)

    # Timestamp
    row[_SC["col_last_synced"]] = datetime.now(timezone.utc).isoformat()

    return row


# ── Step 5: Detect if CORE should activate ──────────────────────────────────

def _detect_stale(rows: list[dict]) -> list[dict]:
    if not rows:
        return rows

    col_deal_id = _SC["col_deal_id"]
    col_activity = _CT["supabase_column"]
    col_stale = _SC["col_context_stale"]

    deal_ids = [r[col_deal_id] for r in rows if r.get(col_deal_id)]
    current_activity: dict[str, str] = {}

    for i in range(0, len(deal_ids), 200):
        batch = deal_ids[i:i + 200]
        result = (
            supabase.table(_SC["deals_table"])
            .select(f"{col_deal_id}, {col_activity}")
            .in_(col_deal_id, batch)
            .execute()
        )
        for d in (result.data or []):
            current_activity[d[col_deal_id]] = d.get(col_activity) or ""

    for row in rows:
        did = row.get(col_deal_id, "")
        new_activity = row.get(col_activity) or ""
        old_activity = current_activity.get(did, "")
        if new_activity and new_activity != old_activity:
            row[col_stale] = True

    return rows


# ── Step 6: Upsert to Supabase ──────────────────────────────────────────────

def _upsert_deals(rows: list[dict]) -> int:
    written = 0
    for i in range(0, len(rows), UPSERT_BATCH_SIZE):
        batch = rows[i:i + UPSERT_BATCH_SIZE]
        result = (
            supabase.table(_SC["deals_table"])
            .upsert(batch, on_conflict=_SC["deals_upsert_key"])
            .execute()
        )
        written += len(result.data or [])
    return written


def _sync_meetings(deal_ids: list[str]) -> int:
    if not deal_ids:
        return 0

    meeting_rows = []
    for did in deal_ids:
        try:
            assoc = hubspot.get(f"/crm/v4/objects/deals/{did}/associations/meetings?limit=100")
            meeting_ids = [str(a.get("toObjectId", "")) for a in assoc.get("results", []) if a.get("toObjectId")]
            if not meeting_ids:
                continue
            mdata = hubspot.post(
                "/crm/v3/objects/meetings/batch/read",
                {"inputs": [{"id": mid} for mid in meeting_ids], "properties": HS_ALL_MEETING_SYNC_PROPS},
            )
            for m in mdata.get("results", []):
                mp = m.get("properties", {})
                row = {
                    _SC["meetings_col_deal_id"]: did,
                    _SC["meetings_col_meeting_id"]: m["id"],
                }
                for hs_prop, col in HS_TO_SUPABASE_MEETINGS.items():
                    val = mp.get(hs_prop)
                    if val is not None:
                        row[col] = val
                meeting_rows.append(row)
        except Exception as e:
            print(f"    Meeting fetch error for deal {did}: {e}")

    if not meeting_rows:
        return 0

    seen = set()
    unique = []
    for r in meeting_rows:
        mid = r.get(_SC["meetings_upsert_key"])
        if mid and mid not in seen:
            seen.add(mid)
            unique.append(r)

    written = 0
    for i in range(0, len(unique), UPSERT_BATCH_SIZE):
        batch = unique[i:i + UPSERT_BATCH_SIZE]
        result = (
            supabase.table(_SC["meetings_table"])
            .upsert(batch, on_conflict=_SC["meetings_upsert_key"])
            .execute()
        )
        written += len(result.data or [])
    return written


# ── Main entry point ─────────────────────────────────────────────────────────

def run(full: bool = False) -> dict:
    print("=" * 60)
    print(f"SYNC DEALS — {'FULL' if full else 'INCREMENTAL'}")
    print(f"Active teams: {sorted(ACTIVE_TEAMS)}")
    print("=" * 60)

    hubspot.reset_counter()

    # Step 1
    since_ms = None if full else _get_since_ms()
    if since_ms:
        print(f"\n1. Incremental since: {datetime.fromtimestamp(since_ms / 1000, tz=timezone.utc).isoformat()}")
    else:
        print("\n1. Full sync (no cutoff)")

    # Step 2
    print("\n2. Searching HubSpot ...")
    deal_ids = _find_deal_ids(since_ms)
    if not deal_ids:
        print("   No deals found.")
        return {"synced": 0, "stale": 0, "meetings": 0}

    # Step 3
    deal_id_list = sorted(deal_ids)
    print(f"\n3. Fetching properties for {len(deal_id_list)} deals ...")
    owners = _fetch_owners()
    print(f"   {len(owners)} owners loaded")
    hs_deals = _batch_read_deals(deal_id_list)
    print(f"   {len(hs_deals)} deals read")
    print("   Fetching company associations ...")
    company_map = _fetch_company_associations(deal_id_list)
    print(f"   {len(company_map)} company links")

    # Step 4
    print("\n4. Resolving deals ...")
    rows = []
    skipped = 0
    for hd in hs_deals:
        row = _resolve_deal(hd, owners, company_map)
        if row:
            rows.append(row)
        else:
            skipped += 1
    print(f"   {len(rows)} resolved, {skipped} excluded")

    # Step 5
    print("\n5. Detecting activity changes ...")
    rows = _detect_stale(rows)
    stale = sum(1 for r in rows if r.get(_SC["col_context_stale"]))
    print(f"   {stale} deals with new activity → context_stale=True")

    # Step 6
    print(f"\n6. Upserting {len(rows)} deals ...")
    written = _upsert_deals(rows)
    print(f"   {written} deals upserted")

    print("\n7. Syncing meetings ...")
    meeting_deal_ids = [r[_SC["col_deal_id"]] for r in rows if r.get(_SC["col_deal_id"])]
    meetings = _sync_meetings(meeting_deal_ids)
    print(f"   {meetings} meetings upserted")

    print(f"\n   HubSpot API requests: {hubspot.total_requests()}")
    print("=" * 60)

    return {"synced": written, "stale": stale, "meetings": meetings}
