import os
import time

import requests

from src.config import (
    HUBSPOT_BASE_URL,
    HUBSPOT_MIN_REQUEST_INTERVAL,
    HUBSPOT_MAX_RETRIES,
    HUBSPOT_RETRYABLE_CODES,
)

_TOKEN = os.environ.get("HUBSPOT_TOKEN", "")
_HEADERS = {"Authorization": f"Bearer {_TOKEN}", "Content-Type": "application/json"}
_last_request_at = 0.0
_total_requests = 0


def _throttle():
    global _last_request_at
    elapsed = time.time() - _last_request_at
    if elapsed < HUBSPOT_MIN_REQUEST_INTERVAL:
        time.sleep(HUBSPOT_MIN_REQUEST_INTERVAL - elapsed)
    _last_request_at = time.time()


def get(path: str, params: dict | None = None) -> dict:
    global _total_requests
    url = f"{HUBSPOT_BASE_URL}{path}" if path.startswith("/") else path
    for attempt in range(HUBSPOT_MAX_RETRIES):
        _throttle()
        _total_requests += 1
        resp = requests.get(url, headers=_HEADERS, params=params, timeout=30)
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code in HUBSPOT_RETRYABLE_CODES:
            wait = 2 ** attempt
            time.sleep(wait)
            continue
        resp.raise_for_status()
    resp.raise_for_status()


def post(path: str, body: dict) -> dict:
    global _total_requests
    url = f"{HUBSPOT_BASE_URL}{path}" if path.startswith("/") else path
    for attempt in range(HUBSPOT_MAX_RETRIES):
        _throttle()
        _total_requests += 1
        resp = requests.post(url, headers=_HEADERS, json=body, timeout=30)
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code in HUBSPOT_RETRYABLE_CODES:
            wait = 2 ** attempt
            time.sleep(wait)
            continue
        resp.raise_for_status()
    resp.raise_for_status()


def total_requests() -> int:
    return _total_requests


def reset_counter():
    global _total_requests
    _total_requests = 0
