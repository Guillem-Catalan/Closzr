"""
Google Calendar API client — read-only access to rep calendars.
Auth via OAuth2 refresh token (env vars).
"""

import os

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from src.config2 import GCAL_MAX_RESULTS
from src.org import API_ENDPOINTS, GCAL_FIELD_MAP
from src.schema import GCAL_EVENT_COLS, GCAL_ATTENDEE_COLS

_F = GCAL_FIELD_MAP
_C = GCAL_EVENT_COLS
_A = GCAL_ATTENDEE_COLS

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
        token_uri=API_ENDPOINTS["google_token"],
        client_id=_CLIENT_ID,
        client_secret=_CLIENT_SECRET,
        scopes=[API_ENDPOINTS["google_calendar_scope"]],
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
            orderBy=_F["order_by"],
            maxResults=GCAL_MAX_RESULTS,
        ).execute()
    except Exception as e:
        print(f"    [gcal] {calendar_id}: {e}")
        return []

    events = []
    for ev in result.get(_F["response_key"], []):
        start = ev.get(_F["event_start"], {})
        if _F["event_datetime"] not in start:
            continue
        if ev.get(_F["event_status"]) == _F["status_cancelled"]:
            continue

        attendees = []
        for a in ev.get(_F["event_attendees"], []):
            if a.get(_F["attendee_rsvp"]) == _F["rsvp_declined"]:
                continue
            email = a.get(_F["attendee_email"], "")
            if email:
                attendees.append({
                    _A["email"]: email.lower(),
                    _A["name"]: a.get(_F["attendee_name"], ""),
                })

        events.append({
            _C["gcal_event_id"]: ev[_F["event_id"]],
            _C["title"]: ev.get(_F["event_title"], ""),
            _C["meeting_start"]: start[_F["event_datetime"]],
            _C["meeting_end"]: ev.get(_F["event_end"], {}).get(_F["event_datetime"]),
            _C["attendees"]: attendees,
        })

    return events
