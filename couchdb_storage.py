"""
Optional CouchDB-backed history store — an alternate backend to storage.py's
SQLite implementation, exposing the identical function surface so it's a
drop-in swap (see db_backend.py, which selects between the two via the
STORAGE_BACKEND env var).

This module is a thin REST client over CouchDB's HTTP API (uses `requests`,
already a dependency — no CouchDB client library needed). It does NOT run,
install, or embed CouchDB itself: CouchDB must be running as its own server
(Docker is the recommended path — see docs/PHASE2_WALKTHROUGH.md) and reachable
at COUCHDB_URL. This module is only ever exercised if STORAGE_BACKEND=couchdb
is set; until then storage.py (SQLite) remains the active backend and nothing
here is imported into the request path.

Two databases are used:
  - snapshots db: one document per persisted /environment snapshot
  - alerts db:    one document per logged alert (cooldown-deduped, same as SQLite)

Every document additionally gets a Mango index on (lat, lon, timestamp) /
(lat, lon, rule_id, triggered_at) so range queries don't force full scans.
"""

import os
import json
import uuid
import logging
from datetime import datetime, timezone, timedelta

import requests

from utils import get_path

logger = logging.getLogger("environmental_api")

COUCHDB_URL = os.getenv("COUCHDB_URL", "http://localhost:5984").rstrip("/")
COUCHDB_USER = os.getenv("COUCHDB_USER")
COUCHDB_PASSWORD = os.getenv("COUCHDB_PASSWORD")
SNAPSHOTS_DB = os.getenv("COUCHDB_SNAPSHOTS_DB", "confluence_snapshots")
ALERTS_DB = os.getenv("COUCHDB_ALERTS_DB", "confluence_alerts")

REQUEST_TIMEOUT = 10
DEFAULT_RETENTION_DAYS = 90

# For /health display parity with storage.py's DB_PATH — there's no local file
# here, so this just names the reachable endpoint instead.
DB_PATH = f"couchdb@{COUCHDB_URL}"


def _auth():
    if COUCHDB_USER and COUCHDB_PASSWORD:
        return (COUCHDB_USER, COUCHDB_PASSWORD)
    return None


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _db_url(db_name, path=""):
    return f"{COUCHDB_URL}/{db_name}{path}"


def _ensure_database(db_name):
    r = requests.put(_db_url(db_name), auth=_auth(), timeout=REQUEST_TIMEOUT)
    # 201 Created or 412 Precondition Failed (already exists) both mean "it's there now".
    if r.status_code not in (201, 412):
        r.raise_for_status()


def _ensure_index(db_name, fields, name):
    body = {"index": {"fields": fields}, "name": name, "type": "json"}
    r = requests.post(_db_url(db_name, "/_index"), auth=_auth(), json=body, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()


def init_db():
    """Create both databases and their query indexes if missing. Idempotent —
    safe to call on every startup, same contract as storage.init_db().
    """
    _ensure_database(SNAPSHOTS_DB)
    _ensure_database(ALERTS_DB)
    _ensure_index(SNAPSHOTS_DB, ["lat", "lon", "timestamp"], "snapshots_by_location_time")
    _ensure_index(ALERTS_DB, ["lat", "lon", "rule_id", "triggered_at"], "alerts_by_location_rule_time")
    try:
        prune_old_snapshots()
    except Exception:
        pass


def save_snapshot(lat, lon, name, snapshot):
    doc = {
        "_id": f"snapshot:{round(float(lat), 3)}:{round(float(lon), 3)}:{snapshot.get('generated_at') or _now_iso()}:{uuid.uuid4().hex[:8]}",
        "type": "snapshot",
        "lat": round(float(lat), 3),
        "lon": round(float(lon), 3),
        "name": name,
        "timestamp": snapshot.get("generated_at") or _now_iso(),
        "snapshot": snapshot,
    }
    r = requests.post(_db_url(SNAPSHOTS_DB), auth=_auth(), json=doc, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()


def _find(db_name, selector, sort=None, limit=None):
    body = {"selector": selector}
    if sort:
        body["sort"] = sort
    if limit:
        body["limit"] = limit
    r = requests.post(_db_url(db_name, "/_find"), auth=_auth(), json=body, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    return r.json().get("docs", [])


def get_history(lat, lon, start, end, field=None, limit=500):
    selector = {
        "lat": round(float(lat), 3),
        "lon": round(float(lon), 3),
        "timestamp": {"$gte": start, "$lte": end},
    }
    docs = _find(SNAPSHOTS_DB, selector, sort=[{"timestamp": "asc"}], limit=limit)

    result = []
    for doc in docs:
        data = (doc.get("snapshot") or {}).get("data", {})
        if field:
            result.append({"timestamp": doc.get("timestamp"), "value": get_path(data, field)})
        else:
            result.append({"timestamp": doc.get("timestamp"), "data": data})
    return result


def get_reading_hours_ago(lat, lon, hours_ago, tolerance_hours=1.5):
    target = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    lo = (target - timedelta(hours=tolerance_hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    hi = (target + timedelta(hours=tolerance_hours)).strftime("%Y-%m-%dT%H:%M:%SZ")

    selector = {"lat": round(float(lat), 3), "lon": round(float(lon), 3), "timestamp": {"$gte": lo, "$lte": hi}}
    docs = _find(SNAPSHOTS_DB, selector, sort=[{"timestamp": "asc"}])
    if not docs:
        return None

    # Mango can't sort by "closest to X" directly — pick the nearest in Python
    # (the candidate set here is small: at most a couple of hourly-cron rows
    # within a few-hour tolerance window).
    def _distance(doc):
        try:
            ts = datetime.strptime(doc["timestamp"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            return abs((ts - target).total_seconds())
        except (KeyError, ValueError):
            return float("inf")

    closest = min(docs, key=_distance)
    return (closest.get("snapshot") or {}).get("data")


def compute_trend_24h(lat, lon, current_data):
    past = get_reading_hours_ago(lat, lon, 24, tolerance_hours=3)
    if not past:
        return None

    trend_fields = {
        "temperature_c": "weather.temperature_c",
        "humidity_pct": "weather.humidity_pct",
        "pressure_hpa": "weather.pressure_hpa",
        "wind_speed_kmh": "weather.wind_speed_kmh",
        "wave_height_m": "marine.wave_height_m",
        "pm25": "air_quality.pm25",
        "uv_index": "weather.uv_index",
    }
    trend = {}
    for key, path in trend_fields.items():
        cur_val = get_path(current_data, path)
        past_val = get_path(past, path)
        if cur_val is None or past_val is None:
            continue
        change = round(cur_val - past_val, 2)
        trend[key] = {"current": cur_val, "previous": past_val, "change": f"{'+' if change >= 0 else ''}{change}"}
    return trend or None


def get_pressure_change_24h(lat, lon, current_pressure_hpa, tolerance_hours=3):
    if current_pressure_hpa is None:
        return None
    past = get_reading_hours_ago(lat, lon, 24, tolerance_hours=tolerance_hours)
    past_pressure = get_path(past, "weather.pressure_hpa") if past else None
    if past_pressure is None:
        return None
    return round(current_pressure_hpa - past_pressure, 2)


def log_alert(lat, lon, alert, cooldown_minutes=60):
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=cooldown_minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")
    selector = {
        "lat": round(float(lat), 3),
        "lon": round(float(lon), 3),
        "rule_id": alert["id"],
        "triggered_at": {"$gt": cutoff},
    }
    existing = _find(ALERTS_DB, selector, limit=1)
    if existing:
        return False

    doc = {
        "_id": f"alert:{round(float(lat), 3)}:{round(float(lon), 3)}:{alert['id']}:{uuid.uuid4().hex[:8]}",
        "type": "alert",
        "lat": round(float(lat), 3),
        "lon": round(float(lon), 3),
        "rule_id": alert["id"],
        "severity": alert.get("severity"),
        "message": alert.get("message"),
        "triggered_at": alert.get("triggered_at") or _now_iso(),
        "value": alert.get("value"),
    }
    r = requests.post(_db_url(ALERTS_DB), auth=_auth(), json=doc, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    return True


def get_alert_history(lat=None, lon=None, limit=100):
    """Note: intentionally does NOT pass `sort` to Mango here. CouchDB's Mango
    _find only accepts a sort when a matching index exists for that exact
    selector+sort shape (confirmed against a live instance — sorting by
    triggered_at alone doesn't match the (lat, lon, rule_id, triggered_at)
    index used by log_alert's dedupe lookup). Sorting the small result set in
    Python avoids needing a second, narrower index just for this rarely-hit path.
    """
    selector = {"type": "alert"}
    if lat is not None and lon is not None:
        selector["lat"] = round(float(lat), 3)
        selector["lon"] = round(float(lon), 3)
    docs = _find(ALERTS_DB, selector, limit=max(limit, 1000))
    docs.sort(key=lambda d: d.get("triggered_at") or "", reverse=True)
    docs = docs[:limit]
    return [
        {
            "lat": d.get("lat"),
            "lon": d.get("lon"),
            "rule_id": d.get("rule_id"),
            "severity": d.get("severity"),
            "message": d.get("message"),
            "triggered_at": d.get("triggered_at"),
            "value": d.get("value"),
        }
        for d in docs
    ]


def prune_old_snapshots(retention_days=DEFAULT_RETENTION_DAYS):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    docs = _find(SNAPSHOTS_DB, {"timestamp": {"$lt": cutoff}}, limit=1000)
    if not docs:
        return 0

    deletions = [{"_id": d["_id"], "_rev": d["_rev"], "_deleted": True} for d in docs]
    r = requests.post(_db_url(SNAPSHOTS_DB, "/_bulk_docs"), auth=_auth(), json={"docs": deletions}, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    return len(deletions)


def is_healthy():
    try:
        r = requests.get(f"{COUCHDB_URL}/", auth=_auth(), timeout=REQUEST_TIMEOUT)
        return r.status_code == 200
    except Exception:
        return False
