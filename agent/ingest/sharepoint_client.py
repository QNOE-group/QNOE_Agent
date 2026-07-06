"""Microsoft Graph API client for SharePoint document library access.

Authentication via ROPC (username/password) using MSAL — same pattern as teams_polling.
All network operations are synchronous (requests library).

Key functions:
  authenticate(auth_cfg)                  → access token str
  get_site_id(group_id, token)            → site ID str
  get_drive_id(site_id, drive_name, token)→ drive ID str
  list_drive_items(drive_id, token)       → list of file item dicts
  download_to_temp(drive_id, item_id, dest_path, token)
  get_delta(drive_id, delta_link, token)  → (items, new_delta_link)
"""
import logging
import os
from pathlib import Path

import msal
import requests

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def authenticate(auth_cfg: dict) -> str:
    """Acquire access token via ROPC flow. Returns access token string."""
    username = os.environ.get(auth_cfg["username_env"])
    password = os.environ.get(auth_cfg["password_env"])
    if not username or not password:
        raise ValueError(
            f"Missing credentials: set {auth_cfg['username_env']} and "
            f"{auth_cfg['password_env']} environment variables"
        )
    app = msal.PublicClientApplication(
        auth_cfg["app_id"],
        authority=f"https://login.microsoftonline.com/{auth_cfg['tenant_id']}",
    )
    result = app.acquire_token_by_username_password(
        username=username,
        password=password,
        scopes=auth_cfg["scopes"],
    )
    if "access_token" not in result:
        raise RuntimeError(
            f"MSAL auth failed: {result.get('error_description', result)}"
        )
    return result["access_token"]


# ---------------------------------------------------------------------------
# Graph API helpers
# ---------------------------------------------------------------------------

def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _get(url: str, token: str, params: dict | None = None) -> dict:
    resp = requests.get(url, headers=_headers(token), params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Site / drive discovery
# ---------------------------------------------------------------------------

def get_site_id(group_id: str, token: str) -> str:
    """Get the SharePoint site ID associated with a Teams group."""
    data = _get(f"{GRAPH_BASE}/groups/{group_id}/sites/root", token)
    return data["id"]


def get_drive_id(site_id: str, drive_name: str, token: str) -> str:
    """Get the drive ID for a named document library within a site."""
    data = _get(f"{GRAPH_BASE}/sites/{site_id}/drives", token)
    for drive in data.get("value", []):
        if drive["name"].lower() == drive_name.lower():
            return drive["id"]
    available = [d["name"] for d in data.get("value", [])]
    raise ValueError(
        f"Drive '{drive_name}' not found in site {site_id}. Available: {available}"
    )


# ---------------------------------------------------------------------------
# Item listing
# ---------------------------------------------------------------------------

def list_drive_items(drive_id: str, token: str) -> list[dict]:
    """Recursively list all files in a drive. Returns file item metadata only (no folders).

    Handles @odata.nextLink pagination at every level.
    """
    items: list[dict] = []

    def _recurse(url: str) -> None:
        while url:
            data = _get(url, token)
            for item in data.get("value", []):
                if "folder" in item:
                    child_url = (
                        f"{GRAPH_BASE}/drives/{drive_id}/items/{item['id']}/children"
                    )
                    _recurse(child_url)
                elif "file" in item:
                    items.append(item)
            url = data.get("@odata.nextLink")

    _recurse(f"{GRAPH_BASE}/drives/{drive_id}/root/children")
    return items


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

def download_to_temp(drive_id: str, item_id: str, dest_path: Path, token: str) -> None:
    """Stream a file to dest_path without loading it fully into RAM.

    Uses requests streaming + chunked write. Follows Graph API redirect to CDN.
    Caller is responsible for deleting dest_path after processing.
    """
    url = f"{GRAPH_BASE}/drives/{drive_id}/items/{item_id}/content"
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(
        url, headers=_headers(token), stream=True, timeout=120, allow_redirects=True
    ) as resp:
        resp.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                f.write(chunk)


# ---------------------------------------------------------------------------
# Delta
# ---------------------------------------------------------------------------

def get_delta(
    drive_id: str,
    delta_link: str | None,
    token: str,
    auth_cfg: dict | None = None,
) -> tuple[list[dict], str]:
    """Fetch delta changes for a drive since the last delta_link.

    If delta_link is None, returns all items (initial delta) plus a new delta_link.
    Handles @odata.nextLink pagination. Returns (changed_items, new_delta_link).

    Pass auth_cfg to enable automatic token refresh every 45 min during long listings
    (required for large drives where pagination takes >60 min).
    """
    import time as _time
    url = delta_link or f"{GRAPH_BASE}/drives/{drive_id}/root/delta"
    items: list[dict] = []
    new_delta_link: str | None = None
    page_count = 0
    token_ts = _time.monotonic()

    while url:
        # Refresh token if >45 min have elapsed (tokens expire at 60 min)
        if auth_cfg and _time.monotonic() - token_ts >= 45 * 60:
            try:
                token = authenticate(auth_cfg)
                token_ts = _time.monotonic()
                logger.info("SP get_delta: token refreshed at page %d", page_count)
            except Exception as exc:
                logger.warning("SP get_delta: token refresh failed: %s", exc)

        data = _get(url, token)
        items.extend(data.get("value", []))
        page_count += 1
        if page_count % 20 == 0:
            logger.info(
                "SP delta listing: page %d, %d items so far (drive %s…)",
                page_count, len(items), drive_id[:20],
            )
        new_delta_link = data.get("@odata.deltaLink") or new_delta_link
        url = data.get("@odata.nextLink")

    if not new_delta_link:
        raise RuntimeError(f"No @odata.deltaLink received for drive {drive_id}")
    logger.info("SP delta listing complete: %d pages, %d items", page_count, len(items))
    return items, new_delta_link
