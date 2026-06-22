"""
Google Calendar API client — read-only access to rep calendars.
Auth via OAuth2 refresh token (env vars).
"""

import os

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from src.config import GOOGLE_TOKEN_URI, GOOGLE_CALENDAR_SCOPE

_CLIENT_ID = os.environ.get("GCAL_CLIENT_ID", "")
_CLIENT_SECRET = os.environ.get("GCAL_CLIENT_SECRET", "")
_REFRESH_TOKEN = os.environ.get("GCAL_REFRESH_TOKEN", "")

_service = None


def _get_service():
    global _service
    if _service:
        return _service
    creds = Credentials(
        token=None,
        refresh_token=_REFRESH_TOKEN,
        token_uri=GOOGLE_TOKEN_URI,
        client_id=_CLIENT_ID,
        client_secret=_CLIENT_SECRET,
        scopes=[GOOGLE_CALENDAR_SCOPE],
    )
    _service = build("calendar", "v3", credentials=creds, cache_discovery=False)
    return _service


def fetch_events(calendar_id: str, time_min: str, time_max: str) -> list[dict]:
    """Fetch timed events (not all-day) from a calendar in the given window."""
    try:
        service = _get_service()
        result = service.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
            maxResults=50,
        ).execute()
    except Exception as e:
        print(f"    [gcal] {calendar_id}: {e}")
        return []

    events = []
    for ev in result.get("items", []):
        start = ev.get("start", {})
        if "dateTime" not in start:
            continue
        if ev.get("status") == "cancelled":
            continue

        attendees = []
        for a in ev.get("attendees", []):
            if a.get("responseStatus") == "declined":
                continue
            email = a.get("email", "")
            if email:
                attendees.append({
                    "email": email.lower(),
                    "name": a.get("displayName", ""),
                })

        events.append({
            "gcal_event_id": ev["id"],
            "title": ev.get("summary", ""),
            "meeting_start": start["dateTime"],
            "meeting_end": ev.get("end", {}).get("dateTime"),
            "attendees": attendees,
        })

    return events
