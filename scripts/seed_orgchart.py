"""
Seed the orgchart table from org.py data.

Reads PARTNERS_ORGCHART, DIRECT_SALES, XL_SALES, MANAGER_EMAILS,
and CRM_OWNER_MAP, then upserts all people into the orgchart table.

Idempotent — safe to run multiple times.

Usage:
    python scripts/seed_orgchart.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from src import org
from src.db.client import supabase


def _resolve_name(email: str, tl_name: str | None = None) -> str:
    if tl_name:
        return tl_name
    info = org.CRM_OWNER_MAP.get(email)
    if info and info.get("name"):
        return info["name"]
    return email.split("@")[0].replace(".", " ").title()


def _hs_id(email: str) -> str | None:
    info = org.CRM_OWNER_MAP.get(email)
    return info["id"] if info else None


def _add(rows: list, seen: set, email: str, full_name: str, role: str,
         channel: str, team_name: str, reports_to: str | None,
         hierarchy_level: int, is_active: bool = True):
    if email in seen:
        return
    seen.add(email)
    rows.append({
        "email": email,
        "full_name": full_name,
        "hs_owner_id": _hs_id(email),
        "role": role,
        "channel": channel,
        "team_name": team_name,
        "reports_to": reports_to,
        "hierarchy_level": hierarchy_level,
        "is_active": is_active,
        "target_mrr": 0,
        "additional_teams": [],
    })


def _collect_partners_old_format(team_name: str, team: dict, rows: list, seen: set):
    """Telefonica, TIM, TELEKOM — old format with leadership/pbd/pae."""
    leadership = team.get("leadership", {})
    is_active = team.get("active", False)

    director_email = None
    tl_pae_email = None
    tl_pbd_email = None

    for role_key, person in leadership.items():
        email = person["email"]
        name = person["name"]
        if "head" in role_key:
            _add(rows, seen, email, name, "Head", "partners", team_name, None, 0, is_active)
        elif "director" in role_key:
            director_email = email
            _add(rows, seen, email, name, "Director", "partners", team_name, None, 1, is_active)
        elif "tl_pae" in role_key or "tl" == role_key:
            tl_pae_email = email
            _add(rows, seen, email, name, "TL", "partners", team_name, director_email, 2, is_active)
        elif "tl_pbd" in role_key:
            tl_pbd_email = email
            _add(rows, seen, email, name, "TL", "partners", team_name, director_email, 2, is_active)
        elif "pdm" in role_key:
            _add(rows, seen, email, name, "PDM", "partners", team_name, director_email or tl_pbd_email, 2, is_active)

    for email in team.get("pae", set()):
        _add(rows, seen, email, _resolve_name(email), "PAE", "partners", team_name, tl_pae_email, 3, is_active)

    for email in team.get("pbd", set()):
        _add(rows, seen, email, _resolve_name(email), "PBD", "partners", team_name, tl_pbd_email, 3, is_active)


def _collect_ds_tree(node: dict, team_name: str, channel: str,
                     parent_email: str | None, depth: int,
                     rows: list, seen: set):
    """Recursive traversal of tl/subteams/ae format (DIRECT_SALES + Mexico)."""
    is_active = node.get("active", True)

    tl_email = node.get("tl")
    if tl_email and isinstance(tl_email, str):
        _add(rows, seen, tl_email, _resolve_name(tl_email, node.get("tl_name")),
             "TL", channel, team_name, parent_email, depth, is_active)

    for ae_email in node.get("ae", set()):
        _add(rows, seen, ae_email, _resolve_name(ae_email),
             "AE", channel, team_name, tl_email, depth + 1, is_active)

    for sub_name, sub in node.get("subteams", {}).items():
        _collect_ds_tree(sub, sub_name, channel, tl_email, depth + 1, rows, seen)


def build_rows() -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()

    # --- PARTNERS (old format: Telefonica, TIM, TELEKOM) ---
    for team_name, team in org.PARTNERS_ORGCHART.items():
        if "tl" in team and isinstance(team["tl"], str):
            # DS-style format (Mexico)
            _collect_ds_tree(team, team_name, "partners", None, 0, rows, seen)
        else:
            _collect_partners_old_format(team_name, team, rows, seen)

    # --- DIRECT SALES ---
    for team_name, team in org.DIRECT_SALES.get("teams", {}).items():
        _collect_ds_tree(team, team_name, "direct_sales", None, 0, rows, seen)

    # --- XL SALES ---
    cm = org.XL_SALES.get("country_manager", {})
    cm_email = cm.get("email")
    if cm_email:
        _add(rows, seen, cm_email, cm.get("name", ""), "Country_Manager", "xl", "XL", None, 0)
    for ae_email in org.XL_SALES.get("ae", set()):
        _add(rows, seen, ae_email, _resolve_name(ae_email), "AE", "xl", "XL", cm_email, 1)
    for sdr_email in org.XL_SALES.get("sdr", set()):
        _add(rows, seen, sdr_email, _resolve_name(sdr_email), "SDR", "xl", "XL", cm_email, 1)

    # --- MANAGERS ---
    for email in org.MANAGER_EMAILS:
        _add(rows, seen, email, _resolve_name(email), "Manager", "management", "Management", None, 0)

    # --- CRM_OWNER_MAP orphans ---
    for email, info in org.CRM_OWNER_MAP.items():
        if email not in seen:
            _add(rows, seen, email, info.get("name", email), "AE", "management", "Unassigned", None, 0, False)

    # --- Multi-team: mark additional_teams ---
    from src import config2
    for email, teams in config2._EMAIL_TO_TEAMS.items():
        if len(teams) > 1:
            row = next((r for r in rows if r["email"] == email), None)
            if row:
                primary = row["team_name"]
                extra = [t for t in teams if t != primary]
                if extra:
                    row["additional_teams"] = extra

    return rows


def main():
    rows = build_rows()
    rows.sort(key=lambda r: r["hierarchy_level"])

    print(f"Seeding orgchart with {len(rows)} people...")

    batch_size = 50
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        supabase.table("orgchart").upsert(batch, on_conflict="email").execute()

    active = sum(1 for r in rows if r["is_active"])
    inactive = len(rows) - active
    channels = {}
    for r in rows:
        channels[r["channel"]] = channels.get(r["channel"], 0) + 1
    roles = {}
    for r in rows:
        roles[r["role"]] = roles.get(r["role"], 0) + 1

    print(f"  {active} active, {inactive} inactive")
    print(f"  By channel: {channels}")
    print(f"  By role: {roles}")
    print("Done.")


if __name__ == "__main__":
    main()
