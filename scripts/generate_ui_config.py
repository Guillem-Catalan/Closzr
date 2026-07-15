"""
Generate UI config from config.py → ui/src/config.generated.json

Single source of truth: config.py defines teams, stages, roles, thresholds.
This script extracts what the UI needs and writes a JSON file.
Runs as Vercel prebuild: "prebuild": "python3 ../scripts/generate_ui_config.py"

Usage:
    python3 scripts/generate_ui_config.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import (
    # Teams & org
    PARTNERS_ORGCHART,
    DIRECT_SALES_ES,
    XL_SALES,
    MANAGER_EMAILS,
    ACTIVE_TEAMS,
    HUBSPOT_OWNER_IDS,
    HUBSPOT_ACCOUNT_ID,
    # Stages
    STAGE_DISPLAY,
    STAGE_PROSPECTING,
    STAGE_NURTURING,
    STAGE_DEMO,
    STAGE_EVALUATION,
    STAGE_CLOSING,
    STAGE_WON,
    STAGE_LOST,
    # Parser config (macro_stage_map, stale_thresholds)
    PARSER_CONFIG,
    # Pipeline stages
    PIPELINE_STAGES,
)


def build_teams() -> dict:
    """Build teams dict from PARTNERS_ORGCHART + DIRECT_SALES_ES + XL_SALES."""
    teams = {}

    # Partners
    for name, team in PARTNERS_ORGCHART.items():
        leadership = team.get("leadership", {})
        directors = []
        tls = []
        for role_key, person in leadership.items():
            if "director" in role_key:
                directors.append({"email": person["email"], "name": person["name"], "role": person["role"]})
            elif "tl" in role_key:
                tls.append({"email": person["email"], "name": person["name"], "role": person["role"]})

        teams[name] = {
            "active": team.get("active", False),
            "channel": "partners",
            "directors": directors,
            "tls": tls,
            "pae": sorted(team.get("pae", set())),
            "pbd": sorted(team.get("pbd", set())),
            "ae": [],
            "sdr": [],
        }

    # Direct Sales
    ds_director = DIRECT_SALES_ES.get("sales_director", {})
    for name, ds_team in DIRECT_SALES_ES.get("teams", {}).items():
        directors = []
        if ds_director.get("email"):
            directors.append({"email": ds_director["email"], "name": ds_director["name"], "role": ds_director["role"]})

        tls = []
        if ds_team.get("tl"):
            tls.append({"email": ds_team["tl"], "name": ds_team.get("tl_name", ""), "role": ds_team.get("role", "TL")})

        ae = sorted(ds_team.get("ae", set()))

        # Collect AEs from subteams
        for sub_name, sub in ds_team.get("subteams", {}).items():
            if sub.get("tl"):
                tls.append({"email": sub["tl"], "name": sub.get("tl_name", ""), "role": "Sub-TL"})
            ae.extend(sorted(sub.get("ae", set())))

        teams[name] = {
            "active": ds_team.get("active", False),
            "channel": "ds",
            "directors": directors,
            "tls": tls,
            "pae": [],
            "pbd": [],
            "ae": sorted(set(ae)),
            "sdr": [],
        }

    # XL
    xl_director = XL_SALES.get("country_manager", {})
    teams["XL"] = {
        "active": XL_SALES.get("active", False),
        "channel": "xl",
        "directors": [{"email": xl_director["email"], "name": xl_director["name"], "role": xl_director["role"]}] if xl_director.get("email") else [],
        "tls": [],
        "pae": [],
        "pbd": [],
        "ae": sorted(XL_SALES.get("ae", set())),
        "sdr": sorted(XL_SALES.get("sdr", set())),
    }

    return teams


def build_stages() -> dict:
    """Build stage config: display names, categories, funnel grouping."""

    # Stage display: label → {short, abbr}
    display = {}
    for label, info in STAGE_DISPLAY.items():
        display[label] = {"short": info["short"], "abbr": info["abbr"]}

    # Stage → macro_stage (from PARSER_CONFIG, the actual source used by parser.py)
    macro_stage_map = PARSER_CONFIG["macro_stage_map"]

    # Stage categories (from the frozensets in config.py)
    categories = {
        "prospecting": sorted(STAGE_PROSPECTING),
        "nurturing": sorted(STAGE_NURTURING),
        "demo": sorted(STAGE_DEMO),
        "evaluating": sorted(STAGE_EVALUATION),
        "closing": sorted(STAGE_CLOSING),
        "won": sorted(STAGE_WON),
        "lost": sorted(STAGE_LOST),
    }

    # Stage tone: derive from category
    category_tones = {
        "prospecting": "ink",
        "nurturing": "amber",
        "demo": "blue",
        "evaluating": "violet",
        "closing": "indigo",
        "won": "green",
        "lost": "red",
    }

    tones = {}
    for cat, stages in categories.items():
        tone = category_tones[cat]
        for s in stages:
            tones[s] = tone
    # Special overrides
    tones["Engaged"] = "teal"
    tones["On Hold"] = "amber"
    tones["To reschedule"] = "amber"
    tones["To Reschedule"] = "amber"
    tones["Product Alignment"] = "green"

    return {
        "display": display,
        "macro_stage_map": macro_stage_map,
        "categories": categories,
        "tones": tones,
    }


def build_funnel() -> list:
    """Pipeline funnel definition — order matters."""
    return [
        {"key": "prospecting", "label": "Prospecting", "tone": "ink"},
        {"key": "qualifying", "label": "Qualifying", "tone": "blue"},
        {"key": "nurturing", "label": "Nurturing", "tone": "amber"},
        {"key": "demo", "label": "Demo", "tone": "teal"},
        {"key": "evaluating", "label": "Evaluating", "tone": "violet"},
        {"key": "closing", "label": "Closing", "tone": "indigo"},
        {"key": "won", "label": "Closed Won", "tone": "green"},
    ]


def build_funnel_aside() -> list:
    return [
        {"key": "onhold", "label": "On Hold", "tone": "amber"},
        {"key": "other", "label": "Other", "tone": "ink"},
    ]


def build_owner_names() -> dict:
    """email → display name from HUBSPOT_OWNER_IDS."""
    return {email: info["name"] for email, info in HUBSPOT_OWNER_IDS.items()}


def build_known_users() -> dict:
    """email → {role, team} for auto-detection on signup."""
    from src.config import ALL_PBD_EMAILS, ALL_PAE_EMAILS, ALL_DS_EMAILS, ALL_XL_EMAILS, _EMAIL_TO_TEAM

    users = {}
    for email, team in _EMAIL_TO_TEAM.items():
        if email in ALL_PAE_EMAILS:
            role = "PAE"
        elif email in ALL_PBD_EMAILS:
            role = "PBD"
        elif email in ALL_DS_EMAILS:
            role = "AE"
        elif email in ALL_XL_EMAILS:
            role = "AE"
        else:
            role = "PAE"
        users[email] = {"role": role, "team": team}

    for email in MANAGER_EMAILS:
        if email not in users:
            users[email] = {"role": "Manager", "team": "All"}
        else:
            users[email]["role"] = "Manager"

    return users


def main():
    config = {
        "hubspot_account_id": HUBSPOT_ACCOUNT_ID,
        "teams": build_teams(),
        "active_teams": sorted(ACTIVE_TEAMS),
        "stages": build_stages(),
        "funnel": build_funnel(),
        "funnel_aside": build_funnel_aside(),
        "stale_thresholds": PARSER_CONFIG["stale_thresholds"],
        "stale_default": PARSER_CONFIG["stale_default"],
        "owner_names": build_owner_names(),
        "known_users": build_known_users(),
        "managers": sorted(MANAGER_EMAILS),
        "pipeline_stages": PIPELINE_STAGES,
    }

    out_path = ROOT / "ui" / "src" / "config.generated.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n")
    print(f"Generated {out_path} ({out_path.stat().st_size:,} bytes)")
    print(f"  {len(config['teams'])} teams ({len(config['active_teams'])} active)")
    print(f"  {len(config['stages']['display'])} stage display entries")
    print(f"  {len(config['stages']['macro_stage_map'])} macro_stage mappings")
    print(f"  {len(config['owner_names'])} owner names")
    print(f"  {len(config['known_users'])} known users for auto-signup")


if __name__ == "__main__":
    main()
