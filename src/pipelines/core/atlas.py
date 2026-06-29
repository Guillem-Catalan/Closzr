"""
Core Atlas — Phase 2 of the CORE pipeline.

Generates company intelligence for a deal's company.
Everything comes from config — this file only orchestrates.
1 Claude call per company (Sonnet).
"""

import json
import re
from datetime import datetime, timezone

from src.config import (
    ATLAS_CONFIG,
    IGNORE_DOMAINS_ATLAS,
    PROMPTS_DIR,
    MODEL_DEFAULT,
    MAX_TOKENS_ATLAS,
)
from src.db.client import supabase
from src.integrations import claude, hubspot

_CFG = ATLAS_CONFIG


# ── HubSpot fetchers ────────────────────────────────────────────────────────

def _fetch_company(crm_id: str) -> dict:
    props = ",".join(_CFG["hs_company_props"])
    data = hubspot.get(f"/crm/v3/objects/companies/{crm_id}", {"properties": props})
    return data.get("properties", {})


def _fetch_association_ids(crm_id: str, object_type: str) -> list[str]:
    ids: list[str] = []
    after = None
    while True:
        params = {"limit": "500"}
        if after:
            params["after"] = after
        data = hubspot.get(f"/crm/v4/objects/companies/{crm_id}/associations/{object_type}", params)
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
        data = hubspot.post(
            f"/crm/v3/objects/{object_type}/batch/read",
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
        "/crm/v3/objects/companies/search",
        {
            "filterGroups": [{"filters": [
                {"propertyName": _CFG["hs_domain_prop"], "operator": "EQ", "value": normalized}
            ]}],
            "properties": [_CFG["hs_company_props"][0]],
            "limit": 50,
        },
    )
    return [r["id"] for r in data.get("results", []) if str(r["id"]) != str(exclude_crm_id)]


# ── Prompt formatters ───────────────────────────────────────────────────────

def _format_company(company: dict) -> str:
    labels = _CFG["company_labels"]
    lines = [f"{labels[key]}: {company[key]}" for key in labels if company.get(key)]
    return "\n".join(lines) if lines else "(sin información de empresa)"


def _format_deals(deals: list[dict], owners: dict) -> str:
    if not deals:
        return "(sin deals asociados)"
    df = _CFG["deal_format_fields"]
    lines = []
    for obj in deals:
        p = obj.get("properties", {})
        is_won = p.get(df["is_closed_won"]) == "true"
        is_closed = p.get(df["is_closed"]) == "true"
        status = "GANADO" if is_won else ("PERDIDO/CERRADO" if is_closed else "ACTIVO")
        owner_id = p.get(df["owner_id"]) or ""
        owner_info = owners.get(owner_id, {})
        owner_name = owner_info.get("name", "") if isinstance(owner_info, dict) else str(owner_info)
        parts = [f"- {p.get(df['name'], '?')}", f"  Stage: {p.get(df['stage'], '?')}", f"  Estado: {status}"]
        amt = p.get(df["amount"])
        if amt: parts.append(f"  Amount: {amt}")
        cd = p.get(df["create_date"])
        if cd: parts.append(f"  Creado: {cd[:10]}")
        cld = p.get(df["close_date"])
        if cld: parts.append(f"  Cierre: {cld[:10]}")
        fc = p.get(df["forecast"])
        if fc: parts.append(f"  Forecast: {fc}")
        if owner_name: parts.append(f"  Owner: {owner_name}")
        lines.append("\n".join(parts))
    return "\n\n".join(lines)


def _format_contacts(contacts: list[dict]) -> str:
    if not contacts:
        return "(sin contactos asociados)"
    cf = _CFG["contact_format_fields"]
    lines = []
    for obj in contacts:
        p = obj.get("properties", {})
        first = p.get(cf["firstname"]) or ""
        last = p.get(cf["lastname"]) or ""
        name = f"{first} {last}".strip() or "(sin nombre)"
        parts = [f"- {name}"]
        jt = p.get(cf["jobtitle"])
        if jt: parts.append(f"  Cargo: {jt}")
        em = p.get(cf["email"])
        if em: parts.append(f"  Email: {em}")
        ph = p.get(cf["phone"])
        if ph: parts.append(f"  Teléfono: {ph}")
        lines.append("\n".join(parts))
    return "\n\n".join(lines)


# ── Main ────────────────────────────────────────────────────────────────────

def generate(atlas_id: str, crm_id: str, owners: dict | None = None, team: str = ""):
    """Generate atlas for a company. Owners passed from run.py to avoid duplicate fetch."""
    print(f"  ATLAS: fetching company {crm_id} ...")
    company = _fetch_company(crm_id)
    company_name = company.get(_CFG["hs_company_props"][0]) or ""

    # Siblings
    website_prop = next(p for p in _CFG["hs_company_props"] if p == "website")
    domain = company.get(website_prop) or ""
    sibling_ids = _fetch_sibling_ids(domain, crm_id) if domain else []

    # Deals + contacts for company + siblings
    all_crm_ids = [crm_id] + sibling_ids
    assoc_deals = _CFG["hs_assoc_deals"]
    assoc_contacts = _CFG["hs_assoc_contacts"]
    deal_ids = list({did for cid in all_crm_ids for did in _fetch_association_ids(cid, assoc_deals)})
    contact_ids = list({cid_c for cid in all_crm_ids for cid_c in _fetch_association_ids(cid, assoc_contacts)})

    deals = _batch_read(assoc_deals, deal_ids, _CFG["hs_deal_props"]) if deal_ids else []
    contacts = _batch_read(assoc_contacts, contact_ids, _CFG["hs_contact_props"]) if contact_ids else []

    # Format
    company_text = _format_company(company)
    deals_text = _format_deals(deals, owners or {})
    contacts_text = _format_contacts(contacts)

    # Prompt: base (contexto Factorial) + atlas (instrucciones específicas) + lang
    from src.lang import get_lang_prompt
    base_prompt = (PROMPTS_DIR / _CFG["base_prompt_path"]).read_text(encoding="utf-8")
    atlas_prompt = (PROMPTS_DIR / _CFG["prompt_path"]).read_text(encoding="utf-8")
    lang_text = get_lang_prompt(team)
    system_prompt = f"{base_prompt}\n\n{atlas_prompt}"
    if lang_text:
        system_prompt += "\n\n" + lang_text
    user_prompt = (
        f"## Empresa\n{company_text}\n\n"
        f"## Deals ({len(deals)} total)\n{deals_text}\n\n"
        f"## Contactos ({len(contacts)} total)\n{contacts_text}"
    )

    # Claude
    print(f"  ATLAS: calling Claude ({len(user_prompt)} chars) ...")
    raw = claude.analyze(system_prompt, user_prompt, model=MODEL_DEFAULT, max_tokens=MAX_TOKENS_ATLAS)

    # Parse
    text = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    text = re.sub(r"\s*```$", "", text).strip()
    parsed = json.loads(text)

    # Build Supabase row from config mappings
    row = {}

    # Direct HubSpot → Supabase
    for hs_prop, sb_col in _CFG["hs_to_supabase"].items():
        val = company.get(hs_prop)
        if val is not None:
            row[sb_col] = val

    # Claude output → Supabase
    for claude_key, sb_col in _CFG["claude_to_supabase"].items():
        val = parsed.get(claude_key)
        if val is not None:
            row[sb_col] = json.dumps(val, ensure_ascii=False) if isinstance(val, dict) else val

    # Generated fields
    gen = _CFG["generated_columns"]
    row[gen["company_info"]] = company_text
    row[gen["deals_breakdown"]] = deals_text
    row[gen["contacts_breakdown"]] = contacts_text
    row[gen["sibling_crm_ids"]] = sibling_ids or None
    row[gen["last_generated"]] = datetime.now(timezone.utc).isoformat()

    supabase.table(_CFG["table"]).update(row).eq("id", atlas_id).execute()
    print(f"  ATLAS: done for {company_name} ({len(deals)} deals, {len(contacts)} contacts)")
