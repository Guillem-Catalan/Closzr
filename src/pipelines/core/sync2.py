"""
Core Sync v2 — Phase 1 of the CORE pipeline.

Finds deals that changed in HubSpot, fetches their properties,
resolves team/owner, and upserts to Supabase.
Marks context_stale=True if there's new activity.

Zero Claude calls. Pure HubSpot → Supabase sync.

Uses only internal names (schema + org + config2).
"""

from datetime import datetime, timezone, timedelta

from src import schema, org
from src.config2 import (
    ACTIVE_TEAMS,
    STALE_COOLDOWN_HOURS,
    UPSERT_BATCH_SIZE,
    get_deal_team,
    get_email_by_owner_id,
    get_display_name,
    get_owner_ids_for_team,
)
from src.db.client import supabase
from src.integrations import hubspot

# ── Internal-name shortcuts ────────────────────────────────────────────────

_col = schema.col
_tbl = schema.tbl

DEALS_TABLE       = _tbl("deals")
DEALS_UPSERT_KEY  = schema.upsert_key("deals")

COL_DEAL_ID       = _col("deal_id")
COL_STAGE         = _col("stage")
COL_PIPELINE      = _col("pipeline")
COL_PAE           = _col("pae")
COL_PBD           = _col("pbd")
COL_TEAM          = _col("team")
COL_PARTNER       = _col("partner")
COL_CRM_ID        = _col("crm_id")
COL_LAST_SYNCED   = _col("last_synced")
COL_STALE         = _col("context_stale")
COL_LAST_ACTIVITY = _col("last_activity")
COL_STALE_CHECKED = _col("stale_checked_at")

# org-level external names
_F = org.CRM_DEAL_PROPERTIES
_SD = org.CRM_STAGE_DATE_PROPERTIES
_STAGE_MAP = org.CRM_STAGE_MAP
_PIPELINE_MAP = org.CRM_PIPELINE_MAP
_PARTNER_OBJECTS = org.CRM_PARTNER_OBJECTS
_STAGE_TO_INTERNAL = org.CRM_STAGE_LABEL_TO_INTERNAL
_STRATEGY = org.CRM_SYNC_STRATEGY
_TRIGGER = org.CRM_CORE_TRIGGER

SEARCH_URL = org.API_ENDPOINTS["deal_search"]
HUBSPOT_BASE = org.API_ENDPOINTS["hubspot"]

_OWN = org.CRM_OWNER_RESPONSE_FIELDS

# CRM property names resolved from internal names — never hardcoded
_HS_STAGE     = org.crm_prop("stage")
_HS_PIPELINE  = org.crm_prop("pipeline")
_HS_OWNER     = org.crm_prop("owner_id")
_HS_CREATOR   = org.crm_prop("creator_id")
_HS_ALL_IDS   = org.crm_prop("all_owner_ids")
_HS_IS_CLOSED = org.crm_prop("is_closed")


# ── Step 1: Determine what to search ──────────────────────────────────────

def _get_since_ms() -> int | None:
    result = (
        supabase.table(DEALS_TABLE)
        .select(COL_LAST_SYNCED)
        .not_.is_(COL_LAST_SYNCED, "null")
        .order(COL_LAST_SYNCED, desc=True)
        .limit(1)
        .execute()
    )
    if result.data and result.data[0].get(COL_LAST_SYNCED):
        last = datetime.fromisoformat(result.data[0][COL_LAST_SYNCED])
        lookback = _STRATEGY["incremental_lookback_minutes"]
        return int((last - timedelta(minutes=lookback)).timestamp() * 1000)
    return None


# ── Step 2: Search HubSpot for deals ─────────────────────────────────────

def _search_all(filter_groups: list[dict]) -> set[str]:
    ids: set[str] = set()
    after = None
    while True:
        body: dict = {
            "filterGroups": filter_groups,
            "properties": [],
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


_NOT_CLOSED = {"propertyName": _HS_IS_CLOSED, "operator": "NEQ", "value": "true"}


def _mod_filter(since_ms: int | None) -> dict | None:
    if since_ms is None:
        return None
    return {"propertyName": org.crm_prop(_TRIGGER["search_internal"]), "operator": "GTE", "value": str(since_ms)}


_ACTIVE_PIPELINE_FILTER = {
    "propertyName": _HS_PIPELINE, "operator": "IN",
    "values": org.CRM_ACTIVE_PIPELINE_IDS,
}


def _find_deal_ids(since_ms: int | None) -> set[str]:
    all_oids = list({oid for t in ACTIVE_TEAMS for oid in get_owner_ids_for_team(t)})
    if not all_oids:
        return set()
    mf = _mod_filter(since_ms)
    ids: set[str] = set()
    for i in range(0, len(all_oids), 4):
        batch = all_oids[i:i + 4]
        filter_groups = []
        for oid in batch:
            filters = [
                {"propertyName": _HS_OWNER, "operator": "EQ", "value": oid},
                _NOT_CLOSED,
                _ACTIVE_PIPELINE_FILTER,
            ]
            if mf:
                filters.append(mf)
            filter_groups.append({"filters": filters})
        ids |= _search_all(filter_groups)
    print(f"  {len(ids)} deals from {len(all_oids)} owners")
    return ids


# ── Step 3: Fetch properties + associations from HubSpot ─────────────────

def _fetch_owners() -> dict[str, dict]:
    owners: dict[str, dict] = {}
    url = f"{org.API_ENDPOINTS['owners']}?limit=100"
    while url:
        data = hubspot.get(url)
        for o in data.get("results", []):
            first = o.get(_OWN["first_name"]) or ""
            last = o.get(_OWN["last_name"]) or ""
            name = f"{first} {last}".strip() or o.get(_OWN["email"], "")
            owners[o[_OWN["id"]]] = {"name": name, "email": o.get(_OWN["email"], "")}
        next_link = data.get("paging", {}).get("next", {}).get("link")
        url = next_link.replace(HUBSPOT_BASE, "") if next_link else ""
    return owners


def _batch_read_deals(deal_ids: list[str]) -> list[dict]:
    results = []
    for i in range(0, len(deal_ids), 100):
        batch = deal_ids[i:i + 100]
        data = hubspot.post(
            org.API_ENDPOINTS["deal_batch_read"],
            {"inputs": [{"id": did} for did in batch], "properties": org.CRM_ALL_DEAL_PROPS},
        )
        results.extend(data.get("results", []))
    return results


def _fetch_company_associations(deal_ids: list[str]) -> dict[str, str]:
    company_map: dict[str, str] = {}
    for i in range(0, len(deal_ids), 100):
        batch = deal_ids[i:i + 100]
        try:
            data = hubspot.post(
                org.API_ENDPOINTS["company_associations"],
                {"inputs": [{"id": did} for did in batch]},
            )
            if not data:
                continue
            for result in data.get("results", []):
                did = str(result.get("from", {}).get("id", ""))
                to_list = result.get("to", [])
                if did and to_list:
                    company_map[did] = str(to_list[0].get("toObjectId", ""))
        except Exception as e:
            print(f"    Company association batch {i // 100 + 1} failed: {e}")
    return company_map


def _fetch_partner_associations(deal_ids: list[str]) -> dict[str, str]:
    partner_map: dict[str, str] = {}
    for i in range(0, len(deal_ids), 100):
        batch = deal_ids[i:i + 100]
        try:
            data = hubspot.post(
                org.API_ENDPOINTS["partner_associations"].format(partner_type=org.CRM_PARTNER_OBJECT_TYPE_ID),
                {"inputs": [{"id": did} for did in batch]},
            )
            if not data:
                continue
            for result in data.get("results", []):
                did = str(result.get("from", {}).get("id", ""))
                to_list = result.get("to", [])
                if did and to_list:
                    partner_map[did] = str(to_list[0].get("toObjectId", ""))
        except Exception as e:
            print(f"    Partner assoc batch {i // 100 + 1} failed: {e}")
    return partner_map


def _to_iso(val: str) -> str | None:
    if not val:
        return None
    if val.isdigit() and len(val) >= 10:
        try:
            return datetime.fromtimestamp(int(val) / 1000, tz=timezone.utc).isoformat()
        except (ValueError, OSError):
            return None
    return val


# ── HS props whose schema type is date/datetime ─────────────────────────

_HS_DATE_PROPS = {
    hs_prop
    for hs_prop, info in _F.items()
    if schema.is_date_field(info["internal"])
}


# ── Step 4: Resolve each deal ────────────────────────────────────────────

def _resolve_deal(
    hs_deal: dict,
    owners: dict,
    company_map: dict,
    partner_map: dict,
    allow_closed: bool = False,
) -> dict | None:
    props = hs_deal.get("properties", {})

    pipeline_id = props.get(_HS_PIPELINE) or ""
    if pipeline_id in org.CRM_EXCLUDE_PIPELINE_IDS:
        return None
    pipeline_entry = _PIPELINE_MAP.get(pipeline_id)
    pipeline_name = pipeline_entry["name"] if pipeline_entry else pipeline_id

    stage_raw = props.get(_HS_STAGE) or ""
    stage_label = _STAGE_MAP.get(stage_raw, stage_raw)
    stage_internal = _STAGE_TO_INTERNAL.get(stage_label)

    if stage_internal and stage_internal in schema.EXCLUDED:
        return None
    if not allow_closed and stage_internal and stage_internal in schema.CLOSED:
        return None

    row = {}
    for hs_prop, info in _F.items():
        val = props.get(hs_prop)
        if val is not None and val != "":
            row[_col(info["internal"])] = _to_iso(val) if hs_prop in _HS_DATE_PROPS else val

    # Map stage date properties (all are dates)
    for hs_prop, info in _SD.items():
        val = props.get(hs_prop)
        if val is not None and val != "":
            row[_col(info["internal"])] = _to_iso(val)

    # Override stage with internal name (schema-compatible)
    row[COL_STAGE] = stage_internal or stage_label

    # Override pipeline_name
    row[COL_PIPELINE] = pipeline_name

    owner_id = props.get(_HS_OWNER) or ""
    creator_id = props.get(_HS_CREATOR) or ""
    owner_email = get_email_by_owner_id(str(owner_id))
    creator_email = get_email_by_owner_id(str(creator_id))

    row[COL_PAE] = get_display_name(owner_email) if owner_email else ""
    row[COL_PBD] = get_display_name(creator_email) if creator_email else ""

    if not row[COL_PAE] and owner_id in owners:
        row[COL_PAE] = owners[owner_id].get("name", "")
    if not row[COL_PBD] and creator_id in owners:
        row[COL_PBD] = owners[creator_id].get("name", "")

    if not row[COL_PBD]:
        all_ids = (props.get(_HS_ALL_IDS) or "").split(";")
        for aid in all_ids:
            aid = aid.strip()
            if not aid or aid == owner_id:
                continue
            email = get_email_by_owner_id(aid)
            if email:
                row[COL_PBD] = get_display_name(email)
                break
            if aid in owners:
                row[COL_PBD] = owners[aid].get("name", "")
                break

    deal_id = row.get(COL_DEAL_ID, "")
    row[COL_TEAM] = get_deal_team(owner_email)

    partner_id = partner_map.get(deal_id)
    if partner_id and partner_id in _PARTNER_OBJECTS:
        row[COL_PARTNER] = _PARTNER_OBJECTS[partner_id]["display"]

    # Company association → crm_id
    row[COL_CRM_ID] = company_map.get(deal_id)

    # Timestamp
    row[COL_LAST_SYNCED] = datetime.now(timezone.utc).isoformat()

    return row


# ── Step 5: Detect if CORE should activate ────────────────────────────────

def _normalize_ts(val: str) -> str:
    if not val:
        return ""
    return val.replace("+00:00", "Z").rstrip("Z").split(".")[0]


def _detect_stale(rows: list[dict]) -> list[dict]:
    if not rows:
        return rows

    col_activity = _col(_TRIGGER["activity_internal"])
    cooldown_cutoff = (datetime.now(timezone.utc) - timedelta(hours=STALE_COOLDOWN_HOURS)).isoformat()

    deal_ids = [r[COL_DEAL_ID] for r in rows if r.get(COL_DEAL_ID)]
    current_data: dict[str, dict] = {}

    for i in range(0, len(deal_ids), 200):
        batch = deal_ids[i:i + 200]
        result = (
            supabase.table(DEALS_TABLE)
            .select(f"{COL_DEAL_ID}, {col_activity}, {COL_STALE_CHECKED}, {COL_STALE}")
            .in_(COL_DEAL_ID, batch)
            .execute()
        )
        for d in (result.data or []):
            current_data[d[COL_DEAL_ID]] = {
                "activity": d.get(col_activity) or "",
                "checked_at": d.get(COL_STALE_CHECKED) or "",
                "stale": d.get(COL_STALE),
            }

    skipped_cooldown = 0
    for row in rows:
        did = row.get(COL_DEAL_ID, "")
        existing = current_data.get(did, {})

        if existing.get("stale") is True:
            row[COL_STALE] = True
            continue

        new_activity = _normalize_ts(row.get(col_activity) or "")
        if not new_activity:
            continue

        checked_at = existing.get("checked_at", "")

        if checked_at and checked_at > cooldown_cutoff:
            skipped_cooldown += 1
            continue

        if not checked_at or new_activity > _normalize_ts(checked_at):
            row[COL_STALE] = True

    if skipped_cooldown:
        print(f"   {skipped_cooldown} deals skipped (cooldown {STALE_COOLDOWN_HOURS}h)")

    return rows


# ── Step 6: Upsert to Supabase ────────────────────────────────────────────

def _upsert_deals(rows: list[dict]) -> int:
    written = 0
    for i in range(0, len(rows), UPSERT_BATCH_SIZE):
        batch = rows[i:i + UPSERT_BATCH_SIZE]
        result = (
            supabase.table(DEALS_TABLE)
            .upsert(batch, on_conflict=DEALS_UPSERT_KEY)
            .execute()
        )
        written += len(result.data or [])
    return written


# ── Main entry point ─────────────────────────────────────────────────────

def run(full: bool = False) -> dict:
    print("=" * 60)
    print(f"SYNC DEALS v2 — {'FULL' if full else 'INCREMENTAL'}")
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
        return {"synced": 0, "stale": 0, "deal_ids": []}

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
    print("   Fetching partner associations ...")
    partner_map = _fetch_partner_associations(deal_id_list)
    print(f"   {len(partner_map)} partner links")

    # Step 4
    print("\n4. Resolving deals ...")
    rows = []
    skipped = 0
    for hd in hs_deals:
        row = _resolve_deal(hd, owners, company_map, partner_map)
        if row:
            rows.append(row)
        else:
            skipped += 1
    print(f"   {len(rows)} resolved, {skipped} excluded")

    # Step 5
    print("\n5. Detecting activity changes ...")
    rows = _detect_stale(rows)
    stale = sum(1 for r in rows if r.get(COL_STALE))
    print(f"   {stale} deals with new activity → context_stale=True")

    # Step 6
    print(f"\n6. Upserting {len(rows)} deals ...")
    written = _upsert_deals(rows)
    print(f"   {written} deals upserted")

    print(f"\n   HubSpot API requests: {hubspot.total_requests()}")
    print("=" * 60)

    synced_ids = [r[COL_DEAL_ID] for r in rows if r.get(COL_DEAL_ID)]
    return {"synced": written, "stale": stale, "deal_ids": synced_ids}
