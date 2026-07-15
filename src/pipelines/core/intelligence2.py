"""
Core Intelligence v2 — the brain of the CORE pipeline.

Entry point: run(deal_uuid)

Receives a deal marked context_stale=True by sync. Goes to HubSpot to fetch
all communications (emails, notes, meetings, calls), resolves Modjo transcripts,
detects what's new vs deal_context, calls Claude once with everything, and writes:
  - calls table (new calls with transcript)
  - pbd_audits / pae_audits (one per auditable call/meeting)
  - deals.deal_context (chronological timeline, appended)
  - front_deal_snapshots (cumulative deal state)
  - pbd_snapshots (BANT qualification, if PBD stage)
  - deal_product_signals (product intelligence)

Changes vs v1:
  - All CRM props via org.CRM_*_PROPERTIES / crm_prop() / reverse lookups
  - All Supabase cols via schema.col() / schema.tbl() / schema.upsert_key()
  - All thresholds via config2.*
  - BUG FIX: today computed at call time (not module-level)
  - BUG FIX: _write_snapshot uses upsert (not select+update/insert)
  - BUG FIX: stale_cooldown_hours enforced
  - BUG FIX: context entry skipped if audit write fails
  - BUG FIX: partner label via config2.get_partner_label() (not fragile string replace)
  - Dead code removed (_get_lang_from_team)
  - Day-of-week + DD/MM in Today's date prompt
"""

import json
import re
from datetime import date, datetime, timezone
from html import unescape

from src import org, schema
from src.config2 import (
    PROMPTS_DIR, PROMPTS, CHANNEL_PROMPT_MAP, ROLE_PROMPT_MAP,
    MODEL_DEFAULT, MAX_TOKENS,
    CONTEXT_CALL_PATTERN, CONTEXT_HS_PATTERN, MODJO_LINK_PATTERN,
    CONTEXT_RPC, CONTEXT_RPC_PARAMS,
    CONTEXT_RECENT_LINES, MAX_COMMS_PER_BATCH,
    TRANSCRIPT_PENDING_HOURS, MIN_TRANSCRIPT_FOR_AUDIT,
    STALE_COOLDOWN_HOURS, DEAL_NAME_EXCLUDE_PATTERNS,
    RED_FLAGS,
    get_role, get_subteam, get_partner_label, get_lang_prompt,
)
from src.db.client import supabase
from src.integrations import claude, hubspot, modjo


# ═══════════════════════════════════════════════════════════════════════════
# RESOLVED CONSTANTS — computed once at import from schema / org / config2
# ═══════════════════════════════════════════════════════════════════════════

# ── Tables ──
_TBL_DEALS = schema.tbl("deals")
_TBL_CALLS = schema.tbl("calls")
_TBL_ATLAS = schema.tbl("atlas")
_TBL_PBD_AUDITS = schema.tbl("pbd_audits")
_TBL_PAE_AUDITS = schema.tbl("pae_audits")
_TBL_SNAPSHOTS = schema.tbl("snapshots")
_TBL_PBD_SNAP = schema.tbl("pbd_snapshots")
_TBL_PRODUCT = schema.tbl("product_signals")
_TBL_PROD_STATS = schema.tbl("product_stats")

# ── Deal columns (from schema.FIELDS) ──
_D_UUID = schema.col("deal_uuid")
_D_ID = schema.col("deal_id")
_D_NAME = schema.col("deal_name")
_D_STAGE = schema.col("stage")
_D_MRR = schema.col("mrr")
_D_AGE = schema.col("deal_age")
_D_CLOSE = schema.col("close_date")
_D_FORECAST = schema.col("forecast_category")
_D_PBD = schema.col("pbd")
_D_PAE = schema.col("pae")
_D_TEAM = schema.col("team")
_D_CRM = schema.col("crm_id")
_D_CONTEXT = schema.col("deal_context")
_D_STALE = schema.col("context_stale")
_D_CHECKED = schema.col("stale_checked_at")

# ── Call columns (from schema.CALL_COLS) ──
_CC = schema.CALL_COLS

# ── Audit structures ──
_AUDIT_META = schema.AUDIT_METADATA_COLS
_AUDIT_COMMON = schema.AUDIT_COMMON_COLS
_AUDIT_BANT = schema.AUDIT_BANT_PILLARS
_AUDIT_MEDDIC = schema.AUDIT_MEDDIC_PILLARS
_AUDIT_SCRIPT = schema.AUDIT_SCRIPT_COLS

# ── Snapshot structures ──
_SNAP_META = schema.SNAPSHOT_METADATA
_SNAP_CLAUDE = schema.SNAPSHOT_CLAUDE_COLS
_PBD_SNAP_COLS = schema.PBD_SNAPSHOT_COLS

# ── Forecast fields (for prev snapshot display) ──
_FORECAST_DISPLAY = schema.FORECAST_CLAUDE_COLS + schema.FORECAST_COMPUTED_COLS

# ── Product signal columns ──
_PROD = schema.PRODUCT_SIGNAL_COLS

# ── Atlas columns ──
_ATLAS = schema.ATLAS_COLS

# ── Snapshot identity + product stats columns ──
_SNAP_ID = schema.SNAPSHOT_IDENTITY_COLS
_PSTATS = schema.PRODUCT_STATS_TABLE_COLS

# ── CRM engagement property reverse lookups ──
# column_name → CRM property name  (e.g. "direction" → "hs_email_direction")
_EP = {v["column"]: k for k, v in org.CRM_EMAIL_PROPERTIES.items()}
_NP = {v["column"]: k for k, v in org.CRM_NOTE_PROPERTIES.items()}
_CP = {v["column"]: k for k, v in org.CRM_CALL_PROPERTIES.items()}
_MP = {v["column"]: k for k, v in org.CRM_MEETING_CONTEXT_PROPERTIES.items()}

# ── CRM association object types ──
_ASSOC_FROM = org.CRM_ASSOCIATIONS["deal_to_emails"]["from"]  # "deals"
_ASSOC_EMAILS = org.CRM_ASSOCIATIONS["deal_to_emails"]["to"]
_ASSOC_NOTES = org.CRM_ASSOCIATIONS["deal_to_notes"]["to"]
_ASSOC_MEETINGS = org.CRM_ASSOCIATIONS["deal_to_meetings"]["to"]
_ASSOC_CALLS = org.CRM_ASSOCIATIONS["deal_to_calls"]["to"]

# ── CRM owner response fields ──
_OWN = org.CRM_OWNER_RESPONSE_FIELDS

# ── API endpoints ──
_URL_ASSOC = org.API_ENDPOINTS["association_read"]
_URL_BATCH = org.API_ENDPOINTS["batch_read"]
_URL_OWNERS = org.API_ENDPOINTS["owners"]
_URL_BASE = org.API_ENDPOINTS["hubspot"]

# ── Compiled patterns ──
_CALL_RE = re.compile(CONTEXT_CALL_PATTERN)
_HS_RE = re.compile(CONTEXT_HS_PATTERN)
_MODJO_RE = re.compile(MODJO_LINK_PATTERN)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_MULTI_NL_RE = re.compile(r"\n{3,}")
_CID_RE = re.compile(r"\[cid:[^\]]+\]")
_CHAIN_RE = re.compile(
    r"(^>+ .+$|^-{3,}.*original message.*$|^-{3,}.*forwarded message.*$"
    r"|^On .{5,100} wrote:$|^El .{5,100} escribió:$"
    r"|^De:.*Enviado:.*Para:.*Asunto:|^From:.*Sent:.*To:.*Subject:)",
    re.IGNORECASE | re.MULTILINE,
)
_SIG_RE = re.compile(
    r"(^--\s*$|^best regards[,.]?\s*$|^kind regards[,.]?\s*$|^saludos[,.]?\s*$"
    r"|^un saludo[,.]?\s*$|^atentamente[,.]?\s*$|^regards[,.]?\s*$"
    r"|^thanks[,.]?\s*$|^gracias[,.]?\s*$|^cheers[,.]?\s*$"
    r"|AVISO DE CONFIDENCIALIDAD|CONFIDENTIALITY NOTICE"
    r"|Create Your Own Free Signature"
    r"|Enviado desde Outlook|Sent from Outlook"
    r"|Enviado desde mi iPhone|Sent from my iPhone)",
    re.IGNORECASE | re.MULTILINE,
)

# ── Upsert keys ──
_UK_CALLS = schema.upsert_key("calls")
_UK_PBD_AUDITS = schema.upsert_key("pbd_audits")
_UK_PAE_AUDITS = schema.upsert_key("pae_audits")
_UK_SNAPSHOTS = schema.upsert_key("snapshots")
_UK_PBD_SNAP = schema.upsert_key("pbd_snapshots")
_UK_PRODUCT = schema.upsert_key("product_signals")


# ═══════════════════════════════════════════════════════════════════════════
# TEXT HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _hours_since(iso_date: str) -> float:
    try:
        dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).total_seconds() / 3600
    except Exception:
        return 999


def _format_date(raw: str | None) -> str:
    if not raw:
        return "?"
    return raw[:10] if len(raw) >= 10 else raw


def _strip_html(text: str) -> str:
    clean = _HTML_TAG_RE.sub("", text)
    clean = clean.replace("&nbsp;", " ").replace("&amp;", "&")
    clean = clean.replace("&lt;", "<").replace("&gt;", ">")
    clean = _CID_RE.sub("", clean)
    lines = [line.strip() for line in clean.splitlines()]
    return "\n".join(line for line in lines if line)


def _clean_email_body(raw: str | None) -> str:
    if not raw:
        return "(no body)"
    text = unescape(raw)
    text = _HTML_TAG_RE.sub(" ", text)
    text = _CID_RE.sub("", text)
    chain_match = _CHAIN_RE.search(text)
    sig_match = _SIG_RE.search(text)
    cutoffs = [m.start() for m in [chain_match, sig_match] if m]
    if cutoffs:
        text = text[:min(cutoffs)]
    text = _MULTI_NL_RE.sub("\n\n", text)
    text = text.strip()
    return text if text else "(no body)"


def _parse_iso(raw: str | None) -> str | None:
    if not raw:
        return None
    return raw.replace("Z", "+00:00") if "T" in raw else None


def _today() -> str:
    return date.today().isoformat()


def _today_prompt() -> str:
    return date.today().strftime("%A %d/%m/%Y")


# ═══════════════════════════════════════════════════════════════════════════
# HUBSPOT FETCHERS
# ═══════════════════════════════════════════════════════════════════════════

def _fetch_associations(hs_deal_id: str, object_type: str) -> list[str]:
    ids: list[str] = []
    after = None
    while True:
        params = {"limit": "500"}
        if after:
            params["after"] = after
        url = _URL_ASSOC.format(from_type=_ASSOC_FROM, object_id=hs_deal_id, to_type=object_type)
        data = hubspot.get(url, params)
        for item in data.get("results", []):
            oid = str(item.get("toObjectId", ""))
            if oid:
                ids.append(oid)
        after = data.get("paging", {}).get("next", {}).get("after")
        if not after:
            break
    return ids


def _batch_read_hs(object_type: str, ids: list[str], properties: list[str]) -> list[dict]:
    results = []
    for i in range(0, len(ids), 100):
        batch = ids[i:i + 100]
        url = _URL_BATCH.format(object_type=object_type)
        data = hubspot.post(
            url,
            {"inputs": [{"id": oid} for oid in batch], "properties": properties},
        )
        results.extend(data.get("results", []))
    return results


def _fetch_owners() -> dict[str, dict]:
    owners: dict[str, dict] = {}
    url = f"{_URL_OWNERS}?limit=100"
    while url:
        data = hubspot.get(url)
        for o in data.get("results", []):
            first = o.get(_OWN["first_name"]) or ""
            last = o.get(_OWN["last_name"]) or ""
            name = f"{first} {last}".strip() or o.get(_OWN["email"], "")
            owners[o[_OWN["id"]]] = {"name": name, "email": o.get(_OWN["email"], "")}
        next_link = data.get("paging", {}).get("next", {}).get("link")
        url = next_link.replace(_URL_BASE, "") if next_link else ""
    return owners


# ═══════════════════════════════════════════════════════════════════════════
# RESOLVE COMMUNICATIONS — fetch from HubSpot + Modjo, detect new
# ═══════════════════════════════════════════════════════════════════════════

def _resolve_communications(
    deal_uuid: str, hs_deal_id: str, crm_id: str, deal_context: str, deal_team: str = ""
) -> tuple[list[dict], bool]:
    """Fetch all communications from HubSpot + Modjo, detect what's new."""

    processed_call_ids = set(re.findall(_CALL_RE, deal_context or ""))
    processed_hs_ids = set(re.findall(_HS_RE, deal_context or ""))

    items: list[dict] = []
    has_pending = False
    modjo_ids_seen: set[str] = set()
    owners: dict[str, dict] | None = None

    def _get_owners() -> dict[str, dict]:
        nonlocal owners
        if owners is None:
            owners = _fetch_owners()
        return owners

    # ── Emails ──
    email_ids = _fetch_associations(hs_deal_id, _ASSOC_EMAILS)
    new_email_ids = [eid for eid in email_ids if eid not in processed_hs_ids]

    if new_email_ids:
        email_objects = _batch_read_hs(_ASSOC_EMAILS, new_email_ids, org.CRM_ALL_EMAIL_PROPS)
        for obj in email_objects:
            p = obj.get("properties", {})
            hs_id = str(obj.get("id", ""))
            date_val = p.get(_EP["activity_date"]) or p.get(_EP["created_at"]) or ""
            raw_dir = (p.get(_EP["direction"]) or "")
            direction = org.CRM_EMAIL_DIRECTIONS.get(raw_dir, raw_dir.lower())
            body_raw = p.get(_EP["body_text"]) or p.get(_EP["body_html"]) or ""
            items.append({
                "type": "email",
                "date": date_val,
                "data": {
                    "hs_engagement_id": hs_id,
                    "date": date_val,
                    "direction": direction,
                    "from_email": p.get(_EP["from_email"]) or "?",
                    "subject": p.get(_EP["subject"]) or "(no subject)",
                    "body_clean": _clean_email_body(body_raw),
                },
            })
        print(f"    {len(new_email_ids)} new emails")

    # ── Notes ──
    note_ids = _fetch_associations(hs_deal_id, _ASSOC_NOTES)
    new_note_ids = [nid for nid in note_ids if nid not in processed_hs_ids]

    if new_note_ids:
        note_objects = _batch_read_hs(_ASSOC_NOTES, new_note_ids, org.CRM_ALL_NOTE_PROPS)
        for obj in note_objects:
            p = obj.get("properties", {})
            hs_id = str(obj.get("id", ""))
            date_val = p.get(_NP["activity_date"]) or p.get(_NP["created_at"]) or ""
            owner_id = p.get(_NP["owner_id"]) or ""
            owner_info = _get_owners().get(owner_id, {})
            author = owner_info.get("name", "?") if isinstance(owner_info, dict) else "?"
            content = _strip_html(p.get(_NP["body"]) or "")
            items.append({
                "type": "note",
                "date": date_val,
                "data": {
                    "hs_engagement_id": hs_id,
                    "date": date_val,
                    "owner": author,
                    "content": content if content else "(sin contenido)",
                },
            })
        print(f"    {len(new_note_ids)} new notes")

    # ── Meetings ──
    meeting_ids = _fetch_associations(hs_deal_id, _ASSOC_MEETINGS)
    new_meeting_ids = [mid for mid in meeting_ids if mid not in processed_hs_ids]
    meetings_pending = 0

    if new_meeting_ids:
        meeting_objects = _batch_read_hs(_ASSOC_MEETINGS, new_meeting_ids, org.CRM_ALL_MEETING_PROPS)
        for obj in meeting_objects:
            p = obj.get("properties", {})
            hs_id = str(obj.get("id", ""))
            outcome = p.get(_MP["meeting_outcome"]) or ""
            if outcome not in org.CRM_MEETING_PROCESSABLE_OUTCOMES:
                continue
            date_val = p.get(_MP["activity_date"]) or p.get(_MP["meeting_start"]) or ""

            owner_id = p.get(_MP["owner_id"]) or ""
            owner_info = _get_owners().get(owner_id, {})
            owner_email = owner_info.get("email", "") if isinstance(owner_info, dict) else ""
            owner_name = owner_info.get("name", "") if isinstance(owner_info, dict) else ""
            title = p.get(_MP["meeting_title"]) or ""

            duration_str = ""
            start = p.get(_MP["meeting_start"]) or ""
            end = p.get(_MP["meeting_end"]) or ""
            if start and end:
                try:
                    s = datetime.fromisoformat(start.replace("Z", "+00:00"))
                    e = datetime.fromisoformat(end.replace("Z", "+00:00"))
                    mins = int((e - s).total_seconds() / 60)
                    if mins > 0:
                        duration_str = f"{mins}min"
                except (ValueError, TypeError):
                    pass

            meeting_meta = {
                "hs_id": hs_id,
                "title": title,
                "outcome": outcome,
                "duration": duration_str,
                "owner_name": owner_name,
            }

            notes_raw = p.get(_MP["meeting_notes"]) or ""
            modjo_match = _MODJO_RE.search(notes_raw) if outcome == "COMPLETED" else None

            if modjo_match:
                modjo_id = modjo_match.group(1)
                modjo_ids_seen.add(modjo_id)
                result = _resolve_modjo_call(
                    modjo_id, deal_uuid, hs_deal_id, crm_id,
                    owner_email, owner_name, title, date_val,
                    processed_call_ids, meeting_meta,
                )
                if result == "pending":
                    has_pending = True
                    meetings_pending += 1
                elif result:
                    items.append(result)
            else:
                if outcome == "NO_SHOW":
                    meeting_meta["notes"] = "Prospect did not attend"
                else:
                    internal_notes = _strip_html(notes_raw) if notes_raw else ""
                    if internal_notes:
                        meeting_meta["notes"] = internal_notes
                items.append({"type": "meeting", "date": date_val, "data": meeting_meta})

        auditable = sum(1 for it in items if it["type"] == "call" and it.get("_meeting_meta"))
        metadata = sum(1 for it in items if it["type"] == "meeting")
        print(f"    {len(new_meeting_ids)} new meetings: {auditable} auditable, {metadata} metadata, {meetings_pending} pending")

    # ── HubSpot Calls ──
    hs_call_ids = _fetch_associations(hs_deal_id, _ASSOC_CALLS)
    new_hs_call_ids = [cid for cid in hs_call_ids if cid not in processed_hs_ids and f"hs_{cid}" not in processed_call_ids]
    calls_auditable = 0

    if new_hs_call_ids:
        call_objects = _batch_read_hs(_ASSOC_CALLS, new_hs_call_ids, org.CRM_ALL_CALL_PROPS)
        for obj in call_objects:
            p = obj.get("properties", {})
            hs_id = str(obj.get("id", ""))
            body_raw = p.get(_CP["call_body"]) or ""
            body_clean = _strip_html(body_raw)

            modjo_match = _MODJO_RE.search(body_raw)
            owner_id = p.get(_CP["owner_id"]) or ""
            owner_info = _get_owners().get(owner_id, {})
            owner_email = owner_info.get("email", "")
            owner_name = owner_info.get("name", "")

            date_val = p.get(_CP["activity_date"]) or ""
            duration_ms = p.get(_CP["call_duration_ms"])
            duration_s = int(float(duration_ms) / 1000) if duration_ms else 0

            if modjo_match:
                modjo_id = modjo_match.group(1)
                if modjo_id in modjo_ids_seen:
                    continue
                modjo_ids_seen.add(modjo_id)
                result = _resolve_modjo_call(
                    modjo_id, deal_uuid, hs_deal_id, crm_id,
                    owner_email, owner_name,
                    p.get(_CP["call_title"]) or "", date_val,
                    processed_call_ids, None,
                )
                if result == "pending":
                    has_pending = True
                elif result:
                    items.append(result)
            elif len(body_clean) >= MIN_TRANSCRIPT_FOR_AUDIT:
                call_data = _build_call_row(
                    deal_team,
                    call_id=f"hs_{hs_id}", hs_call_id=hs_id,
                    deal_uuid=deal_uuid, hs_deal_id=hs_deal_id, crm_id=crm_id,
                    titulo=p.get(_CP["call_title"]) or "", fecha=_parse_iso(date_val),
                    owner_email=owner_email, owner_name=owner_name,
                    tags=[], duration_s=duration_s,
                    transcript=body_clean, source="hubspot",
                )
                _upsert_call(call_data)
                call_row = _fetch_call_by_id(f"hs_{hs_id}")
                if call_row:
                    call_data = call_row
                items.append({"type": "call", "date": date_val, "data": call_data})
                calls_auditable += 1
            else:
                items.append({
                    "type": "call_no_transcript",
                    "date": date_val,
                    "data": _build_call_row(
                        deal_team,
                        call_id=f"hs_{hs_id}", hs_call_id=hs_id,
                        deal_uuid=deal_uuid, hs_deal_id=hs_deal_id, crm_id=crm_id,
                        titulo=p.get(_CP["call_title"]) or "", fecha=_parse_iso(date_val),
                        owner_email=owner_email, owner_name=owner_name,
                        tags=[], duration_s=duration_s,
                        transcript="", source="hubspot",
                    ),
                })

        if new_hs_call_ids:
            print(f"    {len(new_hs_call_ids)} HS calls: {calls_auditable} auditable")

    # ── Modjo-only calls (in Supabase, no HS call object) ──
    modjo_only_resp = (
        supabase.table(_TBL_CALLS)
        .select("*")
        .eq(_CC["deal_id"], deal_uuid)
        .is_(_CC["hs_call_id"], "null")
        .execute()
    )
    for c in (modjo_only_resp.data or []):
        cid = c.get(_CC["call_id"]) or ""
        if cid in processed_call_ids or cid in modjo_ids_seen:
            continue
        transcript = (c.get(_CC["transcript"]) or "").strip()
        if transcript and len(transcript) >= MIN_TRANSCRIPT_FOR_AUDIT:
            items.append({"type": "call", "date": c.get(_CC["fecha"]) or "", "data": c})
        elif not transcript:
            hours = _hours_since(c.get(_CC["created_at"]) or c.get(_CC["fecha"]) or "")
            if hours < TRANSCRIPT_PENDING_HOURS:
                has_pending = True
            else:
                items.append({"type": "call_no_transcript", "date": c.get(_CC["fecha"]) or "", "data": c})

    items.sort(key=lambda x: x["date"] or "")
    return items, has_pending


def _resolve_modjo_call(
    modjo_id: str, deal_uuid: str, hs_deal_id: str, crm_id: str,
    owner_email: str, owner_name: str, title: str, date_val: str,
    processed_call_ids: set, meeting_meta: dict | None,
) -> dict | str | None:

    if modjo_id in processed_call_ids:
        return None

    existing = (
        supabase.table(_TBL_CALLS)
        .select("*")
        .eq(_CC["call_id"], modjo_id)
        .limit(1)
        .execute()
    )

    if existing.data:
        c = existing.data[0]
        transcript = (c.get(_CC["transcript"]) or "").strip()
        if transcript and len(transcript) >= MIN_TRANSCRIPT_FOR_AUDIT:
            item = {"type": "call", "date": c.get(_CC["fecha"]) or date_val, "data": c}
            if meeting_meta:
                item["_meeting_meta"] = meeting_meta
            return item
        hours = _hours_since(c.get(_CC["created_at"]) or c.get(_CC["fecha"]) or "")
        if hours < TRANSCRIPT_PENDING_HOURS:
            return "pending"
        item = {"type": "call_no_transcript", "date": c.get(_CC["fecha"]) or date_val, "data": c}
        if meeting_meta:
            item["_meeting_meta"] = meeting_meta
        return item

    raw_calls = modjo.fetch_call_details([int(modjo_id)])
    if not raw_calls:
        return _meeting_or_metadata(meeting_meta, date_val)

    normalized = modjo.normalize(raw_calls[0], fallback_email=owner_email, fallback_name=owner_name)

    if normalized and normalized.get("transcript") and len(normalized["transcript"]) >= MIN_TRANSCRIPT_FOR_AUDIT:
        normalized[_CC["deal_id"]] = deal_uuid
        normalized[_CC["hs_deal_id"]] = hs_deal_id
        normalized[_CC["crm_id"]] = crm_id
        if not normalized.get(_CC["titulo"]):
            normalized[_CC["titulo"]] = title
        _upsert_call(normalized)
        call_row = _fetch_call_by_id(modjo_id)
        if call_row:
            normalized = call_row
        item = {"type": "call", "date": date_val, "data": normalized}
        if meeting_meta:
            item["_meeting_meta"] = meeting_meta
        return item

    hours = _hours_since(date_val)
    if hours < TRANSCRIPT_PENDING_HOURS:
        return "pending"
    return _meeting_or_metadata(meeting_meta, date_val)


def _meeting_or_metadata(meeting_meta: dict | None, date_val: str) -> dict | None:
    if meeting_meta:
        return {"type": "meeting", "date": date_val, "data": meeting_meta}
    return None


def _build_call_row(deal_team: str = "", **kwargs) -> dict:
    role = get_role(kwargs.get("owner_email", ""), kwargs.get("tags", []))
    sub = get_subteam(kwargs.get("owner_email", "")) if kwargs.get("owner_email") else None
    return {
        _CC["call_id"]:      kwargs["call_id"],
        _CC["hs_call_id"]:   kwargs.get("hs_call_id"),
        _CC["deal_id"]:      kwargs["deal_uuid"],
        _CC["hs_deal_id"]:   kwargs["hs_deal_id"],
        _CC["crm_id"]:       kwargs["crm_id"],
        _CC["titulo"]:       kwargs.get("titulo", ""),
        _CC["fecha"]:        kwargs.get("fecha"),
        _CC["owner_email"]:  kwargs.get("owner_email"),
        _CC["owner_nombre"]: kwargs.get("owner_name", ""),
        _CC["rol"]:          "PAE" if role in ("AE", "PAE", None) else role,
        _CC["tags"]:         kwargs.get("tags", []),
        _CC["team"]:         deal_team,
        _CC["duracion"]:     kwargs.get("duration_s", 0),
        _CC["transcript"]:   kwargs.get("transcript", ""),
        _CC["subteam"]:      sub,
        _CC["source"]:       kwargs.get("source", "modjo"),
    }


def _upsert_call(call_data: dict):
    row = {k: v for k, v in call_data.items() if v is not None and not k.startswith("_")}
    supabase.table(_TBL_CALLS).upsert(row, on_conflict=_UK_CALLS).execute()


def _fetch_call_by_id(call_id: str) -> dict | None:
    resp = (
        supabase.table(_TBL_CALLS)
        .select("*")
        .eq(_CC["call_id"], call_id)
        .limit(1)
        .execute()
    )
    return resp.data[0] if resp.data else None


# ═══════════════════════════════════════════════════════════════════════════
# PROMPT ASSEMBLY
# ═══════════════════════════════════════════════════════════════════════════

def _read_prompt(relative_path: str) -> str:
    return (PROMPTS_DIR / relative_path).read_text(encoding="utf-8").strip()


def _channel_key(team: str) -> str | None:
    """Team name → channel prompt key (partners / direct_sales_es / xl_sales)."""
    if team in org.PARTNERS_ORGCHART:
        return "partners"
    if _find_ds_team(team):
        return "direct_sales_es"
    if team == "XL":
        return "xl_sales"
    return None


def _find_ds_team(team_name: str, teams: dict | None = None) -> dict | None:
    if teams is None:
        teams = org.DIRECT_SALES.get("teams", {})
    if team_name in teams:
        return teams[team_name]
    for t in teams.values():
        result = _find_ds_team(team_name, t.get("subteams", {}))
        if result:
            return result
    return None


def _stage_to_role_key(stage: str, channel: str | None) -> str | None:
    is_partner = (channel == "partners")
    if stage in schema.PBD_STAGES:
        return "PBD" if is_partner else "SDR"
    return "PAE" if is_partner else "AE"


def _fetch_product_benchmark(atlas: dict | None, deal: dict) -> str | None:
    sector = atlas.get(_ATLAS["industry"]) if atlas else None
    country = ((atlas or {}).get(_ATLAS["country"]) or "").upper()
    seats = int((atlas or {}).get(_ATLAS["company_size"]) or 0)

    if seats <= 20: size = "1-20"
    elif seats <= 50: size = "21-50"
    elif seats <= 100: size = "51-100"
    elif seats <= 250: size = "101-250"
    elif seats <= 500: size = "251-500"
    else: size = "500+"

    keys_to_try = []
    if sector and size:
        keys_to_try.append(f"{sector}|{size}")
    if sector and country:
        keys_to_try.append(f"{sector}|{country}")
    if sector:
        keys_to_try.append(sector)
    if country and size:
        keys_to_try.append(f"{country}|{size}")

    segment_data = None
    segment_key = None
    for key in keys_to_try:
        try:
            r = supabase.table(_TBL_PROD_STATS).select(_PSTATS["data"]).eq(_PSTATS["stat_type"], "segment").eq(_PSTATS["stat_key"], key).limit(1).execute()
            if r.data:
                segment_data = json.loads(r.data[0][_PSTATS["data"]]) if isinstance(r.data[0][_PSTATS["data"]], str) else r.data[0][_PSTATS["data"]]
                segment_key = key
                break
        except Exception:
            continue

    if not segment_data:
        return None

    lines = [f"Segment: {segment_key} ({segment_data['sample_size']} companies)"]
    lines.append(f"Avg: {segment_data['avg_products']} products, €{segment_data['avg_mrr']}/month, {segment_data['avg_seats']} employees")
    lines.append("Adoption rates:")
    for module, pct in sorted(segment_data.get("adoption", {}).items(), key=lambda x: -x[1]):
        if pct >= 5:
            lines.append(f"  - {module}: {pct}%")

    try:
        cross = supabase.table(_TBL_PROD_STATS).select(_PSTATS["data"]).eq(_PSTATS["stat_type"], "cross_sell").execute()
        if cross.data:
            lines.append("Cross-sell patterns:")
            for row in cross.data:
                d = json.loads(row[_PSTATS["data"]]) if isinstance(row[_PSTATS["data"]], str) else row[_PSTATS["data"]]
                module = d.get("module", "")
                top = sorted(d.get("cross_sell", {}).items(), key=lambda x: -x[1].get("probability", 0))[:2]
                if top:
                    pairs = ", ".join(f"{m} ({info['probability']}%)" for m, info in top)
                    lines.append(f"  - If {module} → also have: {pairs}")
    except Exception:
        pass

    try:
        ladder = supabase.table(_TBL_PROD_STATS).select(_PSTATS["data"]).eq(_PSTATS["stat_type"], "mrr_ladder").limit(1).execute()
        if ladder.data:
            d = json.loads(ladder.data[0][_PSTATS["data"]]) if isinstance(ladder.data[0][_PSTATS["data"]], str) else ladder.data[0][_PSTATS["data"]]
            lines.append("MRR by product count:")
            for n in sorted(d, key=int):
                if int(n) <= 6:
                    lines.append(f"  - {n} products: €{d[n]['avg_mrr']}/month")
    except Exception:
        pass

    return "\n".join(lines)


def _build_system_prompt(deal: dict) -> str:
    team = deal.get(_D_TEAM) or ""
    stage = deal.get(_D_STAGE) or ""

    parts = [_read_prompt(PROMPTS["base"])]

    channel = _channel_key(team)
    if channel and channel in CHANNEL_PROMPT_MAP:
        parts.append(_read_prompt(CHANNEL_PROMPT_MAP[channel]))

    role_key = _stage_to_role_key(stage, channel)
    if role_key and role_key in ROLE_PROMPT_MAP:
        parts.append(_read_prompt(ROLE_PROMPT_MAP[role_key]))

    parts.append(_read_prompt(PROMPTS["intelligence_system"]))
    parts.append(_read_prompt(PROMPTS["product_catalog"]))

    owner_email = deal.get(_D_PAE) or deal.get(_D_PBD)
    lang_text = get_lang_prompt(team, owner_email=owner_email)
    if lang_text:
        parts.append(lang_text)

    system_prompt = "\n\n".join(parts)

    partner_label = get_partner_label(owner_email) if owner_email else None
    if partner_label and partner_label != "Unknown Partner":
        system_prompt = system_prompt.replace("Banco Santander, Telefónica, and MEO", partner_label)
        system_prompt = system_prompt.replace("Santander, Telefónica, or MEO", partner_label)

    return system_prompt


def _build_user_prompt(
    deal, deal_context, atlas, prev_snapshot, prev_pbd,
    items, is_pbd_stage, today_str: str, full_context: bool = False,
):
    lines = []

    lines.append("## DEAL METADATA")
    lines.append(f"- Deal Name: {deal.get(_D_NAME) or '?'}")
    lines.append(f"- Deal ID: {deal.get(_D_ID) or '?'}")
    lines.append(f"- Stage: {deal.get(_D_STAGE) or '?'}")
    lines.append(f"- MRR: {deal.get(_D_MRR) or '?'}€")
    lines.append(f"- Deal Age: {deal.get(_D_AGE) or '?'} days")
    lines.append(f"- Close Date: {deal.get(_D_CLOSE) or '?'}")
    lines.append(f"- Forecast Category: {deal.get(_D_FORECAST) or '?'}")
    lines.append(f"- PBD: {deal.get(_D_PBD) or 'None'}")
    lines.append(f"- PAE: {deal.get(_D_PAE) or 'None'}")
    lines.append(f"- Team: {deal.get(_D_TEAM) or '?'}")
    lines.append(f"- is_pbd_stage: {str(is_pbd_stage).lower()}")
    lines.append("")

    lines.append("## ATLAS — COMPANY CONTEXT")
    if atlas:
        ctx = atlas.get(_ATLAS["company_context"]) or atlas.get(_ATLAS["company_card"])
        lines.append(str(ctx) if ctx else "(no atlas generated yet)")
    else:
        lines.append("(no company linked — no atlas available)")
    lines.append("")

    benchmark = _fetch_product_benchmark(atlas, deal)
    if benchmark:
        lines.append("## PRODUCT BENCHMARK — companies similar to this prospect")
        lines.append(benchmark)
        lines.append("")

    lines.append("## DEAL CONTEXT — ALREADY PROCESSED HISTORY")
    if deal_context and deal_context.strip():
        dc_lines = deal_context.strip().split("\n")
        if not full_context and prev_snapshot and len(dc_lines) > CONTEXT_RECENT_LINES:
            recent = dc_lines[-CONTEXT_RECENT_LINES:]
            lines.append(f"(showing last {len(recent)} of {len(dc_lines)} entries — full history summarized in PREVIOUS SNAPSHOT)")
            lines.append("\n".join(recent))
        else:
            lines.append(deal_context.strip())
    else:
        lines.append("No prior interactions. First analysis.")
    lines.append("")

    if prev_snapshot:
        snap_date = prev_snapshot.get(_SNAP_ID["snapshot_date"], "?")
        lines.append(f"## PREVIOUS SNAPSHOT ({snap_date})")
        for field in _SNAP_CLAUDE:
            val = prev_snapshot.get(field)
            if val is not None and val != "":
                lines.append(f"{field}: {val}")
        for field in _FORECAST_DISPLAY:
            val = prev_snapshot.get(field)
            if val is not None and val != "":
                lines.append(f"{field}: {val}")
        lines.append("")
    else:
        lines.append("## PREVIOUS SNAPSHOT: No previous snapshot. First analysis.")
        lines.append("")

    if is_pbd_stage:
        if prev_pbd:
            pbd_date = prev_pbd.get(_SNAP_ID["snapshot_date"], "?")
            lines.append(f"## PREVIOUS PBD SNAPSHOT ({pbd_date})")
            for col in _PBD_SNAP_COLS:
                val = prev_pbd.get(col)
                if val is not None:
                    lines.append(f"{col}: {val}")
        else:
            lines.append("## PREVIOUS PBD SNAPSHOT: No previous PBD snapshot.")
        lines.append("")

    if prev_snapshot:
        deal_uuid = deal.get(_D_UUID)
        if deal_uuid:
            try:
                pi = (
                    supabase.table(_TBL_PRODUCT)
                    .select(f"{_PROD['product_assessment']}, {_PROD['product_actions']}, {_PROD['expansion_summary']}")
                    .eq(_PROD["deal_id"], deal_uuid)
                    .order(_PROD["snapshot_date"], desc=True)
                    .limit(1)
                    .execute()
                )
                if pi.data:
                    p = pi.data[0]
                    if p.get(_PROD["product_assessment"]):
                        lines.append("## PREVIOUS PRODUCT INTEL")
                        lines.append(f"Assessment: {p[_PROD['product_assessment']]}")
                        if p.get(_PROD["expansion_summary"]):
                            lines.append(f"Expansion: {p[_PROD['expansion_summary']]}")
                        lines.append("")
            except Exception:
                pass

    call_ids_expected = []
    email_note_ids_expected = []
    n = len(items)
    lines.append(f"## NEW COMMUNICATIONS ({n} new since last update)")
    lines.append("")

    for i, item in enumerate(items, 1):
        t = item["type"]
        d = item["data"]

        if t == "call":
            tags = d.get(_CC["tags"]) or []
            tags_str = ", ".join(tags) if tags else "untagged"
            role = d.get(_CC["rol"]) or get_role(d.get(_CC["owner_email"], ""), tags) or "?"
            dur = round((d.get(_CC["duracion"]) or 0) / 60, 1)
            rep = d.get(_CC["owner_nombre"]) or d.get(_CC["owner_email"]) or "?"
            cid = d.get(_CC["call_id"]) or "?"
            meeting = item.get("_meeting_meta")
            if meeting:
                lines.append(f"### [{i}/{n}] MEETING + CALL — {_format_date(d.get(_CC['fecha']))} — {role} {rep} — {meeting.get('title', '')} [{tags_str}] ({dur}min)")
                lines.append(f"Meeting [hs:{meeting['hs_id']}] | Outcome: {meeting.get('outcome', '?')} | Duration: {meeting.get('duration', '?')}")
            else:
                lines.append(f"### [{i}/{n}] CALL — {_format_date(d.get(_CC['fecha']))} — {role} {rep} — Tags: [{tags_str}] ({dur}min)")
            lines.append(f"Call ID: {cid} | Role: {role}")
            lines.append(d.get(_CC["transcript"]) or "(sin transcripción)")
            call_ids_expected.append(cid)

        elif t == "call_no_transcript":
            tags = d.get(_CC["tags"]) or []
            tags_str = ", ".join(tags) if tags else "untagged"
            role = d.get(_CC["rol"]) or "?"
            dur = round((d.get(_CC["duracion"]) or 0) / 60, 1)
            rep = d.get(_CC["owner_nombre"]) or d.get(_CC["owner_email"]) or "?"
            cid = d.get(_CC["call_id"]) or "?"
            meeting = item.get("_meeting_meta")
            if meeting:
                lines.append(f"### [{i}/{n}] MEETING (no transcript) — {_format_date(item['date'])} — {rep} — {meeting.get('title', '')}")
                lines.append(f"Meeting [hs:{meeting['hs_id']}] | Outcome: {meeting.get('outcome', '?')}")
            else:
                lines.append(f"### [{i}/{n}] CALL (no transcript) — {_format_date(item['date'])} — {role} {rep} — Tags: [{tags_str}] ({dur}min)")
            lines.append(f"Call ID: {cid}")
            lines.append("(transcript not available — include in audits with win_rate_score: null)")
            call_ids_expected.append(cid)

        elif t == "email":
            lines.append(f"### [{i}/{n}] EMAIL {(d.get('direction') or '?').upper()} — {_format_date(d.get('date'))} — From: {d.get('from_email', '?')}")
            lines.append(f"Subject: {d.get('subject', '?')} | Engagement ID: hs_{d.get('hs_engagement_id', '?')}")
            lines.append(d.get("body_clean") or "(no body)")
            email_note_ids_expected.append(("email", d.get("hs_engagement_id", "?")))

        elif t == "note":
            lines.append(f"### [{i}/{n}] NOTE — {_format_date(d.get('date'))} — Author: {d.get('owner', '?')}")
            lines.append(f"Engagement ID: hs_{d.get('hs_engagement_id', '?')}")
            lines.append(d.get("content") or "(no content)")
            email_note_ids_expected.append(("note", d.get("hs_engagement_id", "?")))

        elif t == "meeting":
            lines.append(f"### [{i}/{n}] MEETING — {_format_date(item['date'])} — {d.get('owner_name', '?')} — {d.get('title', '')}")
            lines.append(f"Meeting [hs:{d.get('hs_id', '?')}] | Outcome: {d.get('outcome', '?')} | Duration: {d.get('duration', '?')}")
            if d.get("notes"):
                lines.append(f"Notes: {d['notes']}")
            email_note_ids_expected.append(("meeting", d.get("hs_id", "?")))

        lines.append("")

    lines.append("## EXPECTED OUTPUTS")
    if call_ids_expected:
        lines.append(f"AUDITS expected for call_ids: {json.dumps(call_ids_expected)}")
    else:
        lines.append("AUDITS: none expected (no calls in this batch)")
    if email_note_ids_expected:
        ids_list = [f"hs_{eid} ({etype})" for etype, eid in email_note_ids_expected]
        lines.append(f"NARRATIVES expected for: {', '.join(ids_list)}")
    else:
        lines.append("NARRATIVES: none expected")
    lines.append(f"SNAPSHOT: 1 (cumulative state after all {n} communications)")
    lines.append(f"PBD_SNAPSHOT: {'1 (deal is in PBD stage)' if is_pbd_stage else 'null (not PBD stage)'}")
    lines.append("")
    lines.append(f"Today's date: {today_str}")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# RESPONSE PARSING
# ═══════════════════════════════════════════════════════════════════════════

def _parse_response(text: str) -> dict:
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text).strip()
    if text and text[-1] != "}":
        raise ValueError(f"JSON truncated (last char: '{text[-1]}', len={len(text)})")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start:end + 1])
        raise


def _extract_red_flags(flags) -> list[str]:
    if not flags or not isinstance(flags, list):
        return []
    return [f for f in flags if isinstance(f, str) and f in RED_FLAGS]


def _extract_audit_fields(raw_audit: dict, role: str) -> dict:
    fields = {}
    for col in _AUDIT_COMMON:
        val = raw_audit.get(col)
        if col == "improvement_items_json" and isinstance(val, list):
            val = json.dumps(val, ensure_ascii=False)
        fields[col] = val
    fields["red_flags_fired"] = _extract_red_flags(raw_audit.get("red_flags_fired"))

    if role in ("PBD", "SDR"):
        bant = raw_audit.get("bant") or {}
        for pillar in _AUDIT_BANT:
            p = bant.get(pillar) or {}
            fields[f"bant_{pillar}_status"] = p.get("status")
            fields[f"bant_{pillar}_confidence"] = p.get("confidence")
            fields[f"bant_{pillar}_evidence"] = p.get("evidence")
        script = raw_audit.get("script_compliance") or {}
        fields["script_opener"] = script.get("opener")
        fields["script_industry_pivot"] = script.get("industry_pivot")
        fields["script_close"] = script.get("close")
        fields["two_slot_close"] = script.get("two_slot_close", False)
    elif role in ("PAE", "AE"):
        meddic = raw_audit.get("meddic") or {}
        for pillar in _AUDIT_MEDDIC:
            p = meddic.get(pillar) or {}
            fields[f"meddic_{pillar}_status"] = p.get("status")
            fields[f"meddic_{pillar}_confidence"] = p.get("confidence")
            fields[f"meddic_{pillar}_evidence"] = p.get("evidence")
    return fields


# ═══════════════════════════════════════════════════════════════════════════
# CONTEXT ENTRY BUILDERS
# ═══════════════════════════════════════════════════════════════════════════

def _build_context_entry_call(call: dict, audit_fields: dict, meeting_meta: dict | None = None) -> str:
    fecha = _format_date(call.get(_CC["fecha"]))
    rol = call.get(_CC["rol"]) or "?"
    tags = call.get(_CC["tags"]) or []
    tags_str = ", ".join(tags) if tags else "untagged"
    dur = round((call.get(_CC["duracion"]) or 0) / 60)
    rep = call.get(_CC["owner_nombre"]) or call.get(_CC["owner_email"]) or "?"
    call_id = call.get(_CC["call_id"]) or "?"

    if meeting_meta:
        hs_id = meeting_meta.get("hs_id", "?")
        title = meeting_meta.get("title", "")
        outcome = meeting_meta.get("outcome", "?")
        duration = meeting_meta.get("duration", "?")
        parts = [f"[{fecha}] MEETING AUDITED — {rol} {rep} — {title} [hs:{hs_id}] [call:{call_id}]"]
        parts.append(f"  Outcome: {outcome} | Duration: {duration}")
    else:
        parts = [f"[{fecha}] CALL AUDITED — {rol} {rep} — Tags: [{tags_str}] ({dur}min) [call:{call_id}]"]

    wrs = audit_fields.get("win_rate_score")
    ff = audit_fields.get("forecast_flag") or "—"
    pl = audit_fields.get("partner_leverage_score") or "—"
    lt = audit_fields.get("lead_temperature") or "—"
    parts.append(f"  Win rate: {wrs} | Forecast: {ff} | Partner leverage: {pl} | Temperature: {lt}")

    dc = audit_fields.get("deal_context")
    if dc:
        parts.append(f"  Narrative: {dc[:500]}")
    gap = audit_fields.get("biggest_gap")
    if gap:
        parts.append(f"  Biggest gap: {gap}")
    nco = audit_fields.get("next_call_objective")
    if nco:
        parts.append(f"  Next objective: {nco}")
    obj = audit_fields.get("objections")
    if obj:
        parts.append(f"  Objections: {obj[:300]}")
    sig = audit_fields.get("buying_signals")
    if sig:
        parts.append(f"  Buying signals: {sig[:300]}")
    blk = audit_fields.get("blockers")
    if blk:
        parts.append(f"  Blockers: {blk[:300]}")

    for prefix, pillars in [("bant", _AUDIT_BANT), ("meddic", _AUDIT_MEDDIC)]:
        pillar_lines = []
        for p in pillars:
            status = audit_fields.get(f"{prefix}_{p}_status")
            if status and status != "Missing":
                evidence = audit_fields.get(f"{prefix}_{p}_evidence") or ""
                line = f"    {p.replace('_', ' ').title()}: {status}"
                if evidence:
                    line += f' — "{evidence[:150]}"'
                pillar_lines.append(line)
        if pillar_lines:
            parts.append(f"  {prefix.upper()}:")
            parts.extend(pillar_lines)

    return "\n".join(parts)


def _build_context_entry_call_metadata(call: dict, meeting_meta: dict | None = None) -> str:
    fecha = _format_date(call.get(_CC["fecha"]))
    rol = call.get(_CC["rol"]) or "?"
    tags = call.get(_CC["tags"]) or []
    tags_str = ", ".join(tags) if tags else "untagged"
    dur = round((call.get(_CC["duracion"]) or 0) / 60)
    rep = call.get(_CC["owner_nombre"]) or call.get(_CC["owner_email"]) or "?"
    call_id = call.get(_CC["call_id"]) or "?"

    if meeting_meta:
        hs_id = meeting_meta.get("hs_id", "?")
        title = meeting_meta.get("title", "")
        outcome = meeting_meta.get("outcome", "?")
        return (
            f"[{fecha}] MEETING [hs:{hs_id}] [call:{call_id}] — {rep} — {title}\n"
            f"  Outcome: {outcome}\n"
            f"  (transcript not available — metadata only)"
        )
    titulo = call.get(_CC["titulo"]) or ""
    return (
        f"[{fecha}] CALL [call:{call_id}] — {rol} {rep} — Tags: [{tags_str}] ({dur}min)\n"
        f"  {titulo}\n"
        f"  (transcript not available — metadata only)"
    )


def _build_context_entry_email(email: dict, narrative: str) -> str:
    fecha = _format_date(email.get("date"))
    direction = (email.get("direction") or "?").upper()
    eid = email.get("hs_engagement_id") or "?"
    subject = email.get("subject") or "(no subject)"
    return f"[{fecha}] EMAIL {direction} [hs:{eid}] — {subject}\n  {narrative}"


def _build_context_entry_note(note: dict) -> str:
    fecha = _format_date(note.get("date"))
    nid = note.get("hs_engagement_id") or "?"
    author = note.get("owner") or "?"
    content = (note.get("content") or "").strip()
    return f"[{fecha}] NOTE [hs:{nid}] — {author}\n  {content}"


def _build_context_entry_meeting(meeting: dict, narrative: str, date_val: str) -> str:
    fecha = _format_date(date_val)
    hs_id = meeting.get("hs_id") or "?"
    owner = meeting.get("owner_name") or "?"
    title = meeting.get("title") or ""
    outcome = meeting.get("outcome") or "?"
    duration = meeting.get("duration") or "?"
    return (
        f"[{fecha}] MEETING [hs:{hs_id}] — {owner} — {title}\n"
        f"  Outcome: {outcome} | Duration: {duration}\n"
        f"  {narrative}"
    )


# ═══════════════════════════════════════════════════════════════════════════
# SUPABASE WRITERS
# ═══════════════════════════════════════════════════════════════════════════

def _write_audit(call: dict, audit_fields: dict, role: str) -> bool:
    try:
        table = _TBL_PBD_AUDITS if role in ("PBD", "SDR") else _TBL_PAE_AUDITS
        upsert_key = _UK_PBD_AUDITS if role in ("PBD", "SDR") else _UK_PAE_AUDITS
        row = {}
        for audit_col, call_col in _AUDIT_META.items():
            row[audit_col] = call.get(call_col)
        row.update(audit_fields)
        row = {k: v for k, v in row.items() if v is not None}
        supabase.table(table).upsert(row, on_conflict=upsert_key).execute()
        return True
    except Exception as e:
        print(f"    ✗ Audit write failed: {e}")
        return False


def _write_snapshot(deal: dict, snapshot_fields: dict, today_iso: str) -> bool:
    if not snapshot_fields.get("deal_summary"):
        print(f"    ✗ Snapshot rejected — deal_summary empty")
        return False
    try:
        row = {
            _SNAP_ID["deal_id"]: deal.get(_D_UUID),
            _SNAP_ID["hs_deal_id"]: deal.get(_D_ID),
            _SNAP_ID["snapshot_date"]: today_iso,
        }
        for snap_col, deal_col in _SNAP_META.items():
            val = deal.get(deal_col)
            if val is not None:
                row[snap_col] = val
        for col in _SNAP_CLAUDE:
            val = snapshot_fields.get(col)
            if val is not None:
                row[col] = json.dumps(val, ensure_ascii=False) if isinstance(val, (list, dict)) else val
        row = {k: v for k, v in row.items() if v is not None and v != ""}
        supabase.table(_TBL_SNAPSHOTS).upsert(row, on_conflict=_UK_SNAPSHOTS).execute()
        return True
    except Exception as e:
        print(f"    ✗ Snapshot write failed: {e}")
        return False


def _write_pbd_snapshot(deal: dict, pbd_data: dict, today_iso: str) -> bool:
    if not pbd_data:
        return True
    try:
        row = {
            _SNAP_ID["deal_id"]: deal.get(_D_UUID),
            _SNAP_ID["hs_deal_id"]: deal.get(_D_ID),
            _SNAP_ID["snapshot_date"]: today_iso,
            _SNAP_META["pbd"]: deal.get(_D_PBD),
        }
        for col in _PBD_SNAP_COLS:
            val = pbd_data.get(col)
            if val is not None:
                row[col] = val
        row = {k: v for k, v in row.items() if v is not None}
        supabase.table(_TBL_PBD_SNAP).upsert(row, on_conflict=_UK_PBD_SNAP).execute()
        return True
    except Exception as e:
        print(f"    ✗ PBD snapshot write failed: {e}")
        return False


def _write_product_intel(deal: dict, product_intel: dict, today_iso: str) -> bool:
    if not product_intel:
        return True
    assessment = product_intel.get(_PROD["product_assessment"])
    actions = product_intel.get(_PROD["product_actions"])
    expansion = product_intel.get(_PROD["expansion_summary"])
    if not assessment and not actions:
        return True
    try:
        row = {
            _PROD["deal_id"]: deal.get(_D_UUID),
            _PROD["snapshot_date"]: today_iso,
        }
        if assessment:
            row[_PROD["product_assessment"]] = assessment
        if actions:
            row[_PROD["product_actions"]] = json.dumps(actions, ensure_ascii=False)
        if expansion:
            row[_PROD["expansion_summary"]] = expansion
        row = {k: v for k, v in row.items() if v is not None}
        supabase.table(_TBL_PRODUCT).upsert(row, on_conflict=_UK_PRODUCT).execute()
        return True
    except Exception as e:
        print(f"    ✗ Product intel failed (non-critical): {e}")
        return True


def _append_context(deal_uuid: str, entry: str) -> bool:
    try:
        params = CONTEXT_RPC_PARAMS
        supabase.rpc(CONTEXT_RPC, {params["deal_id"]: deal_uuid, params["text"]: entry}).execute()
        return True
    except Exception as e:
        print(f"    ✗ Context append failed: {e}")
        return False


def _fetch_deal(deal_uuid: str) -> dict | None:
    resp = supabase.table(_TBL_DEALS).select("*").eq(_D_UUID, deal_uuid).limit(1).execute()
    return resp.data[0] if resp.data else None


def _fetch_atlas(crm_id: str) -> dict | None:
    if not crm_id:
        return None
    resp = (
        supabase.table(_TBL_ATLAS)
        .select(f"{_ATLAS['company_context']}, {_ATLAS['company_card']}, {_ATLAS['industry']}, {_ATLAS['country']}, {_ATLAS['company_size']}")
        .eq(_D_CRM, crm_id)
        .maybe_single()
        .execute()
    )
    return resp.data if resp.data else None


def _fetch_previous_snapshot(hs_deal_id: str) -> dict | None:
    resp = supabase.table(_TBL_SNAPSHOTS).select("*").eq(_SNAP_ID["hs_deal_id"], hs_deal_id).order(_SNAP_ID["snapshot_date"], desc=True).limit(1).execute()
    return resp.data[0] if resp.data else None


def _fetch_previous_pbd_snapshot(hs_deal_id: str) -> dict | None:
    resp = supabase.table(_TBL_PBD_SNAP).select("*").eq(_SNAP_ID["hs_deal_id"], hs_deal_id).order(_SNAP_ID["snapshot_date"], desc=True).limit(1).execute()
    return resp.data[0] if resp.data else None


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def run(
    deal_uuid: str,
    max_comms: int | None = MAX_COMMS_PER_BATCH,
    max_tokens: int | None = None,
    full_context: bool = False,
) -> dict | None:
    """Process a deal: fetch comms from HubSpot+Modjo, analyze with Claude, write everything."""

    today_iso = _today()
    today_str = _today_prompt()

    print(f"\n  INTELLIGENCE: {deal_uuid}")

    deal = _fetch_deal(deal_uuid)
    if not deal:
        print(f"    Deal not found")
        return None

    deal_name = deal.get(_D_NAME) or "?"

    # Exclude patterns before cooldown — excluded deals get marked done immediately
    if any(pat in deal_name.lower() for pat in DEAL_NAME_EXCLUDE_PATTERNS):
        _mark_done(deal_uuid)
        return None

    # BUG FIX: enforce stale cooldown
    checked_at = deal.get(_D_CHECKED)
    if checked_at and STALE_COOLDOWN_HOURS > 0:
        hours = _hours_since(checked_at)
        if hours < STALE_COOLDOWN_HOURS:
            print(f"    Cooldown: checked {hours:.1f}h ago (min {STALE_COOLDOWN_HOURS}h)")
            return None

    hs_deal_id = deal.get(_D_ID) or ""
    crm_id = deal.get(_D_CRM) or ""
    stage = deal.get(_D_STAGE) or ""
    is_pbd_stage = stage in schema.PBD_STAGES

    print(f"    {deal_name} | stage={stage} | pbd={is_pbd_stage}")

    deal_context = deal.get(_D_CONTEXT) or ""

    team = deal.get(_D_TEAM) or ""
    items, has_pending = _resolve_communications(deal_uuid, hs_deal_id, crm_id, deal_context, team)

    if not items:
        if has_pending:
            print(f"    Waiting for transcripts — staying stale")
        else:
            print(f"    Nothing new — done")
            _mark_done(deal_uuid)
        return None

    overflow = False
    if max_comms and len(items) > max_comms:
        print(f"    {len(items)} comms — capping to {max_comms}")
        items = items[:max_comms]
        overflow = True

    calls = sum(1 for it in items if it["type"] in ("call", "call_no_transcript"))
    emails = sum(1 for it in items if it["type"] == "email")
    notes = sum(1 for it in items if it["type"] == "note")
    meetings = sum(1 for it in items if it["type"] == "meeting")
    print(f"    {len(items)} to process: {calls}c {emails}e {notes}n {meetings}m")

    atlas = _fetch_atlas(crm_id)
    prev_snapshot = _fetch_previous_snapshot(hs_deal_id) if hs_deal_id else None
    prev_pbd = _fetch_previous_pbd_snapshot(hs_deal_id) if is_pbd_stage and hs_deal_id else None

    system_prompt = _build_system_prompt(deal)
    user_prompt = _build_user_prompt(
        deal, deal_context, atlas, prev_snapshot, prev_pbd,
        items, is_pbd_stage, today_str, full_context=full_context,
    )

    print(f"    Claude ({len(user_prompt)} user, {len(system_prompt)} system)...")
    try:
        response_text = claude.analyze(
            system_prompt, user_prompt,
            model=MODEL_DEFAULT,
            max_tokens=max_tokens or MAX_TOKENS["audit"],
        )
    except Exception as e:
        print(f"    ✗ Claude failed: {e}")
        return None

    print(f"    Parsing ({len(response_text)} chars)...")
    try:
        parsed = _parse_response(response_text)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"    ✗ Parse failed: {e}")
        return None

    raw_audits = parsed.get("audits") or []
    raw_narratives = parsed.get("communication_narratives") or []
    raw_snapshot = parsed.get("snapshot") or {}
    raw_pbd = parsed.get("pbd_snapshot")
    raw_product = parsed.get("product_intel") or {}

    narrative_by_id = {(n.get("id") or "").replace("hs_", ""): n.get("narrative", "") for n in raw_narratives}
    audit_by_call_id = {a.get("call_id", ""): a for a in raw_audits}

    context_entries: list[str] = []
    all_ok = True

    for item in items:
        t = item["type"]
        d = item["data"]
        meeting_meta = item.get("_meeting_meta")

        if t == "call":
            call_id = d.get(_CC["call_id"]) or ""
            role = d.get(_CC["rol"]) or get_role(d.get(_CC["owner_email"], ""), d.get(_CC["tags"])) or "PAE"
            raw_audit = audit_by_call_id.get(call_id)
            if raw_audit:
                audit_fields = _extract_audit_fields(raw_audit, role)
                audit_ok = _write_audit(d, audit_fields, role)
                if not audit_ok:
                    all_ok = False
                # BUG FIX: only append context entry if audit write succeeded
                if audit_ok:
                    entry = _build_context_entry_call(d, audit_fields, meeting_meta)
                    context_entries.append(entry)
            else:
                print(f"    ⚠ Audit omitted for {call_id} — retry next run")
                all_ok = False

        elif t == "call_no_transcript":
            entry = _build_context_entry_call_metadata(d, meeting_meta)
            context_entries.append(entry)

        elif t == "email":
            eid = d.get("hs_engagement_id") or ""
            narrative = narrative_by_id.get(eid, "")
            if not narrative:
                narrative = f"(narrative not produced — {d.get('subject', 'email')})"
                print(f"    ⚠ Narrative omitted for email hs_{eid}")
            entry = _build_context_entry_email(d, narrative)
            context_entries.append(entry)

        elif t == "note":
            entry = _build_context_entry_note(d)
            context_entries.append(entry)

        elif t == "meeting":
            hs_id = d.get("hs_id") or ""
            narrative = narrative_by_id.get(hs_id, "")
            if not narrative:
                notes = d.get("notes") or ""
                narrative = notes if notes else f"Meeting {d.get('outcome', '?')}"
            entry = _build_context_entry_meeting(d, narrative, item["date"])
            context_entries.append(entry)

    if context_entries:
        full_entry = "\n\n".join(context_entries)
        if not _append_context(deal_uuid, full_entry):
            all_ok = False
        else:
            print(f"    {len(context_entries)} context entries appended")

    snapshot_ok = _write_snapshot(deal, raw_snapshot, today_iso)
    if not snapshot_ok:
        all_ok = False

    if is_pbd_stage and raw_pbd:
        if not _write_pbd_snapshot(deal, raw_pbd, today_iso):
            all_ok = False

    _write_product_intel(deal, raw_product, today_iso)

    can_mark_done = all_ok and not has_pending and not overflow
    if can_mark_done:
        _mark_done(deal_uuid)
        print(f"    ✓ Done: {deal_name}")
    else:
        reasons = []
        if not all_ok:
            reasons.append("errors")
        if has_pending:
            reasons.append("pending transcripts")
        if overflow:
            reasons.append("more comms")
        print(f"    ⏳ Partial: {deal_name} ({', '.join(reasons)})")

    return {
        "audits": len(audit_by_call_id),
        "narratives": len(narrative_by_id),
        "entries": len(context_entries),
        "snapshot": snapshot_ok,
        "pbd_snapshot": is_pbd_stage and raw_pbd is not None,
        "done": can_mark_done,
        "has_pending": has_pending or overflow,
    }


def _mark_done(deal_uuid: str):
    supabase.table(_TBL_DEALS).update({
        _D_STALE: False,
        _D_CHECKED: datetime.now(timezone.utc).isoformat(),
    }).eq(_D_UUID, deal_uuid).execute()
