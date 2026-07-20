"""
Core Atlas v2 — Phase 2 of the CORE pipeline.

Generates company intelligence for a deal's company.
Full internal names. Zero hardcoded CRM properties or Supabase columns.

Changes vs v1:
  - All CRM props via org.CRM_COMPANY_PROPERTIES / CRM_CONTACT_PROPERTIES / crm_prop()
  - All Supabase cols via schema.ATLAS_COLS / schema.tbl()
  - Formatting labels in team's language (config2.ATLAS_LABELS)
  - atlas_id validation (empty string → early return)
  - json.loads with fallback (no crash on bad Claude output)
  - Sibling search uses "domain" property directly
"""

import json
import re
from datetime import date, datetime, timezone

from src import org, schema
from src.config2 import (
    PROMPTS_DIR, PROMPTS, MODEL_DEFAULT, MAX_TOKENS,
    IGNORE_DOMAINS_ATLAS, ATLAS_LABELS,
    get_lang_prompt, get_lang_code,
)
from src.db.client import supabase
from src.integrations import claude, hubspot


# ── CRM property lists (resolved once at import) ──────────────────────────────

_COMPANY_PROPS = list(org.CRM_COMPANY_PROPERTIES.keys())
_CONTACT_PROPS = list(org.CRM_CONTACT_PROPERTIES.keys())

_DEAL_PROPS = [
    org.crm_prop("deal_name"), org.crm_prop("stage"),
    org.crm_prop("mrr"), org.crm_prop("close_date"),
    org.crm_prop("create_date"), org.crm_prop("forecast_category"),
    org.crm_prop("owner_id"), org.crm_prop("is_closed_won"),
    org.crm_prop("is_closed"), org.crm_prop("closed_lost_reason"),
]

# internal shorthand → CRM property name (for deal formatting)
_D = {
    "name":          org.crm_prop("deal_name"),
    "stage":         org.crm_prop("stage"),
    "amount":        org.crm_prop("mrr"),
    "close_date":    org.crm_prop("close_date"),
    "create_date":   org.crm_prop("create_date"),
    "forecast":      org.crm_prop("forecast_category"),
    "owner_id":      org.crm_prop("owner_id"),
    "is_closed_won": org.crm_prop("is_closed_won"),
    "is_closed":     org.crm_prop("is_closed"),
    "lost_reason":   org.crm_prop("closed_lost_reason"),
}

# CRM property for sibling company search
_DOMAIN_PROP = next(
    k for k, v in org.CRM_COMPANY_PROPERTIES.items() if v["internal"] == "domain"
)

# CRM property → atlas column (only internals that exist in ATLAS_COLS)
_HS_TO_ATLAS = {
    hs_prop: schema.ATLAS_COLS[info["internal"]]
    for hs_prop, info in org.CRM_COMPANY_PROPERTIES.items()
    if info["internal"] in schema.ATLAS_COLS
}

# Claude output keys that map to atlas columns
_CLAUDE_KEYS = ("deal_history", "contacts_map", "company_context", "company_card", "deal_insights")

# Association object types
_ASSOC_DEALS = org.CRM_ASSOCIATIONS["company_to_deals"]["to"]
_ASSOC_CONTACTS = org.CRM_ASSOCIATIONS["company_to_contacts"]["to"]
_ASSOC_DEAL_CONTACTS = org.CRM_ASSOCIATIONS["deal_to_contacts"]["to"]

_TABLE = schema.tbl("atlas")
_SYS = schema.SYSTEM_COLS


# ── HubSpot fetchers ──────────────────────────────────────────────────────────

_URL_COMPANY_READ = org.API_ENDPOINTS["company_read"]
_URL_COMPANY_SEARCH = org.API_ENDPOINTS["company_search"]
_URL_ASSOC_READ = org.API_ENDPOINTS["association_read"]
_URL_BATCH_READ = org.API_ENDPOINTS["batch_read"]


def _fetch_company(crm_id: str) -> dict:
    props = ",".join(_COMPANY_PROPS)
    url = _URL_COMPANY_READ.format(company_id=crm_id)
    data = hubspot.get(url, {"properties": props})
    return data.get("properties", {})


def _fetch_association_ids(
    crm_id: str, object_type: str, from_type: str = "companies",
) -> list[str]:
    ids: list[str] = []
    after = None
    while True:
        params = {"limit": "500"}
        if after:
            params["after"] = after
        url = _URL_ASSOC_READ.format(from_type=from_type, object_id=crm_id, to_type=object_type)
        data = hubspot.get(url, params)
        for item in data.get("results", []):
            oid = str(item.get("toObjectId", ""))
            if oid:
                ids.append(oid)
        after = data.get("paging", {}).get("next", {}).get("after")
        if not after:
            break
    return ids


def _batch_read(object_type: str, ids: list[str], properties: list[str]) -> list[dict]:
    results = []
    for i in range(0, len(ids), 100):
        batch = ids[i:i + 100]
        url = _URL_BATCH_READ.format(object_type=object_type)
        data = hubspot.post(
            url,
            {"inputs": [{"id": oid} for oid in batch], "properties": properties},
        )
        results.extend(data.get("results", []))
    return results


def _normalize_domain(raw: str) -> str:
    d = raw.strip().lower().rstrip("/")
    d = d.replace("https://", "").replace("http://", "").replace("www.", "")
    return d.split("/")[0]


def _fetch_sibling_ids(domain: str, exclude_crm_id: str) -> list[str]:
    normalized = _normalize_domain(domain)
    if not normalized or normalized in IGNORE_DOMAINS_ATLAS:
        return []
    data = hubspot.post(
        _URL_COMPANY_SEARCH,
        {
            "filterGroups": [{"filters": [
                {"propertyName": _DOMAIN_PROP, "operator": "EQ", "value": normalized},
            ]}],
            "properties": [_COMPANY_PROPS[0]],
            "limit": 50,
        },
    )
    return [r["id"] for r in data.get("results", []) if str(r["id"]) != str(exclude_crm_id)]


# ── Prompt formatters (multilingual) ──────────────────────────────────────────

def _format_company(company: dict, labels: dict) -> str:
    cl = labels["company"]
    lines = []
    for hs_prop, info in org.CRM_COMPANY_PROPERTIES.items():
        internal = info["internal"]
        if internal in cl:
            val = company.get(hs_prop)
            if val:
                lines.append(f"{cl[internal]}: {val}")
    return "\n".join(lines) if lines else labels["empty"]["company"]


def _format_deals(deals: list[dict], owners: dict, labels: dict) -> str:
    if not deals:
        return labels["empty"]["deals"]
    dl = labels["deal_fields"]
    ds = labels["deal_status"]
    lines = []
    for obj in deals:
        p = obj.get("properties", {})
        is_won = p.get(_D["is_closed_won"]) == "true"
        is_closed = p.get(_D["is_closed"]) == "true"
        status = ds["won"] if is_won else (ds["lost"] if is_closed else ds["active"])
        owner_id = p.get(_D["owner_id"]) or ""
        owner_info = owners.get(owner_id, {})
        owner_name = owner_info.get("name", "") if isinstance(owner_info, dict) else str(owner_info)
        parts = [
            f"- {p.get(_D['name'], '?')}",
            f"  {dl['stage']}: {p.get(_D['stage'], '?')}",
            f"  {dl['status']}: {status}",
        ]
        if is_closed and not is_won:
            reason = p.get(_D["lost_reason"])
            if reason:
                parts.append(f"  {dl['lost_reason']}: {reason}")
        amt = p.get(_D["amount"])
        if amt:
            parts.append(f"  {dl['amount']}: {amt}")
        cd = p.get(_D["create_date"])
        if cd:
            parts.append(f"  {dl['created']}: {cd[:10]}")
        cld = p.get(_D["close_date"])
        if cld:
            parts.append(f"  {dl['close']}: {cld[:10]}")
        fc = p.get(_D["forecast"])
        if fc:
            parts.append(f"  {dl['forecast']}: {fc}")
        if owner_name:
            parts.append(f"  {dl['owner']}: {owner_name}")
        lines.append("\n".join(parts))
    return "\n\n".join(lines)


_C = {info["internal"]: hs_prop for hs_prop, info in org.CRM_CONTACT_PROPERTIES.items()}


def _format_contacts(
    contacts: list[dict],
    labels: dict,
    contact_deals: dict[str, list[str]] | None = None,
) -> str:
    if not contacts:
        return labels["empty"]["contacts"]
    cl = labels["contact_fields"]
    contact_deals = contact_deals or {}
    lines = []
    for obj in contacts:
        cid = str(obj.get("id", ""))
        p = obj.get("properties", {})
        first = p.get(_C["firstname"]) or ""
        last = p.get(_C["lastname"]) or ""
        name = f"{first} {last}".strip() or labels["empty"]["name"]
        parts = [f"- {name}"]
        jt = p.get(_C["jobtitle"])
        if jt:
            parts.append(f"  {cl['title']}: {jt}")
        em = p.get(_C["email"])
        if em:
            parts.append(f"  {cl['email']}: {em}")
        ph = p.get(_C["phone"])
        if ph:
            parts.append(f"  {cl['phone']}: {ph}")
        deal_names = contact_deals.get(cid)
        if deal_names:
            parts.append(f"  {cl['deals']}: {', '.join(deal_names)}")
        lines.append("\n".join(parts))
    return "\n\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────

def generate(
    atlas_id: str,
    crm_id: str,
    owners: dict | None = None,
    team: str = "",
    owner_email: str = "",
) -> None:
    """Generate atlas for a company. Owners passed from run.py to avoid duplicate fetch."""
    if not atlas_id or not atlas_id.strip():
        print(f"  ATLAS: skipped — empty atlas_id for crm_id={crm_id}")
        return

    print(f"  ATLAS: fetching company {crm_id} ...")
    company = _fetch_company(crm_id)

    # Company name (first property in the dict)
    _name_prop = next(
        k for k, v in org.CRM_COMPANY_PROPERTIES.items() if v["internal"] == "company_name"
    )
    company_name = company.get(_name_prop) or ""

    # Siblings via domain property
    domain = company.get(_DOMAIN_PROP) or ""
    sibling_ids = _fetch_sibling_ids(domain, crm_id) if domain else []

    # Deals + contacts for company + siblings
    all_crm_ids = [crm_id] + sibling_ids
    deal_ids = list({did for cid in all_crm_ids for did in _fetch_association_ids(cid, _ASSOC_DEALS)})
    contact_ids = list({cid_c for cid in all_crm_ids for cid_c in _fetch_association_ids(cid, _ASSOC_CONTACTS)})

    deals = _batch_read(_ASSOC_DEALS, deal_ids, _DEAL_PROPS) if deal_ids else []
    contacts = _batch_read(_ASSOC_CONTACTS, contact_ids, _CONTACT_PROPS) if contact_ids else []

    # Resolve formatting language (before contact→deal mapping so tags are translated)
    lang = get_lang_code(team, owner_email=owner_email or None)
    labels = ATLAS_LABELS.get(lang, ATLAS_LABELS[org.OUTPUT_LANG_DEFAULT])

    # Build contact → deals mapping (which contacts participated in which deals)
    contact_deals: dict[str, list[str]] = {}
    if deals:
        ds = labels["deal_status"]
        for obj in deals:
            did = str(obj.get("id", ""))
            p = obj.get("properties", {})
            dname = p.get(_D["name"], "?")
            is_won = p.get(_D["is_closed_won"]) == "true"
            is_closed = p.get(_D["is_closed"]) == "true"
            tag = ds["won"] if is_won else (ds["lost"] if is_closed else ds["active"])
            assoc_cids = _fetch_association_ids(did, _ASSOC_DEAL_CONTACTS, from_type="deals") if did else []
            for cid in assoc_cids:
                contact_deals.setdefault(cid, []).append(f"{dname} ({tag})")

    # Format
    company_text = _format_company(company, labels)
    deals_text = _format_deals(deals, owners or {}, labels)
    contacts_text = _format_contacts(contacts, labels, contact_deals)

    # Prompt: base (Factorial context) + atlas (specific instructions) + lang
    base_prompt = (PROMPTS_DIR / PROMPTS["atlas_base"]).read_text(encoding="utf-8")
    atlas_prompt = (PROMPTS_DIR / PROMPTS["atlas_system"]).read_text(encoding="utf-8")
    lang_text = get_lang_prompt(team, owner_email=owner_email or None)
    system_prompt = f"{base_prompt}\n\n{atlas_prompt}"
    if lang_text:
        system_prompt += "\n\n" + lang_text

    hdr = labels["headers"]
    today = date.today()
    today_str = today.strftime("%A %d/%m/%Y")
    user_prompt = (
        f"## {hdr['company']}\n{company_text}\n\n"
        f"## {hdr['deals']} ({len(deals)} total)\n{deals_text}\n\n"
        f"## {hdr['contacts']} ({len(contacts)} total)\n{contacts_text}\n\n"
        f"Today's date: {today_str}"
    )

    # Claude
    print(f"  ATLAS: calling Claude ({len(user_prompt)} chars) ...")
    raw = claude.analyze(
        system_prompt, user_prompt,
        model=MODEL_DEFAULT, max_tokens=MAX_TOKENS["atlas"],
    )

    # Parse JSON (with fallback)
    text = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    text = re.sub(r"\s*```$", "", text).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"  ATLAS: JSON parse error for {company_name}: {exc}")
        return

    # Build Supabase row
    row: dict = {}

    # Direct HubSpot → atlas (only properties with matching ATLAS_COLS entry)
    for hs_prop, atlas_col in _HS_TO_ATLAS.items():
        val = company.get(hs_prop)
        if val is not None:
            row[atlas_col] = val

    # Claude output → atlas
    for key in _CLAUDE_KEYS:
        val = parsed.get(key)
        if val is not None:
            row[schema.ATLAS_COLS[key]] = (
                json.dumps(val, ensure_ascii=False) if isinstance(val, dict) else val
            )

    # Generated fields
    row[schema.ATLAS_COLS["company_info"]] = company_text
    row[schema.ATLAS_COLS["deals_breakdown"]] = deals_text
    row[schema.ATLAS_COLS["contacts_breakdown"]] = contacts_text
    row[schema.ATLAS_COLS["sibling_crm_ids"]] = sibling_ids or None
    row[schema.ATLAS_COLS["last_generated"]] = datetime.now(timezone.utc).isoformat()

    supabase.table(_TABLE).update(row).eq(_SYS["id"], atlas_id).execute()
    print(f"  ATLAS: done for {company_name} ({len(deals)} deals, {len(contacts)} contacts)")
