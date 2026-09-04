"""
Optional MongoDB-backed history store — the recommended durable alternative to
storage.py's SQLite (chosen over couchdb_storage.py: MongoDB Atlas's free M0
tier is fully managed — no server to run, patch, or host — and needs no credit
card to sign up, unlike Oracle Cloud's Always Free tier). Exposes the identical
function surface as storage.py/couchdb_storage.py, so it's a drop-in swap via
db_backend.py's STORAGE_BACKEND env var.

Uses the official `pymongo` driver (MongoDB's Atlas Data API — a plain HTTPS
REST option that would have avoided this dependency — was fully shut down in
September 2025, so the driver is the only supported path now). pymongo is an
OPTIONAL dependency (requirements-mongo.txt): imported lazily and guarded, so
the base app runs fine without it installed unless STORAGE_BACKEND=mongo is
actually selected.

Two collections are used, in one database (MONGODB_DB_NAME, default
"confluence"):
  - snapshots: one document per persisted /environment snapshot
  - alerts:    one document per logged alert (cooldown-deduped, same as SQLite)

Unlike CouchDB's Mango _find, MongoDB does NOT reject a query for lacking a
matching index — it just falls back to a collection scan (slower at scale, but
never an outright error). Indexes are still created for performance, but this
sidesteps the whole class of "no_usable_index" bug that had to be fixed in
couchdb_storage.py's get_alert_history.
"""

import os
import logging
from datetime import datetime, timezone, timedelta

from utils import get_path

logger = logging.getLogger("environmental_api")

try:
    from pymongo import MongoClient, ASCENDING, DESCENDING
    _PYMONGO_AVAILABLE = True
except ImportError:
    _PYMONGO_AVAILABLE = False
    # Fall back to pymongo's actual underlying sort-direction values (a stable
    # part of the MongoDB wire protocol, not pymongo-specific) so functions
    # that reference ASCENDING/DESCENDING at module scope don't raise a
    # confusing NameError when pymongo isn't installed — they still correctly
    # fail with the clear RuntimeError from _require_pymongo() instead, at the
    # point where a real (unmocked) DB call is actually attempted.
    ASCENDING = 1
    DESCENDING = -1

MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "confluence")

REQUEST_TIMEOUT_MS = 10000
DEFAULT_RETENTION_DAYS = 90

_client = None


def _require_pymongo():
    if not _PYMONGO_AVAILABLE:
        raise RuntimeError("pymongo isn't installed. Run: pip install -r requirements-mongo.txt")
    if not MONGODB_URI:
        raise RuntimeError("MONGODB_URI isn't set — see .env.example.")


def _get_client():
    global _client
    _require_pymongo()
    if _client is None:
        _client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=REQUEST_TIMEOUT_MS)
    return _client


def _db():
    return _get_client()[MONGODB_DB_NAME]


def _snapshots():
    return _db()["snapshots"]


def _alerts():
    return _db()["alerts"]


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _safe_host_desc():
    """A display-safe description for /health — MONGODB_URI embeds credentials,
    so this must never be logged/returned as-is.
    """
    if not MONGODB_URI:
        return "mongodb (not configured)"
    try:
        # urlparse handles mongodb:// and mongodb+srv:// the same way (any
        # scheme://netloc form) and .hostname already excludes user:pass.
        from urllib.parse import urlparse

        parsed = urlparse(MONGODB_URI)
        host = parsed.hostname or "unknown-host"
        if parsed.port:
            host = f"{host}:{parsed.port}"
        return f"mongodb@{host}"
    except Exception:
        return "mongodb (configured)"


DB_PATH = _safe_host_desc()


def init_db():
    """Create indexes if missing. Idempotent — safe to call on every startup,
    same contract as storage.init_db(). Unlike CouchDB, there's no separate
    "create the database" step; MongoDB creates a database/collection
    implicitly on first write.
    """
    _require_pymongo()
    _snapshots().create_index([("lat", ASCENDING), ("lon", ASCENDING), ("timestamp", ASCENDING)])
    _alerts().create_index([("lat", ASCENDING), ("lon", ASCENDING), ("rule_id", ASCENDING), ("triggered_at", ASCENDING)])
    try:
        prune_old_snapshots()
    except Exception:
        pass
    try:
        prune_old_alerts()
    except Exception:
        pass


def save_snapshot(lat, lon, name, snapshot):
    doc = {
        "lat": round(float(lat), 3),
        "lon": round(float(lon), 3),
        "name": name,
        "timestamp": snapshot.get("generated_at") or _now_iso(),
        "snapshot": snapshot,
    }
    _snapshots().insert_one(doc)


def get_history(lat, lon, start, end, field=None, limit=500):
    query = {"lat": round(float(lat), 3), "lon": round(float(lon), 3), "timestamp": {"$gte": start, "$lte": end}}
    cursor = _snapshots().find(query).sort("timestamp", ASCENDING).limit(limit)

    result = []
    for doc in cursor:
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

    query = {"lat": round(float(lat), 3), "lon": round(float(lon), 3), "timestamp": {"$gte": lo, "$lte": hi}}
    docs = list(_snapshots().find(query).sort("timestamp", ASCENDING))
    if not docs:
        return None

    def _distance(doc):
        try:
            ts = datetime.strptime(doc["timestamp"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            return abs((ts - target).total_seconds())
        except (KeyError, ValueError):
            return float("inf")

    closest = min(docs, key=_distance)
    return (closest.get("snapshot") or {}).get("data")


def compute_trend_24h(lat, lon, current_data, past=None):
    """`past` lets a caller reuse an already-fetched 24h-ago reading instead of
    triggering a second identical Atlas round-trip in the same request.
    """
    if past is None:
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


def get_pressure_change_24h(lat, lon, current_pressure_hpa, tolerance_hours=3, past=None):
    if current_pressure_hpa is None:
        return None
    if past is None:
        past = get_reading_hours_ago(lat, lon, 24, tolerance_hours=tolerance_hours)
    past_pressure = get_path(past, "weather.pressure_hpa") if past else None
    if past_pressure is None:
        return None
    return round(current_pressure_hpa - past_pressure, 2)


def log_alert(lat, lon, alert, cooldown_minutes=60):
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=cooldown_minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")
    existing = _alerts().find_one(
        {"lat": round(float(lat), 3), "lon": round(float(lon), 3), "rule_id": alert["id"], "triggered_at": {"$gt": cutoff}}
    )
    if existing:
        return False

    doc = {
        "lat": round(float(lat), 3),
        "lon": round(float(lon), 3),
        "rule_id": alert["id"],
        "severity": alert.get("severity"),
        "message": alert.get("message"),
        "triggered_at": alert.get("triggered_at") or _now_iso(),
        "value": alert.get("value"),
    }
    _alerts().insert_one(doc)
    return True


def get_alert_history(lat=None, lon=None, limit=100):
    query = {}
    if lat is not None and lon is not None:
        query["lat"] = round(float(lat), 3)
        query["lon"] = round(float(lon), 3)
    cursor = _alerts().find(query).sort("triggered_at", DESCENDING).limit(limit)
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
        for d in cursor
    ]


def prune_old_snapshots(retention_days=DEFAULT_RETENTION_DAYS):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    result = _snapshots().delete_many({"timestamp": {"$lt": cutoff}})
    return result.deleted_count


def prune_old_alerts(retention_days=DEFAULT_RETENTION_DAYS):
    """alerts_log has no equivalent of prune_old_snapshots without this — the
    log would otherwise grow unbounded forever.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    result = _alerts().delete_many({"triggered_at": {"$lt": cutoff}})
    return result.deleted_count


def is_healthy():
    try:
        _get_client().admin.command("ping")
        return True
    except Exception:
        return False
