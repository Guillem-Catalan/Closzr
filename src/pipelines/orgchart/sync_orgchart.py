"""
Orgchart Sync — reads the orgchart Supabase table and regenerates org_people.py.

Triggered from the UI when a TL changes team membership (add/remove/move person).
Not part of core/daily/weekly/monthly — runs independently on demand.

Flow:
  1. Fetch all rows from orgchart table
  2. Reconstruct PARTNERS_ORGCHART, DIRECT_SALES, XL_SALES, CRM_OWNER_MAP, etc.
  3. Write src/org_people.py with the new data
  4. Return a summary of what changed
"""

from __future__ import annotations

import sys
from pathlib import Path
from textwrap import indent

ROOT = Path(__file__).resolve().parent.parent.parent.parent
ORG_PEOPLE_PATH = ROOT / "src" / "org_people.py"

sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from src.db.client import supabase
from src.org import TEAM_PIPELINE_CONFIG


# ── Fetch ────────────────────────────────────────────────────────────────────

def fetch_orgchart() -> list[dict]:
    resp = supabase.table("orgchart").select("*").order("hierarchy_level").execute()
    return resp.data or []


# ── Reconstruct structures ───────────────────────────────────────────────────

def _build_crm_owner_map(rows: list[dict]) -> dict:
    result = {}
    for r in rows:
        hs_id = r.get("hs_owner_id")
        if hs_id:
            result[r["email"]] = {"id": str(hs_id), "name": r["full_name"]}
    return dict(sorted(result.items()))


def _build_manager_emails(rows: list[dict]) -> set[str]:
    return {r["email"] for r in rows if r.get("role") == "Manager"}


_LANG_OVERRIDE_FALLBACK = {
    "andre.reis@factorial.co": "pt",
}


def _build_person_lang_override(rows: list[dict]) -> dict[str, str]:
    result = dict(_LANG_OVERRIDE_FALLBACK)
    for r in rows:
        if r.get("lang_override"):
            result[r["email"]] = r["lang_override"]
    return result


def _children_of(email: str, rows: list[dict]) -> list[dict]:
    return [r for r in rows if r.get("reports_to") == email]


# ── Partner teams (old format: leadership/pbd/pae) ──────────────────────────

def _build_old_partner_team(team_name: str, people: list[dict], all_rows: list[dict]) -> dict:
    cfg = TEAM_PIPELINE_CONFIG.get(team_name, {})
    team: dict = {
        "active": cfg.get("active", False),
        "pipeline_ids": cfg.get("pipeline_ids", []),
    }

    leadership = {}
    pbd: set[str] = set()
    pae: set[str] = set()

    tls = [p for p in people if p["role"] == "TL"]
    for tl in tls:
        reports = _children_of(tl["email"], all_rows)
        pae_count = sum(1 for r in reports if r["role"] == "PAE")
        pbd_count = sum(1 for r in reports if r["role"] == "PBD")
        if pbd_count > pae_count:
            leadership["tl_pbd"] = {"email": tl["email"], "name": tl["full_name"], "role": tl["role"]}
        else:
            leadership["tl_pae"] = {"email": tl["email"], "name": tl["full_name"], "role": tl["role"]}

    for p in people:
        role = p["role"]
        if role == "Head":
            leadership["head"] = {"email": p["email"], "name": p["full_name"], "role": role}
        elif role == "Director":
            leadership["director"] = {"email": p["email"], "name": p["full_name"], "role": role}
        elif role == "PDM":
            leadership["pdm"] = {"email": p["email"], "name": p["full_name"], "role": role}
        elif role == "PAE":
            pae.add(p["email"])
        elif role == "PBD":
            pbd.add(p["email"])

    if leadership:
        team["leadership"] = leadership
    if pbd:
        team["pbd"] = pbd
    if pae:
        team["pae"] = pae

    return team


# ── DS-style teams (tl/subteams/ae recursive) ───────────────────────────────

def _build_ds_node(tl_row: dict, all_rows: list[dict]) -> dict:
    node: dict = {
        "active": tl_row.get("is_active", True),
        "tl": tl_row["email"],
        "tl_name": tl_row["full_name"],
    }
    children = _children_of(tl_row["email"], all_rows)
    ae_emails: set[str] = set()
    subteams: dict = {}

    for child in children:
        child_is_tl = child["role"] == "TL"
        has_reports = bool(_children_of(child["email"], all_rows))
        if child_is_tl or has_reports:
            sub_node = _build_ds_node(child, all_rows)
            subteams[child.get("team_name", child["email"])] = sub_node
        else:
            ae_emails.add(child["email"])

    if subteams:
        node["subteams"] = subteams
    if ae_emails:
        node["ae"] = ae_emails

    return node


def _is_old_format(team_name: str) -> bool:
    cfg = TEAM_PIPELINE_CONFIG.get(team_name, {})
    return cfg.get("format") == "partner"


# ── Build all structures ─────────────────────────────────────────────────────

def _find_root(email: str, email_map: dict[str, dict]) -> str:
    visited = set()
    cur = email
    while cur in email_map:
        if cur in visited:
            break
        visited.add(cur)
        parent = email_map[cur].get("reports_to")
        if not parent or parent not in email_map:
            return cur
        cur = parent
    return cur


def _group_partners_by_root(partner_rows: list[dict]) -> dict[str, list[dict]]:
    email_map = {r["email"]: r for r in partner_rows}
    groups: dict[str, list[dict]] = {}
    for r in partner_rows:
        root_email = _find_root(r["email"], email_map)
        root_team = email_map[root_email]["team_name"]
        groups.setdefault(root_team, []).append(r)
    return groups


def build_partners_orgchart(rows: list[dict]) -> dict:
    partner_rows = [r for r in rows if r.get("channel") == "partners"]
    groups = _group_partners_by_root(partner_rows)

    result = {}
    for team_name in TEAM_PIPELINE_CONFIG:
        if team_name in ("DIRECT_SALES", "XL"):
            continue
        cfg = TEAM_PIPELINE_CONFIG.get(team_name, {})
        people = groups.get(team_name, [])

        if not people:
            result[team_name] = {
                "active": cfg.get("active", False),
                "pipeline_ids": cfg.get("pipeline_ids", []),
            }
            continue

        if _is_old_format(team_name):
            result[team_name] = _build_old_partner_team(team_name, people, rows)
        else:
            partner_emails = {p["email"] for p in people}
            roots = [p for p in people if not p.get("reports_to")
                     or p["reports_to"] not in partner_emails]
            if len(roots) == 1:
                node = _build_ds_node(roots[0], rows)
                node["active"] = cfg.get("active", True)
                node["pipeline_ids"] = cfg.get("pipeline_ids", [])
                result[team_name] = node
            else:
                result[team_name] = {
                    "active": cfg.get("active", True),
                    "pipeline_ids": cfg.get("pipeline_ids", []),
                }

    return result


def build_direct_sales(rows: list[dict]) -> dict:
    cfg = TEAM_PIPELINE_CONFIG.get("DIRECT_SALES", {})
    ds_rows = [r for r in rows if r.get("channel") == "direct_sales"]

    roots = [r for r in ds_rows if not r.get("reports_to")
             or r["reports_to"] not in {rr["email"] for rr in ds_rows}]

    teams = {}
    for root in roots:
        teams[root.get("team_name", root["email"])] = _build_ds_node(root, rows)

    return {
        "pipeline_ids": cfg.get("pipeline_ids", []),
        "teams": teams,
    }


def build_xl_sales(rows: list[dict]) -> dict:
    cfg = TEAM_PIPELINE_CONFIG.get("XL", {})
    xl_rows = [r for r in rows if r.get("channel") == "xl"]

    cm_rows = [r for r in xl_rows if r.get("role") == "Country_Manager"]
    ae_emails = {r["email"] for r in xl_rows if r.get("role") in ("AE", "Country_Manager")}
    sdr_emails = {r["email"] for r in xl_rows if r.get("role") == "SDR"}

    result: dict = {
        "active": cfg.get("active", True),
        "pipeline_ids": cfg.get("pipeline_ids", []),
    }
    if cm_rows:
        result["country_manager"] = {
            "email": cm_rows[0]["email"],
            "name": cm_rows[0]["full_name"],
        }
    if ae_emails:
        result["ae"] = ae_emails
    if sdr_emails:
        result["sdr"] = sdr_emails

    return result


# ── Python source formatting ─────────────────────────────────────────────────

def _fmt(obj, depth=0) -> str:
    ind = "    " * depth
    ind1 = "    " * (depth + 1)

    if isinstance(obj, dict):
        if not obj:
            return "{}"
        items = []
        for k, v in obj.items():
            items.append(f"{ind1}{_fmt(k)}: {_fmt(v, depth + 1)},")
        return "{\n" + "\n".join(items) + f"\n{ind}}}"

    if isinstance(obj, set):
        if not obj:
            return "set()"
        elems = sorted(obj)
        if len(elems) <= 2:
            inner = ", ".join(f'"{e}"' for e in elems)
            return "{" + inner + "}"
        items = [f'{ind1}"{e}",' for e in elems]
        return "{\n" + "\n".join(items) + f"\n{ind}}}"

    if isinstance(obj, list):
        if not obj:
            return "[]"
        inner = ", ".join(repr(e) for e in obj)
        return f"[{inner}]"

    if isinstance(obj, bool):
        return "True" if obj else "False"

    if isinstance(obj, str):
        return repr(obj)

    return repr(obj)


def generate_source(rows: list[dict]) -> str:
    crm_owner_map = _build_crm_owner_map(rows)
    partners = build_partners_orgchart(rows)
    ds = build_direct_sales(rows)
    xl = build_xl_sales(rows)
    managers = _build_manager_emails(rows)
    lang_override = _build_person_lang_override(rows)

    parts = [
        '"""',
        "org_people.py — People & Team Membership Data",
        "",
        "Auto-generated from the orgchart Supabase table by src/pipelines/orgchart/sync_orgchart.py.",
        "Manual edits will be overwritten on the next orgchart sync.",
        "",
        "Contains:",
        "  CRM_OWNER_MAP       — email -> {id, name} for HubSpot owner resolution",
        "  PARTNERS_ORGCHART   — partner team structures (Telefonica, TIM, TELEKOM, Mexico)",
        "  DIRECT_SALES        — direct sales team hierarchy",
        "  XL_SALES            — XL/enterprise sales team",
        "  MANAGER_EMAILS      — set of manager emails",
        "  PERSON_LANG_OVERRIDE — per-person language exceptions",
        '"""',
        "",
        f"CRM_OWNER_MAP = {_fmt(crm_owner_map)}",
        "",
        f"PARTNERS_ORGCHART = {_fmt(partners)}",
        "",
        f"DIRECT_SALES = {_fmt(ds)}",
        "",
        f"XL_SALES = {_fmt(xl)}",
        "",
        f"MANAGER_EMAILS = {_fmt(managers)}",
        "",
        f"PERSON_LANG_OVERRIDE: dict[str, str] = {_fmt(lang_override)}",
        "",
    ]
    return "\n".join(parts)


# ── Main ─────────────────────────────────────────────────────────────────────

def run() -> dict:
    rows = fetch_orgchart()
    if not rows:
        return {"status": "error", "message": "No rows in orgchart table"}

    source = generate_source(rows)
    ORG_PEOPLE_PATH.write_text(source)

    active = sum(1 for r in rows if r.get("is_active"))
    return {
        "status": "ok",
        "total_people": len(rows),
        "active": active,
        "file": str(ORG_PEOPLE_PATH),
    }


if __name__ == "__main__":
    result = run()
    print(result)
