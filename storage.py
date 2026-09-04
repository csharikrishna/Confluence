"""
Phase 2A — Time-Series Store

SQLite-backed persistence for environmental snapshots. Deliberately simple per the
Phase 2 plan: one `snapshots` table, no TimescaleDB/InfluxDB. Also backs the
trend-24h computation and the "N hours ago" lookups the alert rules engine needs
for trend-based rules (e.g. "temperature rose 5C in 3h").

Every public function opens and closes its own connection — cheap for SQLite and
keeps this safe to call from FastAPI's threadpool-executed background tasks without
sharing a connection across threads.
"""

import os
import json
import sqlite3
from datetime import datetime, timezone, timedelta

from utils import get_path

DB_PATH = os.getenv(
    "CONFLUENCE_DB_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "confluence_history.db"),
)

# Fields surfaced in the lightweight meta.trend_24h diff (Phase 2A schema).
TREND_FIELDS = {
    "temperature_c": "weather.temperature_c",
    "humidity_pct": "weather.humidity_pct",
    "pressure_hpa": "weather.pressure_hpa",
    "wind_speed_kmh": "weather.wind_speed_kmh",
    "wave_height_m": "marine.wave_height_m",
    "pm25": "air_quality.pm25",
    "uv_index": "weather.uv_index",
}

DEFAULT_RETENTION_DAYS = 90


def _connect():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    return conn


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def init_db():
    """Create tables/indexes if missing, then run a best-effort retention prune."""
    conn = _connect()
    try:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lat REAL NOT NULL,
                lon REAL NOT NULL,
                name TEXT,
                timestamp TEXT NOT NULL,
                raw_json TEXT NOT NULL
            )"""
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_loc_time ON snapshots (lat, lon, timestamp)")
        conn.execute(
            """CREATE TABLE IF NOT EXISTS alerts_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lat REAL NOT NULL,
                lon REAL NOT NULL,
                rule_id TEXT NOT NULL,
                severity TEXT,
                message TEXT,
                triggered_at TEXT NOT NULL,
                value TEXT
            )"""
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts_loc_rule_time ON alerts_log (lat, lon, rule_id, triggered_at)")
        conn.commit()
    finally:
        conn.close()

    try:
        prune_old_snapshots()
    except Exception:
        pass
    try:
        prune_old_alerts()
    except Exception:
        pass


def save_snapshot(lat, lon, name, snapshot):
    """Persist a full snapshot dict (location/generated_at/data/meta) as one row."""
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO snapshots (lat, lon, name, timestamp, raw_json) VALUES (?, ?, ?, ?, ?)",
            (
                round(float(lat), 3),
                round(float(lon), 3),
                name,
                snapshot.get("generated_at") or _now_iso(),
                json.dumps(snapshot),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_history(lat, lon, start, end, field=None, limit=500):
    """Return stored readings for (lat, lon) between ISO8601 start/end (inclusive).

    If `field` is given (dotted path into the snapshot's `data`, e.g.
    'weather.temperature_c'), each row is {timestamp, value}; otherwise each row is
    {timestamp, data} with the full multi-domain snapshot data.
    """
    conn = _connect()
    try:
        cur = conn.execute(
            "SELECT timestamp, raw_json FROM snapshots WHERE lat=? AND lon=? AND timestamp BETWEEN ? AND ? "
            "ORDER BY timestamp ASC LIMIT ?",
            (round(float(lat), 3), round(float(lon), 3), start, end, limit),
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    result = []
    for ts, raw in rows:
        try:
            snap = json.loads(raw)
        except (TypeError, ValueError):
            continue
        data = snap.get("data", {})
        if field:
            result.append({"timestamp": ts, "value": get_path(data, field)})
        else:
            result.append({"timestamp": ts, "data": data})
    return result


def get_reading_hours_ago(lat, lon, hours_ago, tolerance_hours=1.5):
    """Return the `data` dict of the snapshot closest to (now - hours_ago), or None
    if nothing was stored within `tolerance_hours` of that target time.
    """
    target = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    lo = (target - timedelta(hours=tolerance_hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    hi = (target + timedelta(hours=tolerance_hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    target_str = target.strftime("%Y-%m-%dT%H:%M:%SZ")

    conn = _connect()
    try:
        cur = conn.execute(
            "SELECT raw_json FROM snapshots WHERE lat=? AND lon=? AND timestamp BETWEEN ? AND ? "
            "ORDER BY ABS(strftime('%s', timestamp) - strftime('%s', ?)) ASC LIMIT 1",
            (round(float(lat), 3), round(float(lon), 3), lo, hi, target_str),
        )
        row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        return None
    try:
        return json.loads(row[0]).get("data")
    except (TypeError, ValueError):
        return None


def compute_trend_24h(lat, lon, current_data, past=None):
    """Diff a curated set of fields against the closest stored reading ~24h ago.

    Returns None if there's no reading old enough yet (e.g. a brand-new location) —
    trend data necessarily needs history to exist first.

    `past` lets a caller that already fetched the 24h-ago reading (e.g. for
    get_pressure_change_24h in the same request) pass it in directly instead of
    triggering a second identical lookup — matters most for the remote
    Mongo/CouchDB backends, where each lookup is a network round-trip.
    """
    if past is None:
        past = get_reading_hours_ago(lat, lon, 24, tolerance_hours=3)
    if not past:
        return None

    trend = {}
    for key, path in TREND_FIELDS.items():
        cur_val = get_path(current_data, path)
        past_val = get_path(past, path)
        if cur_val is None or past_val is None:
            continue
        change = round(cur_val - past_val, 2)
        trend[key] = {
            "current": cur_val,
            "previous": past_val,
            "change": f"{'+' if change >= 0 else ''}{change}",
        }
    return trend or None


def get_pressure_change_24h(lat, lon, current_pressure_hpa, tolerance_hours=3, past=None):
    """Raw numeric pressure delta (current - reading ~24h ago), or None if no
    history exists yet or the current pressure isn't available. Powers the
    latitude-normalized rapid-pressure-fall signal in derived_insights.py.

    `past` lets a caller reuse an already-fetched 24h-ago reading — see
    compute_trend_24h's docstring for why this matters.
    """
    if current_pressure_hpa is None:
        return None
    if past is None:
        past = get_reading_hours_ago(lat, lon, 24, tolerance_hours=tolerance_hours)
    past_pressure = get_path(past, "weather.pressure_hpa") if past else None
    if past_pressure is None:
        return None
    return round(current_pressure_hpa - past_pressure, 2)


def log_alert(lat, lon, alert, cooldown_minutes=60):
    """Record a triggered alert, deduped: skip if the same rule already logged for
    this location within `cooldown_minutes` (so a live 5-minute-cached endpoint
    hammered repeatedly doesn't spam the alert history with the same event).
    """
    conn = _connect()
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=cooldown_minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")
        cur = conn.execute(
            "SELECT id FROM alerts_log WHERE lat=? AND lon=? AND rule_id=? AND triggered_at > ? LIMIT 1",
            (round(float(lat), 3), round(float(lon), 3), alert["id"], cutoff),
        )
        if cur.fetchone():
            return False

        conn.execute(
            "INSERT INTO alerts_log (lat, lon, rule_id, severity, message, triggered_at, value) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                round(float(lat), 3),
                round(float(lon), 3),
                alert["id"],
                alert.get("severity"),
                alert.get("message"),
                alert.get("triggered_at") or _now_iso(),
                json.dumps(alert.get("value")),
            ),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def get_alert_history(lat=None, lon=None, limit=100):
    """Return recently logged alerts, optionally scoped to one location."""
    conn = _connect()
    try:
        if lat is not None and lon is not None:
            cur = conn.execute(
                "SELECT lat, lon, rule_id, severity, message, triggered_at, value FROM alerts_log "
                "WHERE lat=? AND lon=? ORDER BY triggered_at DESC LIMIT ?",
                (round(float(lat), 3), round(float(lon), 3), limit),
            )
        else:
            cur = conn.execute(
                "SELECT lat, lon, rule_id, severity, message, triggered_at, value FROM alerts_log "
                "ORDER BY triggered_at DESC LIMIT ?",
                (limit,),
            )
        rows = cur.fetchall()
    finally:
        conn.close()

    return [
        {
            "lat": r[0],
            "lon": r[1],
            "rule_id": r[2],
            "severity": r[3],
            "message": r[4],
            "triggered_at": r[5],
            "value": json.loads(r[6]) if r[6] is not None else None,
        }
        for r in rows
    ]


def is_healthy():
    """Quick connectivity check for /health — a real query, not just file existence."""
    try:
        conn = _connect()
        try:
            conn.execute("SELECT 1")
        finally:
            conn.close()
        return True
    except Exception:
        return False


def prune_old_snapshots(retention_days=DEFAULT_RETENTION_DAYS):
    """Delete snapshots older than `retention_days`. Returns rows deleted."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn = _connect()
    try:
        cur = conn.execute("DELETE FROM snapshots WHERE timestamp < ?", (cutoff,))
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def prune_old_alerts(retention_days=DEFAULT_RETENTION_DAYS):
    """Delete alert_log entries older than `retention_days`. Without this,
    alerts_log has no equivalent of prune_old_snapshots and grows unbounded
    forever. Returns rows deleted.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn = _connect()
    try:
        cur = conn.execute("DELETE FROM alerts_log WHERE triggered_at < ?", (cutoff,))
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()
