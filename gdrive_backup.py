"""
Optional Google Drive backup — a disaster-recovery convenience, NOT a live
database. Whatever storage backend is active (storage.py/SQLite,
mongo_storage.py/MongoDB, or couchdb_storage.py/CouchDB — see db_backend.py)
remains the actual source of truth this app reads and writes on every
request. This module just uploads a periodic point-in-time JSON export of
recent history to a Drive folder, so there's an off-platform copy if the
primary store is ever lost.

Fully inert unless GDRIVE_ENABLED=true AND credentials are configured. The
google-api-python-client / google-auth libraries are imported lazily inside
the functions that need them, so the base app runs fine without them
installed — see requirements-gdrive.txt for the optional extra.

Credentials: create a Google Cloud service account with access to a target
Drive folder (share the folder with the service account's email), then set
EITHER:
  - GDRIVE_SERVICE_ACCOUNT_JSON: the service account key file's contents,
    pasted as a single-line JSON string env var (works well on Render, which
    has no persistent place to upload a key file to), or
  - GDRIVE_SERVICE_ACCOUNT_FILE: a filesystem path to the key file.
Also set GDRIVE_FOLDER_ID (the target Drive folder's ID from its URL) —
optional; omitted, uploads land in the service account's own Drive root.
"""

import os
import json
import logging
import tempfile
from datetime import datetime, timezone

logger = logging.getLogger("environmental_api")

GDRIVE_ENABLED = os.getenv("GDRIVE_ENABLED", "false").strip().lower() == "true"
GDRIVE_FOLDER_ID = os.getenv("GDRIVE_FOLDER_ID")
GDRIVE_SERVICE_ACCOUNT_FILE = os.getenv("GDRIVE_SERVICE_ACCOUNT_FILE")
GDRIVE_SERVICE_ACCOUNT_JSON = os.getenv("GDRIVE_SERVICE_ACCOUNT_JSON")

# drive.file scope: the app can only see/manage files IT created, not the
# service account's whole Drive — the minimum privilege this feature needs.
_SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def is_configured():
    return GDRIVE_ENABLED and bool(GDRIVE_SERVICE_ACCOUNT_JSON or GDRIVE_SERVICE_ACCOUNT_FILE)


def _get_drive_service():
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError as e:
        raise RuntimeError(
            "google-api-python-client / google-auth aren't installed. "
            "Run: pip install -r requirements-gdrive.txt"
        ) from e

    if GDRIVE_SERVICE_ACCOUNT_JSON:
        info = json.loads(GDRIVE_SERVICE_ACCOUNT_JSON)
        creds = service_account.Credentials.from_service_account_info(info, scopes=_SCOPES)
    elif GDRIVE_SERVICE_ACCOUNT_FILE:
        creds = service_account.Credentials.from_service_account_file(GDRIVE_SERVICE_ACCOUNT_FILE, scopes=_SCOPES)
    else:
        raise RuntimeError("No Google Drive credentials configured (GDRIVE_SERVICE_ACCOUNT_JSON or _FILE).")

    return build("drive", "v3", credentials=creds, cache_discovery=False)


def backup_export(export_rows, filename_prefix="confluence_backup"):
    """Upload a JSON export (any JSON-serializable object — typically a list of
    {location, history} dicts gathered from the active storage backend) to the
    configured Drive folder.

    Returns the uploaded file's Drive file ID, or None if unconfigured or on
    failure. Never raises — this must not be able to break the caller (a
    background task or a scheduled loop), since it's a best-effort convenience,
    not the primary data path.
    """
    if not is_configured():
        logger.info("Google Drive backup skipped: not configured (GDRIVE_ENABLED/credentials unset).")
        return None

    tmp_path = None
    try:
        from googleapiclient.http import MediaFileUpload

        service = _get_drive_service()
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        filename = f"{filename_prefix}_{timestamp}.json"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(export_rows, f)
            tmp_path = f.name

        metadata = {"name": filename}
        if GDRIVE_FOLDER_ID:
            metadata["parents"] = [GDRIVE_FOLDER_ID]

        media = MediaFileUpload(tmp_path, mimetype="application/json")
        uploaded = service.files().create(body=metadata, media_body=media, fields="id").execute()
        file_id = uploaded.get("id")
        logger.info(f"Google Drive backup uploaded: {filename} (id={file_id})")
        return file_id
    except Exception as e:
        logger.warning(f"Google Drive backup failed: {e}")
        return None
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


def build_export(locations, storage_module, days=7):
    """Gather recent history for every given location into one export payload,
    using whatever storage backend is passed in (db_backend, or storage.py /
    couchdb_storage.py directly). Kept separate from backup_export() so it's
    trivial to unit test without touching the Drive API.
    """
    from datetime import timedelta

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    end_str = end.strftime("%Y-%m-%dT%H:%M:%SZ")
    start_str = start.strftime("%Y-%m-%dT%H:%M:%SZ")

    export = []
    for loc in locations:
        try:
            history = storage_module.get_history(loc["lat"], loc["lon"], start_str, end_str, limit=1000)
        except Exception as e:
            logger.warning(f"Backup export: history fetch failed for {loc.get('name')}: {e}")
            history = []
        export.append({"location": loc, "history": history})
    return export
