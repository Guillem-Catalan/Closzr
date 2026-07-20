"""
Modjo API client — fetch call details and build transcripts.

Used by intelligence.py to resolve Modjo links found in HubSpot meetings/calls.
"""

import os
import time

import requests

from src.config2 import (
    ALL_REP_EMAILS,
    ALL_PAE_EMAILS,
    MIN_TRANSCRIPT_LENGTH,
    MODJO_MAX_RETRIES,
    MODJO_RATE_LIMIT_WAIT,
    MODJO_REQUEST_TIMEOUT,
    get_role,
)
from src.org import (
    API_ENDPOINTS,
    CALL_TAGS_PBD,
    CALL_TAGS_PAE,
    MODJO_BATCH_SIZE,
    MODJO_FIELD_MAP,
)
from src.schema import CALL_COLS

_F = MODJO_FIELD_MAP
_C = CALL_COLS


def _headers() -> dict:
    return {
        _F["auth_header"]: os.environ["MODJO_API_KEY"],
        "Content-Type": "application/json",
    }


def _post(payload: dict, timeout: int = MODJO_REQUEST_TIMEOUT) -> dict:
    for _ in range(MODJO_MAX_RETRIES):
        r = requests.post(
            f"{API_ENDPOINTS['modjo']}{_F['endpoint']}",
            headers=_headers(),
            json=payload,
            timeout=timeout,
        )
        if r.status_code == 429:
            print(f"    [modjo rate limit] Waiting {MODJO_RATE_LIMIT_WAIT}s...")
            time.sleep(MODJO_RATE_LIMIT_WAIT)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError("Modjo API: max retries exceeded")


def fetch_call_details(call_ids: list[int]) -> list[dict]:
    """Fetch full call data (transcript, tags, users) by Modjo call ID."""
    all_calls: list[dict] = []
    for i in range(0, len(call_ids), MODJO_BATCH_SIZE):
        batch = call_ids[i:i + MODJO_BATCH_SIZE]
        payload = {
            _F["req_pagination"]: {_F["req_page"]: 1, _F["req_per_page"]: len(batch)},
            _F["req_filters"]: {_F["req_call_ids"]: batch},
            _F["req_relations"]: {
                _F["transcript_lines"]: True,
                _F["users"]: True,
                _F["tags"]: True,
            },
        }
        try:
            calls = _post(payload).get(_F["response_key"], [])
            all_calls.extend(calls)
        except Exception as e:
            print(f"    [modjo] Batch fetch failed: {e}")
    return all_calls


def build_transcript(lines: list[dict]) -> str:
    """Format Modjo transcript lines into readable text."""
    parts = []
    for t in lines:
        try:
            start = t.get(_F["start_time"]) or 0
            content = t.get(_F["content"], "")
            parts.append(f"[{int(start // 60):02d}:{int(start) % 60:02d}] {content}")
        except Exception:
            continue
    return "\n".join(parts)


def normalize(raw: dict, fallback_email: str = "", fallback_name: str = "") -> dict | None:
    """Normalize a raw Modjo call into a dict ready for the calls table.
    Returns None if no valid transcript or owner found."""

    rels = raw.get(_F["relations"]) or {}
    users = rels.get(_F["users"], [])
    transcript_lines = rels.get(_F["transcript_lines"], [])
    tags = [t[_F["tag_name"]] for t in rels.get(_F["tags"], [])]

    transcript = build_transcript(transcript_lines)
    if len(transcript.strip()) < MIN_TRANSCRIPT_LENGTH:
        return None

    speaker_counts: dict[str, int] = {}
    for line in transcript_lines:
        speaker = line.get(_F["speaker_name"]) or line.get(_F["speaker_fallback"], "")
        if speaker:
            speaker_counts[speaker] = speaker_counts.get(speaker, 0) + 1

    owner, role = _resolve_owner(users, tags, speaker_counts)

    if owner is None and fallback_email:
        owner = {_F["user_email"]: fallback_email, _F["user_name"]: fallback_name}
        role = get_role(fallback_email, tags)

    if owner is None:
        return None

    owner_email = owner.get(_F["user_email"], "")

    return {
        _C["call_id"]: str(raw[_F["call_id"]]),
        _C["titulo"]: raw.get(_F["titulo"], ""),
        _C["fecha"]: raw.get(_F["fecha"]),
        _C["duracion"]: int(raw.get(_F["duracion"], 0)),
        _C["owner_email"]: owner_email,
        _C["owner_nombre"]: owner.get(_F["user_name"], ""),
        _C["rol"]: "PAE" if role in ("AE", "PAE", None) else role,
        _C["tags"]: tags,
        _C["transcript"]: transcript,
        _C["source"]: "modjo",
    }


def _resolve_owner(
    users: list[dict], tags: list[str], speaker_counts: dict[str, int]
) -> tuple[dict | None, str | None]:
    reps = [u for u in users if u.get(_F["user_email"], "") in ALL_REP_EMAILS]

    if reps:
        has_pae_tag = any(t in CALL_TAGS_PAE for t in tags)
        has_pbd_tag = any(t in CALL_TAGS_PBD for t in tags)

        if has_pae_tag:
            pae_rep = next((u for u in reps if u[_F["user_email"]] in ALL_PAE_EMAILS), None)
            if pae_rep:
                return pae_rep, "PAE"

        owner = next((u for u in reps if u.get(_F["is_owner"])), None)
        if owner is None:
            owner = max(reps, key=lambda u: speaker_counts.get(u.get(_F["user_name"], ""), 0))

        role = get_role(owner[_F["user_email"]], tags)
        if role is None:
            role = "PBD" if has_pbd_tag else ("PAE" if has_pae_tag else "PBD")
        return owner, role

    return None, None
