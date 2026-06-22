"""
Weekly Patterns — generates and updates learned_patterns.

Two types:
  1. Text patterns (Claude) — generalizations from deal lessons
  2. Statistical patterns (Python) — calculated from trajectory numbers

Patterns accumulate — never deleted. Updated via upsert by pattern_key.
History tracked in JSONB column.
Everything from config.
"""

import json
import re
from datetime import date
from collections import defaultdict

from src.config import (
    WEEKLY_CONFIG,
    PROMPTS_DIR,
    MODEL_DEFAULT,
    MAX_TOKENS_PATTERNS,
)
from src.db.client import supabase
from src.integrations import claude

_W = WEEKLY_CONFIG
TODAY = date.today().isoformat()


# ═══════════════════════════════════════════════════════════════════════════
# STATISTICAL PATTERNS (pure Python, zero Claude)
# ═══════════════════════════════════════════════════════════════════════════

def _fetch_all_trajectories() -> list[dict]:
    resp = (
        supabase.table(_W["trajectories_table"])
        .select("outcome, amount, deal_age_days, team, closed_lost_reason, close_date, trajectory, stage_dates, lessons")
        .order("created_at", desc=True)
        .limit(500)
        .execute()
    )
    return resp.data or []


def _parse_json_field(val) -> any:
    if isinstance(val, str):
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return val
    return val


def _compute_temporal_patterns(trajectories: list[dict]) -> list[dict]:
    """Calculate when deals close within the month."""
    patterns = []
    close_days = []
    quarter_end_closes = 0
    total_with_date = 0

    for t in trajectories:
        if t["outcome"] not in ("won", "lost"):
            continue
        cd = t.get("close_date")
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
        "pattern_key": "temporal_month_end_close_rate",
        "pattern_type": "forecast",
        "scope": "all",
        "pattern": f"El {pct_last_5}% de los deals cierran en los últimos 5 días del mes (día 26+). "
                   f"Basado en {len(close_days)} deals cerrados.",
        "confidence": min(0.95, len(close_days) / 100),
        "sample_size": len(close_days),
        "value": pct_last_5,
    })

    if total_with_date >= 20:
        pct_quarter = round(quarter_end_closes / total_with_date * 100)
        patterns.append({
            "pattern_key": "temporal_quarter_end_close_rate",
            "pattern_type": "forecast",
            "scope": "all",
            "pattern": f"El {pct_quarter}% de los deals cierran en las últimas 2 semanas del quarter "
                       f"(meses 3,6,9,12 día 20+). Basado en {total_with_date} deals.",
            "confidence": min(0.90, total_with_date / 100),
            "sample_size": total_with_date,
            "value": pct_quarter,
        })

    return patterns


def _compute_stage_velocity(trajectories: list[dict]) -> list[dict]:
    """Calculate average days per stage."""
    patterns = []
    stage_durations: dict[str, list[int]] = defaultdict(list)

    for t in trajectories:
        stage_dates = _parse_json_field(t.get("stage_dates") or {})
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
        stage_name = stage_key.replace("dist_", "").replace("sdr_", "").replace("sales_", "").replace("_", " ").title()
        patterns.append({
            "pattern_key": f"stage_velocity_{stage_key}",
            "pattern_type": "forecast",
            "scope": "all",
            "pattern": f"Los deals pasan de media {avg} días en {stage_name}. "
                       f"Basado en {len(durations)} deals. "
                       f"Rango: {min(durations)}-{max(durations)} días.",
            "confidence": min(0.90, len(durations) / 50),
            "sample_size": len(durations),
            "value": avg,
        })

    return patterns


def _compute_size_patterns(trajectories: list[dict]) -> list[dict]:
    """Calculate close time by MRR range."""
    patterns = []

    for mrr_range in _W["mrr_ranges"]:
        deals_in_range = [
            t for t in trajectories
            if t["outcome"] in ("won", "lost")
            and t.get("amount") is not None
            and mrr_range["min"] <= float(t.get("amount") or 0) < mrr_range["max"]
        ]
        if len(deals_in_range) < 5:
            continue

        won = [t for t in deals_in_range if t["outcome"] == "won"]
        ages = [t["deal_age_days"] for t in deals_in_range if t.get("deal_age_days")]
        won_ages = [t["deal_age_days"] for t in won if t.get("deal_age_days")]
        win_rate = round(len(won) / len(deals_in_range) * 100) if deals_in_range else 0

        avg_age = round(sum(ages) / len(ages)) if ages else 0
        avg_won_age = round(sum(won_ages) / len(won_ages)) if won_ages else 0
        label = mrr_range["label"]

        patterns.append({
            "pattern_key": f"size_close_time_{label.replace('€', '').replace('<', 'lt').replace('>', 'gt').replace('-', '_')}",
            "pattern_type": "forecast",
            "scope": "all",
            "pattern": f"Deals de {label} MRR: win rate {win_rate}%, "
                       f"ciclo medio de cierre {avg_won_age} días (ganados), "
                       f"{avg_age} días (todos). "
                       f"Basado en {len(deals_in_range)} deals ({len(won)} won).",
            "confidence": min(0.85, len(deals_in_range) / 30),
            "sample_size": len(deals_in_range),
            "value": win_rate,
        })

    return patterns


def _compute_team_patterns(trajectories: list[dict]) -> list[dict]:
    """Win rate and loss reasons by team."""
    patterns = []
    by_team: dict[str, list[dict]] = defaultdict(list)

    for t in trajectories:
        team = t.get("team") or ""
        if team:
            by_team[team].append(t)

    for team, deals in by_team.items():
        if len(deals) < 5:
            continue

        won = sum(1 for d in deals if d["outcome"] == "won")
        lost = sum(1 for d in deals if d["outcome"] == "lost")
        total = won + lost
        if total == 0:
            continue
        win_rate = round(won / total * 100)

        loss_reasons: dict[str, int] = defaultdict(int)
        for d in deals:
            if d["outcome"] == "lost":
                reason = d.get("closed_lost_reason") or "Unknown"
                loss_reasons[reason] += 1
        top_reasons = sorted(loss_reasons.items(), key=lambda x: -x[1])[:3]
        reasons_text = ", ".join(f"{r}: {c}" for r, c in top_reasons) if top_reasons else "N/A"

        patterns.append({
            "pattern_key": f"win_rate_{team.lower().replace(' ', '_')}",
            "pattern_type": "forecast",
            "scope": team.lower(),
            "pattern": f"{team}: win rate {win_rate}% ({won} won, {lost} lost de {total} cerrados). "
                       f"Top razones de pérdida: {reasons_text}.",
            "confidence": min(0.90, total / 30),
            "sample_size": total,
            "value": win_rate,
        })

    return patterns


def generate_statistical_patterns(trajectories: list[dict]) -> list[dict]:
    """Generate all statistical patterns from trajectory data."""
    patterns = []
    patterns.extend(_compute_temporal_patterns(trajectories))
    patterns.extend(_compute_stage_velocity(trajectories))
    patterns.extend(_compute_size_patterns(trajectories))
    patterns.extend(_compute_team_patterns(trajectories))
    return patterns


# ═══════════════════════════════════════════════════════════════════════════
# TEXT PATTERNS (Claude)
# ═══════════════════════════════════════════════════════════════════════════

def _fetch_existing_patterns() -> list[dict]:
    resp = (
        supabase.table(_W["patterns_table"])
        .select("pattern_key, pattern_type, scope, pattern, confidence, sample_size")
        .not_.is_("pattern_key", "null")
        .order("updated_at", desc=True)
        .execute()
    )
    return resp.data or []


def generate_text_patterns(trajectories: list[dict], existing_patterns: list[dict]) -> list[dict]:
    """Use Claude to generate/update text patterns from lessons."""
    all_lessons = []
    for t in trajectories:
        lessons = _parse_json_field(t.get("lessons") or [])
        if isinstance(lessons, list):
            all_lessons.extend(lessons)

    if len(all_lessons) < 10:
        print(f"    Only {len(all_lessons)} lessons — need at least 10")
        return []

    won = [t for t in trajectories if t["outcome"] == "won"]
    lost = [t for t in trajectories if t["outcome"] == "lost"]

    loss_reasons: dict[str, int] = defaultdict(int)
    for t in lost:
        r = t.get("closed_lost_reason") or "Unknown"
        loss_reasons[r] += 1

    existing_text = ""
    if existing_patterns:
        text_patterns = [p for p in existing_patterns if not p.get("pattern_key", "").startswith(("temporal_", "stage_velocity_", "size_close_", "win_rate_"))]
        if text_patterns:
            existing_text = "\n## EXISTING PATTERNS (update these if data confirms or contradicts)\n"
            for p in text_patterns:
                existing_text += f"- [{p.get('pattern_key')}] ({p.get('confidence', '?')} conf, {p.get('sample_size', '?')} deals): {p.get('pattern', '')}\n"

    system_prompt = (PROMPTS_DIR / _W["patterns_prompt_path"]).read_text(encoding="utf-8").strip()
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
        raw = claude.analyze(system_prompt, user_prompt, model=MODEL_DEFAULT, max_tokens=MAX_TOKENS_PATTERNS)
        text = re.sub(r"^```(?:json)?\s*", "", raw.strip())
        text = re.sub(r"\s*```$", "", text).strip()
        return json.loads(text)
    except Exception as e:
        print(f"    ✗ Claude failed: {e}")
        return []


# ═══════════════════════════════════════════════════════════════════════════
# UPSERT WITH HISTORY
# ═══════════════════════════════════════════════════════════════════════════

def _upsert_pattern(pattern: dict):
    """Upsert a pattern, preserving history."""
    key = pattern.get("pattern_key")
    if not key:
        return

    existing_resp = (
        supabase.table(_W["patterns_table"])
        .select("id, history, confidence, sample_size, value")
        .eq("pattern_key", key)
        .maybe_single()
        .execute()
    )

    history = []
    if existing_resp.data:
        old_history = _parse_json_field(existing_resp.data.get("history") or [])
        if isinstance(old_history, list):
            history = old_history
        history.append({
            "date": TODAY,
            "confidence": existing_resp.data.get("confidence"),
            "sample_size": existing_resp.data.get("sample_size"),
            "value": existing_resp.data.get("value"),
        })

    row = {
        "pattern_key": key,
        "pattern_type": pattern.get("pattern_type") or "forecast",
        "scope": pattern.get("scope") or "all",
        "pattern": pattern.get("pattern") or "",
        "confidence": pattern.get("confidence"),
        "sample_size": pattern.get("sample_size"),
        "value": pattern.get("value"),
        "history": json.dumps(history[-52:], ensure_ascii=False),  # keep last 52 weeks
        "updated_at": "now()",
    }
    row = {k: v for k, v in row.items() if v is not None}

    if existing_resp.data:
        supabase.table(_W["patterns_table"]).update(row).eq("id", existing_resp.data["id"]).execute()
    else:
        row["generated_at"] = "now()"
        supabase.table(_W["patterns_table"]).insert(row).execute()


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def run() -> int:
    """Generate/update all patterns: statistical + text."""
    print("\n  PATTERNS: loading trajectories...")

    trajectories = _fetch_all_trajectories()
    if len(trajectories) < _W["min_trajectories"]:
        print(f"    Only {len(trajectories)} trajectories — need at least {_W['min_trajectories']}")
        return 0

    print(f"    {len(trajectories)} trajectories loaded")

    # Statistical patterns (Python, zero Claude)
    print("    Computing statistical patterns...")
    stat_patterns = generate_statistical_patterns(trajectories)
    print(f"    {len(stat_patterns)} statistical patterns")

    for p in stat_patterns:
        try:
            _upsert_pattern(p)
        except Exception as e:
            print(f"    ✗ Stat pattern upsert failed ({p.get('pattern_key')}): {e}")

    # Text patterns (Claude)
    print("    Generating text patterns...")
    existing = _fetch_existing_patterns()
    text_patterns = generate_text_patterns(trajectories, existing)
    print(f"    {len(text_patterns)} text patterns from Claude")

    for p in text_patterns:
        try:
            _upsert_pattern(p)
        except Exception as e:
            print(f"    ✗ Text pattern upsert failed ({p.get('pattern_key')}): {e}")

    total = len(stat_patterns) + len(text_patterns)
    print(f"    {total} patterns upserted")
    return total
