"""Google Photos Library API client.

Uses OAuth refresh token stored in env. Lists screenshots created in the
lookback window and downloads them locally for AI processing.
"""
from __future__ import annotations

import os
import pathlib
from datetime import datetime, timedelta, timezone
from typing import Iterator

import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/photoslibrary.readonly"]
API_BASE = "https://photoslibrary.googleapis.com/v1"


def load_credentials() -> Credentials:
    creds = Credentials(
        token=None,
        refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return creds


def _date_filter(lookback_days: int) -> dict:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=lookback_days)
    return {
        "dateFilter": {
            "ranges": [
                {
                    "startDate": {"year": start.year, "month": start.month, "day": start.day},
                    "endDate": {"year": end.year, "month": end.month, "day": end.day},
                }
            ]
        },
        "contentFilter": {"includedContentCategories": ["SCREENSHOTS"]},
    }


def list_recent_screenshots(creds: Credentials, lookback_days: int) -> Iterator[dict]:
    headers = {"Authorization": f"Bearer {creds.token}"}
    body = {"pageSize": 100, "filters": _date_filter(lookback_days)}
    page_token: str | None = None
    while True:
        if page_token:
            body["pageToken"] = page_token
        r = requests.post(f"{API_BASE}/mediaItems:search", headers=headers, json=body, timeout=30)
        r.raise_for_status()
        payload = r.json()
        for item in payload.get("mediaItems", []):
            yield item
        page_token = payload.get("nextPageToken")
        if not page_token:
            return


def download_item(item: dict, dest_dir: pathlib.Path) -> pathlib.Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    url = f"{item['baseUrl']}=d"
    path = dest_dir / f"{item['id']}.jpg"
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(path, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                f.write(chunk)
    return path
