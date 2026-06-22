"""
Modjo API client — fetch call details and build transcripts.

Used by intelligence.py to resolve Modjo links found in HubSpot meetings/calls.
"""

import os
import time

import requests

from src.config import (
    MODJO_BASE_URL,
    ALL_REP_EMAILS,
    ALL_PAE_EMAILS,
    PBD_TAGS,
    PAE_TAGS,
    get_role,
    get_subteam,
)


def _headers() -> dict:
    return {
        "X-API-KEY": os.environ["MODJO_API_KEY"],
        "Content-Type": "application/json",
    }


def _post(payload: dict, timeout: int = 60) -> dict:
    for _ in range(5):
        r = requests.post(
            f"{MODJO_BASE_URL}/calls/exports",
            headers=_headers(),
            json=payload,
            timeout=timeout,
        )
        if r.status_code == 429:
            print("    [modjo rate limit] Waiting 310s...")
            time.sleep(310)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError("Modjo API: max retries exceeded")


def fetch_call_details(call_ids: list[int]) -> list[dict]:
    """Fetch full call data (transcript, tags, users) by Modjo call ID."""
    all_calls: list[dict] = []
    for i in range(0, len(call_ids), 50):
        batch = call_ids[i:i + 50]
        payload = {
            "pagination": {"page": 1, "perPage": len(batch)},
            "filters": {"callIds": batch},
            "relations": {
                "transcript": True,
                "users": True,
                "tags": True,
            },
        }
        try:
            calls = _post(payload).get("values", [])
            all_calls.extend(calls)
        except Exception as e:
            print(f"    [modjo] Batch fetch failed: {e}")
    return all_calls


def build_transcript(lines: list[dict]) -> str:
    """Format Modjo transcript lines into readable text."""
    parts = []
    for t in lines:
        try:
            start = t.get("startTime") or 0
            content = t.get("content", "")
            parts.append(f"[{int(start // 60):02d}:{int(start) % 60:02d}] {content}")
        except Exception:
            continue
    return "\n".join(parts)


def normalize(raw: dict, fallback_email: str = "", fallback_name: str = "") -> dict | None:
    """Normalize a raw Modjo call into a dict ready for the calls table.
    Returns None if no valid transcript or owner found."""

    rels = raw.get("relations") or {}
    users = rels.get("users", [])
    transcript_lines = rels.get("transcript", [])
    tags = [t["name"] for t in rels.get("tags", [])]

    transcript = build_transcript(transcript_lines)
    if len(transcript.strip()) < 100:
        return None

    speaker_counts: dict[str, int] = {}
    for line in transcript_lines:
        speaker = line.get("userName") or line.get("speaker", "")
        if speaker:
            speaker_counts[speaker] = speaker_counts.get(speaker, 0) + 1

    owner, role = _resolve_owner(users, tags, speaker_counts)

    if owner is None and fallback_email:
        owner = {"email": fallback_email, "name": fallback_name}
        role = get_role(fallback_email, tags)

    if owner is None:
        return None

    owner_email = owner.get("email", "")

    return {
        "call_id": str(raw["callId"]),
        "titulo": raw.get("title", ""),
        "fecha": raw.get("startDate"),
        "duracion_segundos": int(raw.get("duration", 0)),
        "owner_email": owner_email,
        "owner_nombre": owner.get("name", ""),
        "rol": role or "PAE",
        "tags": tags,
        "team": "Partners",
        "crm_id": "",
        "hs_deal_id": "",
        "transcript": transcript,
        "subteam": get_subteam(owner_email) if owner_email else None,
        "source": "modjo",
    }


def _resolve_owner(
    users: list[dict], tags: list[str], speaker_counts: dict[str, int]
) -> tuple[dict | None, str | None]:
    reps = [u for u in users if u.get("email", "") in ALL_REP_EMAILS]

    if reps:
        has_pae_tag = any(t in PAE_TAGS for t in tags)
        has_pbd_tag = any(t in PBD_TAGS for t in tags)

        if has_pae_tag:
            pae_rep = next((u for u in reps if u["email"] in ALL_PAE_EMAILS), None)
            if pae_rep:
                return pae_rep, "PAE"

        owner = next((u for u in reps if u.get("isOwner")), None)
        if owner is None:
            owner = max(reps, key=lambda u: speaker_counts.get(u.get("name", ""), 0))

        role = get_role(owner["email"], tags)
        if role is None:
            role = "PBD" if has_pbd_tag else ("PAE" if has_pae_tag else "PBD")
        return owner, role

    return None, None
