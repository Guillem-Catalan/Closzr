"""
Generate UI config from schema.py + org.py + config2.py → ui/src/config.generated.json

Single source of truth: the 3-file architecture defines everything.
This script extracts what the UI needs and writes a JSON file.
Runs as Vercel prebuild: "prebuild": "python3 ../scripts/generate_ui_config.py"

Zero hardcoded strings — everything derived from:
  schema.py  — business dictionary (stages, pipelines, fields)
  org.py     — external input mappings (CRM, orgchart, domains)
  config2.py — behavior rules (thresholds, scoring, lost reasons)
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import schema, org, config2


# ═══════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════

_INTERNAL_TO_LABELS: dict[str, list[str]] = {}
for _label, _internal in org.CRM_STAGE_LABEL_TO_INTERNAL.items():
    _INTERNAL_TO_LABELS.setdefault(_internal, []).append(_label)


def _pipeline_name(pipeline_id: str) -> str | None:
    entry = org.CRM_PIPELINE_MAP.get(pipeline_id)
    return entry["name"] if entry else None


# ═══════════════════════════════════════════════════════════════════════════
# BUILDERS
# ═══════════════════════════════════════════════════════════════════════════


def build_stages() -> dict:
    """Build stage config from schema.STAGES + org.CRM_STAGE_LABEL_TO_INTERNAL."""

    display = {}
    tones = {}
    macro_stage_map = {}

    category_tones = {
        "prospecting": "ink",
        "nurturing": "amber",
        "demo": "blue",
        "evaluation": "violet",
        "closing": "indigo",
        "won": "green",
        "lost": "red",
        "excluded": "ink",
    }

    tone_overrides = {
        "engaged": "teal",
        "on_hold": "amber",
        "to_reschedule": "amber",
        "product_alignment": "green",
    }

    for label, internal in org.CRM_STAGE_LABEL_TO_INTERNAL.items():
        info = schema.STAGES.get(internal)
        if not info:
            continue

        display[label] = {"short": info["short"], "abbr": info["abbr"]}
        macro_stage_map[label] = info["macro"]

        if internal in tone_overrides:
            tones[label] = tone_overrides[internal]
        else:
            tones[label] = category_tones.get(info["category"], "ink")

    categories: dict[str, list[str]] = {}
    for label, internal in org.CRM_STAGE_LABEL_TO_INTERNAL.items():
        info = schema.STAGES.get(internal)
        if not info:
            continue
        cat = info["category"]
        categories.setdefault(cat, []).append(label)
        if internal not in categories.get(cat, []):
            categories[cat].append(internal)

    for cat in categories:
        categories[cat] = sorted(set(categories[cat]))

    return {
        "display": display,
        "macro_stage_map": macro_stage_map,
        "categories": categories,
        "tones": tones,
    }


def build_teams() -> dict:
    """Build teams dict from org.PARTNERS_ORGCHART + org.DIRECT_SALES + org.XL_SALES."""
    teams = {}

    for name, team in org.PARTNERS_ORGCHART.items():
        leadership = team.get("leadership", {})
        directors = []
        tls = []
        for role_key, person in leadership.items():
            entry = {"email": person["email"], "name": person["name"], "role": person["role"]}
            if "director" in role_key:
                directors.append(entry)
            elif "tl" in role_key:
                tls.append(entry)

        if "tl" in team and isinstance(team["tl"], str):
            tls.append({"email": team["tl"], "name": team.get("tl_name", ""), "role": "TL"})
            all_ae = list(_collect_ds_emails(team) - {team["tl"]})
            teams[name] = {
                "active": team.get("active", False),
                "channel": "partners",
                "directors": directors,
                "tls": tls,
                "pae": sorted(all_ae),
                "pbd": [],
                "ae": [],
                "sdr": [],
            }
        else:
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

    for name, ds_team in _flatten_ds_teams(org.DIRECT_SALES.get("teams", {})):
        directors = []
        tls = []
        if ds_team.get("tl"):
            tls.append({"email": ds_team["tl"], "name": ds_team.get("tl_name", ""), "role": ds_team.get("role", "TL")})

        ae = sorted(ds_team.get("ae", set()))
        for sub in ds_team.get("subteams", {}).values():
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

    xl_mgr = org.XL_SALES.get("country_manager", {})
    teams["XL"] = {
        "active": org.XL_SALES.get("active", False),
        "channel": "xl",
        "directors": [{"email": xl_mgr["email"], "name": xl_mgr["name"], "role": xl_mgr.get("role", "Country Manager")}] if xl_mgr.get("email") else [],
        "tls": [],
        "pae": [],
        "pbd": [],
        "ae": sorted(org.XL_SALES.get("ae", set())),
        "sdr": sorted(org.XL_SALES.get("sdr", set())),
    }

    return teams


def build_funnel() -> list:
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
    return {email: info["name"] for email, info in org.CRM_OWNER_MAP.items()}


def build_known_users() -> dict:
    users = {}
    for email, team in config2._EMAIL_TO_TEAM.items():
        if email in config2.ALL_PAE_EMAILS:
            role = "PAE"
        elif email in config2.ALL_PBD_EMAILS:
            role = "PBD"
        elif email in config2.ALL_DS_EMAILS:
            role = "AE"
        elif email in config2.ALL_XL_EMAILS:
            role = "AE"
        else:
            role = "PAE"
        users[email] = {"role": role, "team": team}

    for email in org.MANAGER_EMAILS:
        if email not in users:
            users[email] = {"role": "Manager", "team": "All"}
        else:
            users[email]["role"] = "Manager"

    return users


def build_pipeline_stages() -> dict:
    """Derive pipeline → open stage labels from CRM_PIPELINE_MAP prefix + schema.STAGE_DATE_FIELDS."""
    prefix_to_pipeline: dict[str, str] = {}
    for pid, entry in org.CRM_PIPELINE_MAP.items():
        prefix = entry.get("prefix")
        if prefix and entry.get("active"):
            prefix_to_pipeline[prefix + "_"] = entry["name"]

    prefixes_sorted = sorted(prefix_to_pipeline.keys(), key=lambda p: -len(p))

    pipeline_stages_raw: dict[str, list[str]] = {name: [] for name in prefix_to_pipeline.values()}
    seen_per_pipeline: dict[str, set[str]] = {name: set() for name in prefix_to_pipeline.values()}

    won_lost_internals = schema.WON | schema.LOST | schema.EXCLUDED

    for col_name in schema.STAGE_DATE_FIELDS:
        if not col_name.endswith("_entered"):
            continue

        base = col_name.removesuffix("_entered")

        matched_prefix = None
        for p in prefixes_sorted:
            if base.startswith(p):
                matched_prefix = p
                break
        if not matched_prefix:
            continue

        pipeline_name = prefix_to_pipeline[matched_prefix]
        stage_slug = base[len(matched_prefix):]

        if stage_slug in won_lost_internals:
            continue

        labels = _INTERNAL_TO_LABELS.get(stage_slug, [])
        if not labels:
            for internal, lbl_list in _INTERNAL_TO_LABELS.items():
                if internal == stage_slug or internal.replace("_", "") == stage_slug.replace("_", ""):
                    labels = lbl_list
                    break

        if not labels:
            stage_info = schema.STAGES.get(stage_slug)
            if stage_info and stage_info["category"] not in ("won", "lost", "excluded"):
                labels = [stage_info["short"]]

        for label in labels:
            if label not in seen_per_pipeline[pipeline_name]:
                seen_per_pipeline[pipeline_name].add(label)
                pipeline_stages_raw[pipeline_name].append(label)
                break

    return pipeline_stages_raw


def build_team_pipelines() -> dict:
    """Derive team → pipeline names from pipeline_ids in orgchart."""
    result = {}

    for name, team in org.PARTNERS_ORGCHART.items():
        pids = team.get("pipeline_ids", [])
        result[name] = [_pipeline_name(pid) for pid in pids if _pipeline_name(pid)]

    ds_pids = org.DIRECT_SALES.get("pipeline_ids", [])
    ds_pipelines = [_pipeline_name(pid) for pid in ds_pids if _pipeline_name(pid)]

    for name, _ in _flatten_ds_teams(org.DIRECT_SALES.get("teams", {})):
        result[name] = ds_pipelines

    xl_pids = org.XL_SALES.get("pipeline_ids", [])
    result["XL"] = [_pipeline_name(pid) for pid in xl_pids if _pipeline_name(pid)]

    return result


def build_team_hierarchy() -> dict:
    """Derive parent → children from org.DIRECT_SALES structure."""
    hierarchy = {}
    _walk_hierarchy(org.DIRECT_SALES.get("teams", {}), hierarchy)
    return hierarchy


def build_stage_roadmaps() -> dict:
    """Derive per-pipeline stage roadmap from schema.STAGE_DATE_FIELDS + CRM_PIPELINE_MAP prefix."""
    prefix_to_pipeline: dict[str, str] = {}
    for pid, entry in org.CRM_PIPELINE_MAP.items():
        prefix = entry.get("prefix")
        if prefix and entry.get("active"):
            prefix_to_pipeline[prefix + "_"] = entry["name"]

    prefixes_sorted = sorted(prefix_to_pipeline.keys(), key=lambda p: -len(p))

    roadmaps: dict[str, list[dict]] = {name: [] for name in prefix_to_pipeline.values()}

    for col_name in schema.STAGE_DATE_FIELDS:
        if not col_name.endswith("_entered"):
            continue

        base = col_name.removesuffix("_entered")

        matched_prefix = None
        for p in prefixes_sorted:
            if base.startswith(p):
                matched_prefix = p
                break
        if not matched_prefix:
            continue

        pipeline_name = prefix_to_pipeline[matched_prefix]
        stage_slug = base[len(matched_prefix):]

        labels = _INTERNAL_TO_LABELS.get(stage_slug, [])
        display_label = labels[0] if labels else schema.STAGES.get(stage_slug, {}).get("short", stage_slug)

        roadmaps[pipeline_name].append({
            "key": base,
            "label": display_label,
        })

    return roadmaps


# ═══════════════════════════════════════════════════════════════════════════
# HELPERS (internal)
# ═══════════════════════════════════════════════════════════════════════════


def _collect_ds_emails(node: dict) -> set[str]:
    """Collect all emails from a DS-style tree (tl/ae/subteams)."""
    emails: set[str] = set()
    emails |= node.get("ae", set())
    if "tl" in node and isinstance(node["tl"], str):
        emails.add(node["tl"])
    for sub in node.get("subteams", {}).values():
        emails |= _collect_ds_emails(sub)
    return emails


def _flatten_ds_teams(teams: dict) -> list[tuple[str, dict]]:
    result = []
    for name, team in teams.items():
        result.append((name, team))
        result.extend(_flatten_ds_teams(team.get("subteams", {})))
    return result


def _walk_hierarchy(teams: dict, result: dict):
    for name, team in teams.items():
        subs = team.get("subteams", {})
        if subs:
            result[name] = list(subs.keys())
            _walk_hierarchy(subs, result)


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════


def build_meddic_axes() -> list:
    return [
        {"key": "M",    "short": "M",    "label": "Metrics"},
        {"key": "E",    "short": "E",    "label": "Economic Buyer"},
        {"key": "DC",   "short": "DC",   "label": "Decision Criteria"},
        {"key": "DP",   "short": "DP",   "label": "Decision Process"},
        {"key": "I",    "short": "I",    "label": "Identify Pain"},
        {"key": "C",    "short": "C",    "label": "Champion"},
        {"key": "Comp", "short": "Comp", "label": "Competition"},
    ]


def build_methodology_name() -> str:
    axes = build_meddic_axes()
    return "MEDDICC" if len(axes) == 7 else "MEDDIC"


def build_role_labels() -> dict:
    return {
        "Admin": "Admin",
        "Manager": "Manager",
        "Director": "Director",
        "TL": "TL",
        "PAE": "PAE",
        "PBD": "PBD",
        "AE": "AE",
        "SDR": "SDR",
    }


def main():
    won_labels = []
    lost_labels = []
    for label, internal in org.CRM_STAGE_LABEL_TO_INTERNAL.items():
        info = schema.STAGES.get(internal)
        if not info:
            continue
        if info["category"] == "won":
            won_labels.append(label)
        if info["category"] == "lost":
            lost_labels.append(label)
    won_labels.sort(key=lambda l: (0 if "closed won" in l.lower() else 1, l))
    lost_labels.sort(key=lambda l: (0 if "closed lost" in l.lower() else 1, l))

    config = {
        "crm_name": org.CRM_NAME,
        "crm_short": org.CRM_SHORT,
        "crm_account_id": org.CRM_ACCOUNT_ID,
        "crm_forecast_categories": org.CRM_FORECAST_CATEGORIES,
        "org_name": org.ORG_NAME,
        "org_domains": sorted(org.INTERNAL_DOMAINS),
        "teams": build_teams(),
        "active_teams": sorted(config2.ACTIVE_TEAMS),
        "stages": build_stages(),
        "won_display_label": won_labels[0] if won_labels else "Won",
        "lost_display_label": lost_labels[0] if lost_labels else "Lost",
        "funnel": build_funnel(),
        "funnel_aside": build_funnel_aside(),
        "stale_thresholds": config2.STALE_THRESHOLDS,
        "stale_default": config2.STALE_DEFAULT,
        "owner_names": build_owner_names(),
        "known_users": build_known_users(),
        "managers": sorted(org.MANAGER_EMAILS),
        "pipeline_stages": build_pipeline_stages(),
        "team_pipelines": build_team_pipelines(),
        "team_hierarchy": build_team_hierarchy(),
        "stage_roadmaps": build_stage_roadmaps(),
        "lost_reasons": config2.LOST_REASONS,
        "meddic_axes": build_meddic_axes(),
        "methodology_name": build_methodology_name(),
        "won_label": "Won",
        "lost_label": "Lost",
        "default_role": "AE",
        "role_labels": build_role_labels(),
        # backward compat
        "hubspot_account_id": org.CRM_ACCOUNT_ID,
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
    print(f"  {len(config['pipeline_stages'])} pipelines with stage lists")
    print(f"  {len(config['team_pipelines'])} team → pipeline mappings")
    print(f"  {len(config['team_hierarchy'])} team hierarchy entries")
    print(f"  {len(config['stage_roadmaps'])} pipeline roadmaps")


if __name__ == "__main__":
    main()
