"""
Storage backend selector. Set STORAGE_BACKEND to "mongo" (recommended durable
option — see mongo_storage.py) or "couchdb" (kept dormant/available, see
couchdb_storage.py) to switch off SQLite; leave unset/"sqlite" (default) to
keep using storage.py exactly as before.

Both app.py and notifications.py import THIS module (aliased `as storage`)
rather than importing storage.py/couchdb_storage.py/mongo_storage.py
directly, so there's a single place that decides which backend is live — no
risk of one module writing to SQLite while another reads from Mongo.

Implementation note: the functions below are bound directly to the active
backend module's function objects (not copied/wrapped), so they still read
that module's own globals at call time — e.g. storage.py's tests, which
monkeypatch storage.DB_PATH directly, keep working unchanged, because
db_backend.save_snapshot IS storage.save_snapshot when STORAGE_BACKEND=sqlite
(the default in every test run, since nothing sets that env var).
"""

import os

import storage as _sqlite
import couchdb_storage as _couchdb
import mongo_storage as _mongo

BACKEND_NAME = os.getenv("STORAGE_BACKEND", "sqlite").strip().lower()
_BACKENDS = {"couchdb": _couchdb, "mongo": _mongo}
_active = _BACKENDS.get(BACKEND_NAME, _sqlite)

init_db = _active.init_db
save_snapshot = _active.save_snapshot
get_history = _active.get_history
get_reading_hours_ago = _active.get_reading_hours_ago
compute_trend_24h = _active.compute_trend_24h
get_pressure_change_24h = _active.get_pressure_change_24h
log_alert = _active.log_alert
get_alert_history = _active.get_alert_history
prune_old_snapshots = _active.prune_old_snapshots
prune_old_alerts = _active.prune_old_alerts
is_healthy = _active.is_healthy
DB_PATH = _active.DB_PATH
