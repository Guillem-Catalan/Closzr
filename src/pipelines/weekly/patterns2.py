"""
Weekly Patterns v2 — generates and updates learned_patterns.

Two types:
  1. Text patterns (Claude) — generalizations from deal lessons
  2. Statistical patterns (Python) — calculated from trajectory numbers

Patterns accumulate — never deleted. Updated via upsert by pattern_key.
History tracked in JSONB column.
Internal names everywhere: schema.tbl(), schema.col(), config2.*.
"""

import json
import re
from datetime import date
from collections import defaultdict

from src import schema
from src.config2 import (
    WEEKLY,
    PROMPTS_DIR,
    MODEL_DEFAULT,
    MAX_TOKENS,
    MRR_RANGES,
    MIN_TRAJECTORIES_FOR_PATTERNS,
)
from src.db.client import supabase
from src.integrations import claude


# ═══════════════════════════════════════════════════════════════════════════
# RESOLVED CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════

_TBL_TRAJECTORIES = schema.tbl("trajectories")
_TBL_PATTERNS     = schema.tbl("patterns")

# ── Trajectory columns (schema mapping) ──
_TC = schema.TRAJECTORY_COLS

# ── Pattern columns (no schema mapping — stable table) ──
_P_KEY        = "pattern_key"
_P_TYPE       = "pattern_type"
_P_SCOPE      = "scope"
_P_PATTERN    = "pattern"
_P_CONFIDENCE = "confidence"
_P_SAMPLE     = "sample_size"
_P_VALUE      = "value"
_P_HISTORY    = "history"
_P_UPDATED    = "updated_at"
_P_GENERATED  = "generated_at"
_P_ID         = "id"

# ── Select strings (built from constants) ──
_TRAJ_SELECT = ", ".join([
    _TC["outcome"], _TC["amount"], _TC["deal_age_days"], _TC["team"],
    _TC["pipeline_name"], _TC["closed_lost_reason"], _TC["close_date"],
    _TC["trajectory"], _TC["stage_dates"], _TC["lessons"],
])

_EXISTING_SELECT = ", ".join([
    _P_KEY, _P_TYPE, _P_SCOPE, _P_PATTERN, _P_CONFIDENCE, _P_SAMPLE,
])

_UPSERT_SELECT = ", ".join([
    _P_ID, _P_HISTORY, _P_CONFIDENCE, _P_SAMPLE, _P_VALUE,
])

# ── Prefixes for statistical pattern keys (to separate from text patterns) ──
_STAT_PREFIXES = (
    "temporal_", "stage_velocity_", "stage_conversion_",
    "size_close_", "win_rate_", "pipeline_",
)

# ── Pipeline prefixes derived from schema.STAGE_DATE_FIELDS ──
# For each field, find the longest matching stage → shortest prefix.
# e.g. "xlsdr_connected_not_engaged_entered" → stage "connected_not_engaged" → prefix "xlsdr_"
def _derive_pipeline_prefixes() -> tuple[str, ...]:
    prefixes: set[str] = set()
    for col in schema.STAGE_DATE_FIELDS:
        base = col.removesuffix("_entered").removesuffix("_exited")
        best_len, best_prefix = 0, None
        for stage in schema.STAGES:
            if base.endswith("_" + stage) and len(stage) > best_len:
                best_len = len(stage)
                best_prefix = base[:len(base) - len(stage) - 1] + "_"
        if best_prefix:
            prefixes.add(best_prefix)
    return tuple(sorted(prefixes, key=lambda p: -len(p)))

_PIPELINE_PREFIXES = _derive_pipeline_prefixes()


# ═══════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _stage_display_name(stage_key: str) -> str:
    """Convert a stage_dates key (e.g. 'dist_demo_booked') to display name.
    Matches against schema.STAGES, stripping pipeline prefixes.
    Falls back to best-effort match for column names that diverge
    from internal names (e.g. 'sdr_prequalified' → 'pre_qualified')."""
    for internal in schema.STAGES:
        if stage_key == internal or stage_key.endswith("_" + internal):
            return schema.stage_short(internal)
    stripped = stage_key
    for prefix in _PIPELINE_PREFIXES:
        if stripped.startswith(prefix):
            stripped = stripped[len(prefix):]
            break
    normalized = stripped.replace("_", "")
    for internal in schema.STAGES:
        if internal.replace("_", "") == normalized:
            return schema.stage_short(internal)
    return stripped.replace("_", " ").title()


def _parse_json_field(val):
    if isinstance(val, str):
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return val
    return val


# ═══════════════════════════════════════════════════════════════════════════
# STATISTICAL PATTERNS (pure Python, zero Claude)
# ═══════════════════════════════════════════════════════════════════════════

def _fetch_all_trajectories() -> list[dict]:
    results = []
    offset = 0
    while True:
        resp = (
            supabase.table(_TBL_TRAJECTORIES)
            .select(_TRAJ_SELECT)
            .order("created_at", desc=True)
            .range(offset, offset + 999)
            .execute()
        )
        batch = resp.data or []
        results.extend(batch)
        if len(batch) < 1000:
            break
        offset += 1000
    return results


def _compute_temporal_patterns(trajectories: list[dict]) -> list[dict]:
    patterns = []
    close_days = []
    quarter_end_closes = 0
    total_with_date = 0

    for t in trajectories:
        if t[_TC["outcome"]] not in ("won", "lost"):
            continue
        cd = t.get(_TC["close_date"])
        if not cd:
            continue
        try:
            d = date.fromisoformat(str(cd)[:10])
            close_days.append(d.day)
            total_with_date += 1
            if d.month in (3, 6, 9, 12) and d.day >= 20:
                quarter_end_closes += 1
        except (ValueError, TypeError):
            continue

    if not close_days:
        return []

    last_5_days = sum(1 for d in close_days if d >= 26)
    pct_last_5 = round(last_5_days / len(close_days) * 100)

    patterns.append({
        _P_KEY: "temporal_month_end_close_rate",
        _P_TYPE: "forecast",
        _P_SCOPE: "all",
        _P_PATTERN: f"El {pct_last_5}% de los deals cierran en los últimos 5 días del mes (día 26+). "
                    f"Basado en {len(close_days)} deals cerrados.",
        _P_CONFIDENCE: min(0.95, len(close_days) / 100),
        _P_SAMPLE: len(close_days),
        _P_VALUE: pct_last_5,
    })

    if total_with_date >= 20:
        pct_quarter = round(quarter_end_closes / total_with_date * 100)
        patterns.append({
            _P_KEY: "temporal_quarter_end_close_rate",
            _P_TYPE: "forecast",
            _P_SCOPE: "all",
            _P_PATTERN: f"El {pct_quarter}% de los deals cierran en las últimas 2 semanas del quarter "
                        f"(meses 3,6,9,12 día 20+). Basado en {total_with_date} deals.",
            _P_CONFIDENCE: min(0.90, total_with_date / 100),
            _P_SAMPLE: total_with_date,
            _P_VALUE: pct_quarter,
        })

    return patterns


def _compute_stage_velocity(trajectories: list[dict]) -> list[dict]:
    patterns = []
    stage_durations: dict[str, list[int]] = defaultdict(list)

    for t in trajectories:
        stage_dates = _parse_json_field(t.get(_TC["stage_dates"]) or {})
        if not isinstance(stage_dates, dict):
            continue
        for stage_key, dates in stage_dates.items():
            if not isinstance(dates, dict):
                continue
            entered = dates.get("entered")
            exited = dates.get("exited")
            if entered and exited:
                try:
                    d1 = date.fromisoformat(str(entered)[:10])
                    d2 = date.fromisoformat(str(exited)[:10])
                    days = (d2 - d1).days
                    if 0 < days < 365:
                        stage_durations[stage_key].append(days)
                except (ValueError, TypeError):
                    continue

    for stage_key, durations in stage_durations.items():
        if len(durations) < 5:
            continue
        avg = round(sum(durations) / len(durations))
        stage_name = _stage_display_name(stage_key)
        patterns.append({
            _P_KEY: f"stage_velocity_{stage_key}",
            _P_TYPE: "forecast",
            _P_SCOPE: "all",
            _P_PATTERN: f"Los deals pasan de media {avg} días en {stage_name}. "
                        f"Basado en {len(durations)} deals. "
                        f"Rango: {min(durations)}-{max(durations)} días.",
            _P_CONFIDENCE: min(0.90, len(durations) / 50),
            _P_SAMPLE: len(durations),
            _P_VALUE: avg,
        })

    return patterns


def _compute_size_patterns(trajectories: list[dict]) -> list[dict]:
    patterns = []

    for mrr_range in MRR_RANGES:
        deals_in_range = [
            t for t in trajectories
            if t[_TC["outcome"]] in ("won", "lost")
            and t.get(_TC["amount"]) is not None
            and mrr_range["min"] <= float(t.get(_TC["amount"]) or 0) < mrr_range["max"]
        ]
        if len(deals_in_range) < 5:
            continue

        won = [t for t in deals_in_range if t[_TC["outcome"]] == "won"]
        ages = [t[_TC["deal_age_days"]] for t in deals_in_range if t.get(_TC["deal_age_days"])]
        won_ages = [t[_TC["deal_age_days"]] for t in won if t.get(_TC["deal_age_days"])]
        win_rate = round(len(won) / len(deals_in_range) * 100) if deals_in_range else 0

        avg_age = round(sum(ages) / len(ages)) if ages else 0
        avg_won_age = round(sum(won_ages) / len(won_ages)) if won_ages else 0
        label = mrr_range["label"]

        patterns.append({
            _P_KEY: f"size_close_time_{label.replace('€', '').replace('<', 'lt').replace('>', 'gt').replace('-', '_')}",
            _P_TYPE: "forecast",
            _P_SCOPE: "all",
            _P_PATTERN: f"Deals de {label} MRR: win rate {win_rate}%, "
                        f"ciclo medio de cierre {avg_won_age} días (ganados), "
                        f"{avg_age} días (todos). "
                        f"Basado en {len(deals_in_range)} deals ({len(won)} won).",
            _P_CONFIDENCE: min(0.85, len(deals_in_range) / 30),
            _P_SAMPLE: len(deals_in_range),
            _P_VALUE: win_rate,
        })

    return patterns


def _compute_team_patterns(trajectories: list[dict]) -> list[dict]:
    patterns = []
    by_team: dict[str, list[dict]] = defaultdict(list)

    for t in trajectories:
        team = t.get(_TC["team"]) or ""
        if team:
            by_team[team].append(t)

    for team, deals in by_team.items():
        if len(deals) < 5:
            continue

        won = sum(1 for d in deals if d[_TC["outcome"]] == "won")
        lost = sum(1 for d in deals if d[_TC["outcome"]] == "lost")
        total = won + lost
        if total == 0:
            continue
        win_rate = round(won / total * 100)

        loss_reasons: dict[str, int] = defaultdict(int)
        for d in deals:
            if d[_TC["outcome"]] == "lost":
                reason = d.get(_TC["closed_lost_reason"]) or "Unknown"
                loss_reasons[reason] += 1
        top_reasons = sorted(loss_reasons.items(), key=lambda x: -x[1])[:3]
        reasons_text = ", ".join(f"{r}: {c}" for r, c in top_reasons) if top_reasons else "N/A"

        patterns.append({
            _P_KEY: f"win_rate_{team.lower().replace(' ', '_')}",
            _P_TYPE: "forecast",
            _P_SCOPE: team.lower(),
            _P_PATTERN: f"{team}: win rate {win_rate}% ({won} won, {lost} lost de {total} cerrados). "
                        f"Top razones de pérdida: {reasons_text}.",
            _P_CONFIDENCE: min(0.90, total / 30),
            _P_SAMPLE: total,
            _P_VALUE: win_rate,
        })

    return patterns


def _compute_stage_conversion(trajectories: list[dict]) -> list[dict]:
    """For each stage, what % of deals that reached it ended up won vs lost,
    and how many days from that stage to close (won only)."""
    patterns = []
    stage_outcomes: dict[str, dict] = defaultdict(lambda: {"won": 0, "lost": 0, "days_to_close": []})

    for t in trajectories:
        outcome = t[_TC["outcome"]]
        if outcome not in ("won", "lost"):
            continue
        stage_dates = _parse_json_field(t.get(_TC["stage_dates"]) or {})
        if not isinstance(stage_dates, dict):
            continue
        close_date_str = t.get(_TC["close_date"])

        for stage_key, dates in stage_dates.items():
            if not isinstance(dates, dict):
                continue
            entered = dates.get("entered")
            if not entered:
                continue
            stage_outcomes[stage_key][outcome] += 1

            if outcome == "won" and close_date_str and entered:
                try:
                    d_entered = date.fromisoformat(str(entered)[:10])
                    d_close = date.fromisoformat(str(close_date_str)[:10])
                    days = (d_close - d_entered).days
                    if 0 < days < 365:
                        stage_outcomes[stage_key]["days_to_close"].append(days)
                except (ValueError, TypeError):
                    pass

    for stage_key, data in stage_outcomes.items():
        total = data["won"] + data["lost"]
        if total < 10:
            continue
        conversion = round(data["won"] / total * 100)
        stage_name = _stage_display_name(stage_key)

        text = (
            f"De los deals que llegan a {stage_name}, el {conversion}% cierra won "
            f"({data['won']} won, {data['lost']} lost de {total})."
        )
        days_list = data["days_to_close"]
        if len(days_list) >= 3:
            avg_days = round(sum(days_list) / len(days_list))
            text += f" Tiempo medio desde {stage_name} hasta cierre: {avg_days} días."

        patterns.append({
            _P_KEY: f"stage_conversion_{stage_key}",
            _P_TYPE: "forecast",
            _P_SCOPE: "all",
            _P_PATTERN: text,
            _P_CONFIDENCE: min(0.90, total / 40),
            _P_SAMPLE: total,
            _P_VALUE: conversion,
        })

    return patterns


def _compute_pipeline_patterns(trajectories: list[dict]) -> list[dict]:
    """Win rate, cycle time, and top loss reasons per pipeline."""
    patterns = []
    by_pipeline: dict[str, list[dict]] = defaultdict(list)

    for t in trajectories:
        pipeline = t.get(_TC["pipeline_name"]) or ""
        if pipeline:
            by_pipeline[pipeline].append(t)

    for pipeline, deals in by_pipeline.items():
        won = [d for d in deals if d[_TC["outcome"]] == "won"]
        lost = [d for d in deals if d[_TC["outcome"]] == "lost"]
        total = len(won) + len(lost)
        if total < 5:
            continue
        win_rate = round(len(won) / total * 100)

        won_ages = [d[_TC["deal_age_days"]] for d in won if d.get(_TC["deal_age_days"])]
        avg_cycle = round(sum(won_ages) / len(won_ages)) if won_ages else 0

        loss_reasons: dict[str, int] = defaultdict(int)
        for d in lost:
            reason = d.get(_TC["closed_lost_reason"]) or "Unknown"
            loss_reasons[reason] += 1
        top_reasons = sorted(loss_reasons.items(), key=lambda x: -x[1])[:3]
        reasons_text = ", ".join(f"{r}: {c}" for r, c in top_reasons) if top_reasons else "N/A"

        pipeline_slug = pipeline.lower().replace(" ", "_")

        text = (
            f"{pipeline}: win rate {win_rate}% ({len(won)} won, {len(lost)} lost de {total})"
        )
        if avg_cycle:
            text += f", ciclo medio {avg_cycle} días (ganados)"
        text += f". Top razones de pérdida: {reasons_text}."

        patterns.append({
            _P_KEY: f"pipeline_{pipeline_slug}",
            _P_TYPE: "forecast",
            _P_SCOPE: pipeline_slug,
            _P_PATTERN: text,
            _P_CONFIDENCE: min(0.90, total / 30),
            _P_SAMPLE: total,
            _P_VALUE: win_rate,
        })

    return patterns


def generate_statistical_patterns(trajectories: list[dict]) -> list[dict]:
    patterns = []
    patterns.extend(_compute_temporal_patterns(trajectories))
    patterns.extend(_compute_stage_velocity(trajectories))
    patterns.extend(_compute_stage_conversion(trajectories))
    patterns.extend(_compute_size_patterns(trajectories))
    patterns.extend(_compute_team_patterns(trajectories))
    patterns.extend(_compute_pipeline_patterns(trajectories))
    return patterns


# ═══════════════════════════════════════════════════════════════════════════
# TEXT PATTERNS (Claude)
# ═══════════════════════════════════════════════════════════════════════════

def _fetch_existing_patterns() -> list[dict]:
    resp = (
        supabase.table(_TBL_PATTERNS)
        .select(_EXISTING_SELECT)
        .not_.is_(_P_KEY, "null")
        .order(_P_UPDATED, desc=True)
        .execute()
    )
    return resp.data or []


def generate_text_patterns(trajectories: list[dict], existing_patterns: list[dict]) -> list[dict]:
    all_lessons = []
    for t in trajectories:
        lessons = _parse_json_field(t.get(_TC["lessons"]) or [])
        if isinstance(lessons, list):
            all_lessons.extend(lessons)

    if len(all_lessons) < 10:
        print(f"    Only {len(all_lessons)} lessons — need at least 10")
        return []

    won = [t for t in trajectories if t[_TC["outcome"]] == "won"]
    lost = [t for t in trajectories if t[_TC["outcome"]] == "lost"]

    loss_reasons: dict[str, int] = defaultdict(int)
    for t in lost:
        r = t.get(_TC["closed_lost_reason"]) or "Unknown"
        loss_reasons[r] += 1

    existing_text = ""
    if existing_patterns:
        text_patterns = [
            p for p in existing_patterns
            if not p.get(_P_KEY, "").startswith(_STAT_PREFIXES)
        ]
        if text_patterns:
            existing_text = "\n## EXISTING PATTERNS (update these if data confirms or contradicts)\n"
            for p in text_patterns:
                existing_text += (
                    f"- [{p.get(_P_KEY)}] ({p.get(_P_CONFIDENCE, '?')} conf, "
                    f"{p.get(_P_SAMPLE, '?')} deals): {p.get(_P_PATTERN, '')}\n"
                )

    system_prompt = (PROMPTS_DIR / WEEKLY["patterns_prompt"]).read_text(encoding="utf-8").strip()
    user_prompt = (
        f"## BENCHMARK\n"
        f"{len(won)} deals ganados, {len(lost)} deals perdidos, {len(trajectories)} total.\n\n"
        f"## TOP RAZONES DE PÉRDIDA\n"
        + "\n".join(f"  {r}: {c} deals" for r, c in sorted(loss_reasons.items(), key=lambda x: -x[1])[:10])
        + f"\n\n## LECCIONES APRENDIDAS ({len(all_lessons)} total)\n"
        + "\n".join(f"• {l}" for l in all_lessons[:80])
        + f"\n\n{existing_text}"
    )

    print(f"    Claude ({len(user_prompt)} chars, {len(all_lessons)} lessons)...")
    try:
        raw = claude.analyze(
            system_prompt, user_prompt,
            model=MODEL_DEFAULT, max_tokens=MAX_TOKENS["patterns"],
        )
        text = re.sub(r"^```(?:json)?\s*", "", raw.strip())
        text = re.sub(r"\s*```$", "", text).strip()
        return json.loads(text)
    except Exception as e:
        print(f"    ✗ Claude failed: {e}")
        return []


# ═══════════════════════════════════════════════════════════════════════════
# UPSERT WITH HISTORY
# ═══════════════════════════════════════════════════════════════════════════

def _upsert_pattern(pattern: dict, today: str):
    key = pattern.get(_P_KEY)
    if not key:
        return

    existing_resp = (
        supabase.table(_TBL_PATTERNS)
        .select(_UPSERT_SELECT)
        .eq(_P_KEY, key)
        .maybe_single()
        .execute()
    )
    existing = existing_resp.data if existing_resp else None

    history = []
    if existing:
        old_history = _parse_json_field(existing.get(_P_HISTORY) or [])
        if isinstance(old_history, list):
            history = old_history
        history.append({
            "date": today,
            _P_CONFIDENCE: existing.get(_P_CONFIDENCE),
            _P_SAMPLE: existing.get(_P_SAMPLE),
            _P_VALUE: existing.get(_P_VALUE),
        })

    row = {
        _P_KEY: key,
        _P_TYPE: pattern.get(_P_TYPE) or "forecast",
        _P_SCOPE: pattern.get(_P_SCOPE) or "all",
        _P_PATTERN: pattern.get(_P_PATTERN) or "",
        _P_CONFIDENCE: pattern.get(_P_CONFIDENCE),
        _P_SAMPLE: pattern.get(_P_SAMPLE),
        _P_VALUE: pattern.get(_P_VALUE),
        _P_HISTORY: json.dumps(history[-52:], ensure_ascii=False),
        _P_UPDATED: "now()",
    }
    row = {k: v for k, v in row.items() if v is not None}

    if existing:
        supabase.table(_TBL_PATTERNS).update(row).eq(_P_ID, existing[_P_ID]).execute()
    else:
        row[_P_GENERATED] = "now()"
        supabase.table(_TBL_PATTERNS).insert(row).execute()


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def run() -> int:
    print("\n  PATTERNS: loading trajectories...")
    today = date.today().isoformat()

    trajectories = _fetch_all_trajectories()
    if len(trajectories) < MIN_TRAJECTORIES_FOR_PATTERNS:
        print(f"    Only {len(trajectories)} trajectories — need at least {MIN_TRAJECTORIES_FOR_PATTERNS}")
        return 0

    print(f"    {len(trajectories)} trajectories loaded")

    print("    Computing statistical patterns...")
    stat_patterns = generate_statistical_patterns(trajectories)
    print(f"    {len(stat_patterns)} statistical patterns")

    for p in stat_patterns:
        try:
            _upsert_pattern(p, today)
        except Exception as e:
            print(f"    ✗ Stat pattern upsert failed ({p.get(_P_KEY)}): {e}")

    print("    Generating text patterns...")
    existing = _fetch_existing_patterns()
    text_patterns = generate_text_patterns(trajectories, existing)
    print(f"    {len(text_patterns)} text patterns from Claude")

    for p in text_patterns:
        try:
            _upsert_pattern(p, today)
        except Exception as e:
            print(f"    ✗ Text pattern upsert failed ({p.get(_P_KEY)}): {e}")

    total = len(stat_patterns) + len(text_patterns)
    print(f"    {total} patterns upserted")
    return total
