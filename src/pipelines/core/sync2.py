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
MEETINGS_TABLE    = _tbl("meetings")
MEETINGS_UPSERT   = schema.upsert_key("meetings")

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

SEARCH_URL = "/crm/v3/objects/deals/search"
HUBSPOT_BASE = org.API_ENDPOINTS["hubspot"]


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
            "properties": [_F["hs_object_id"]["column"]],
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


_HS_IS_CLOSED = {"propertyName": "hs_is_closed", "operator": "NEQ", "value": "true"}


def _mod_filter(since_ms: int | None) -> dict | None:
    if since_ms is None:
        return None
    return {"propertyName": _TRIGGER["search_property"], "operator": "GTE", "value": str(since_ms)}


def _find_deal_ids(since_ms: int | None) -> set[str]:
    all_oids = list({oid for t in ACTIVE_TEAMS for oid in get_owner_ids_for_team(t)})
    if not all_oids:
        return set()
    mf = _mod_filter(since_ms)
    ids: set[str] = set()
    for i in range(0, len(all_oids), 5):
        batch = all_oids[i:i + 5]
        filter_groups = []
        for oid in batch:
            filters = [
                {"propertyName": "hubspot_owner_id", "operator": "EQ", "value": oid},
                _HS_IS_CLOSED,
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
    url = "/crm/v3/owners?limit=100"
    while url:
        data = hubspot.get(url)
        for o in data.get("results", []):
            first = o.get("firstName") or ""
            last = o.get("lastName") or ""
            name = f"{first} {last}".strip() or o.get("email", "")
            owners[o["id"]] = {"name": name, "email": o.get("email", "")}
        next_link = data.get("paging", {}).get("next", {}).get("link")
        url = next_link.replace(HUBSPOT_BASE, "") if next_link else ""
    return owners


def _batch_read_deals(deal_ids: list[str]) -> list[dict]:
    results = []
    for i in range(0, len(deal_ids), 100):
        batch = deal_ids[i:i + 100]
        data = hubspot.post(
            "/crm/v3/objects/deals/batch/read",
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
                "/crm/v4/associations/deals/companies/batch/read",
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
                f"/crm/v4/associations/deals/{org.CRM_PARTNER_OBJECT_TYPE_ID}/batch/read",
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


# ── Build a set of HS prop names whose type is date/datetime ─────────────
# FIX bug #1: use field type metadata instead of string matching on prop name.

_DATE_TYPE_COLUMNS = {
    v["column"]
    for v in _F.values()
    if v["column"] in {f["column"] for f in schema.FIELDS.values() if f["type"] in ("date", "datetime")}
}

_HS_DATE_PROPS = {
    hs_prop
    for hs_prop, info in _F.items()
    if info["column"] in _DATE_TYPE_COLUMNS
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

    # Pipeline filter — use org.CRM_EXCLUDE_PIPELINE_IDS
    pipeline_id = props.get("pipeline") or ""
    if pipeline_id in org.CRM_EXCLUDE_PIPELINE_IDS:
        return None
    pipeline_entry = _PIPELINE_MAP.get(pipeline_id)
    pipeline_name = pipeline_entry["name"] if pipeline_entry else pipeline_id

    # Stage: CRM ID → label → internal name
    stage_raw = props.get("dealstage") or ""
    stage_label = _STAGE_MAP.get(stage_raw, stage_raw)
    stage_internal = _STAGE_TO_INTERNAL.get(stage_label)

    # FIX bug #7: use schema.EXCLUDED set instead of lowercase string matching
    if not allow_closed and stage_internal and stage_internal in schema.EXCLUDED:
        return None
    if not allow_closed and stage_internal and stage_internal in schema.CLOSED:
        return None

    # Map HS properties → Supabase columns
    # FIX bug #1: use _HS_DATE_PROPS set (field type metadata) instead of string matching
    row = {}
    for hs_prop, info in _F.items():
        val = props.get(hs_prop)
        if val is not None and val != "":
            row[info["column"]] = _to_iso(val) if hs_prop in _HS_DATE_PROPS else val

    # Map stage date properties (all are dates)
    for hs_prop, info in _SD.items():
        val = props.get(hs_prop)
        if val is not None and val != "":
            row[info["column"]] = _to_iso(val)

    # Override stage with label (human-readable, not raw ID)
    row[COL_STAGE] = stage_label

    # Override pipeline_name
    row[COL_PIPELINE] = pipeline_name

    # Resolve PAE/PBD names
    owner_id = props.get("hubspot_owner_id") or ""
    creator_id = props.get("created_by") or ""
    owner_email = get_email_by_owner_id(str(owner_id))
    creator_email = get_email_by_owner_id(str(creator_id))

    row[COL_PAE] = get_display_name(owner_email) if owner_email else ""
    row[COL_PBD] = get_display_name(creator_email) if creator_email else ""

    if not row[COL_PAE] and owner_id in owners:
        row[COL_PAE] = owners[owner_id].get("name", "")
    if not row[COL_PBD] and creator_id in owners:
        row[COL_PBD] = owners[creator_id].get("name", "")

    # FIX bug #3: use schema column name instead of hardcoded "hs_all_owner_ids"
    if not row[COL_PBD]:
        all_ids_col = _col("all_owner_ids")
        all_ids = (props.get("hs_all_owner_ids") or "").split(";")
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

    # Resolve team + partner via partner association or owner email
    deal_id = row.get(COL_DEAL_ID, "")
    partner_id = partner_map.get(deal_id)
    row[COL_TEAM] = get_deal_team(partner_id, owner_email)

    # FIX bug #4: use COL_PARTNER (schema internal name) instead of hardcoded "partner"
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

    col_activity = _TRIGGER["supabase_column"]
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


# FIX bug #9: skip meetings for excluded-pipeline deals
def _sync_meetings(deal_ids: list[str], resolved_pipeline_ids: dict[str, str]) -> int:
    if not deal_ids:
        return 0

    # Only sync meetings for deals NOT in excluded pipelines
    active_deal_ids = [
        did for did in deal_ids
        if resolved_pipeline_ids.get(did) not in org.CRM_EXCLUDE_PIPELINE_IDS
    ]
    if not active_deal_ids:
        return 0

    meeting_rows = []
    for did in active_deal_ids:
        try:
            assoc = hubspot.get(f"/crm/v4/objects/deals/{did}/associations/meetings?limit=100")
            meeting_ids = [
                str(a.get("toObjectId", ""))
                for a in assoc.get("results", [])
                if a.get("toObjectId")
            ]
            if not meeting_ids:
                continue
            mdata = hubspot.post(
                "/crm/v3/objects/meetings/batch/read",
                {
                    "inputs": [{"id": mid} for mid in meeting_ids],
                    "properties": list(org.CRM_TO_SUPABASE_MEETINGS.keys()),
                },
            )
            for m in mdata.get("results", []):
                mp = m.get("properties", {})
                row = {
                    "hs_deal_id": did,
                    "hs_meeting_id": m["id"],
                }
                for hs_prop, col in org.CRM_TO_SUPABASE_MEETINGS.items():
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
        mid = r.get(MEETINGS_UPSERT)
        if mid and mid not in seen:
            seen.add(mid)
            unique.append(r)

    written = 0
    for i in range(0, len(unique), UPSERT_BATCH_SIZE):
        batch = unique[i:i + UPSERT_BATCH_SIZE]
        result = (
            supabase.table(MEETINGS_TABLE)
            .upsert(batch, on_conflict=MEETINGS_UPSERT)
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
    print("   Fetching partner associations ...")
    partner_map = _fetch_partner_associations(deal_id_list)
    print(f"   {len(partner_map)} partner links")

    # Step 4
    print("\n4. Resolving deals ...")
    rows = []
    skipped = 0
    pipeline_id_map: dict[str, str] = {}
    for hd in hs_deals:
        props = hd.get("properties", {})
        hs_deal_id = props.get("hs_object_id") or hd.get("id", "")
        pipeline_id_map[hs_deal_id] = props.get("pipeline") or ""

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
