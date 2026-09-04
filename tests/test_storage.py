"""
Unit tests for the Phase 2A SQLite history store (storage.py).
Uses an isolated temp DB file per test (via CONFLUENCE_DB_PATH monkeypatching)
so these tests never touch the real confluence_history.db.
"""

import os
import sys
import json
import tempfile
import unittest
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import storage


def _iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class TestStorage(unittest.TestCase):
    def setUp(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self._tmp_path = path
        self._orig_path = storage.DB_PATH
        storage.DB_PATH = path
        storage.init_db()

    def tearDown(self):
        storage.DB_PATH = self._orig_path
        try:
            os.remove(self._tmp_path)
        except OSError:
            pass

    def _snapshot(self, generated_at, temperature_c=30.0, pm25=20.0, wave=1.0):
        return {
            "location": {"name": "Test Point", "lat": 13.08, "lon": 80.27},
            "generated_at": generated_at,
            "data": {
                "weather": {"status": "ok", "temperature_c": temperature_c, "humidity_pct": 60.0},
                "marine": {"status": "ok", "wave_height_m": wave},
                "air_quality": {"status": "ok", "pm25": pm25},
            },
            "meta": {"confidence": "high"},
        }

    def test_save_and_get_history_full(self):
        now = datetime.now(timezone.utc)
        storage.save_snapshot(13.08, 80.27, "Test Point", self._snapshot(_iso(now)))

        rows = storage.get_history(
            13.08, 80.27,
            _iso(now - timedelta(minutes=5)),
            _iso(now + timedelta(minutes=5)),
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["data"]["weather"]["temperature_c"], 30.0)

    def test_get_history_with_field_path(self):
        now = datetime.now(timezone.utc)
        storage.save_snapshot(13.08, 80.27, "Test Point", self._snapshot(_iso(now), temperature_c=32.5))

        rows = storage.get_history(
            13.08, 80.27,
            _iso(now - timedelta(minutes=5)),
            _iso(now + timedelta(minutes=5)),
            field="weather.temperature_c",
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["value"], 32.5)

    def test_get_history_empty_range_returns_empty_list(self):
        rows = storage.get_history(13.08, 80.27, "2000-01-01T00:00:00Z", "2000-01-02T00:00:00Z")
        self.assertEqual(rows, [])

    def test_get_history_scoped_to_location(self):
        now = datetime.now(timezone.utc)
        storage.save_snapshot(13.08, 80.27, "Chennai", self._snapshot(_iso(now)))
        storage.save_snapshot(18.94, 72.84, "Mumbai", self._snapshot(_iso(now)))

        rows = storage.get_history(
            13.08, 80.27,
            _iso(now - timedelta(minutes=5)),
            _iso(now + timedelta(minutes=5)),
        )
        self.assertEqual(len(rows), 1)

    def test_get_reading_hours_ago_finds_closest_within_tolerance(self):
        target_time = datetime.now(timezone.utc) - timedelta(hours=24)
        storage.save_snapshot(13.08, 80.27, "Test", self._snapshot(_iso(target_time), temperature_c=28.0))

        data = storage.get_reading_hours_ago(13.08, 80.27, hours_ago=24, tolerance_hours=3)
        self.assertIsNotNone(data)
        self.assertEqual(data["weather"]["temperature_c"], 28.0)

    def test_get_reading_hours_ago_none_outside_tolerance(self):
        far_time = datetime.now(timezone.utc) - timedelta(hours=48)
        storage.save_snapshot(13.08, 80.27, "Test", self._snapshot(_iso(far_time)))

        data = storage.get_reading_hours_ago(13.08, 80.27, hours_ago=24, tolerance_hours=1)
        self.assertIsNone(data)

    def test_compute_trend_24h_returns_diff(self):
        past_time = datetime.now(timezone.utc) - timedelta(hours=24)
        storage.save_snapshot(13.08, 80.27, "Test", self._snapshot(_iso(past_time), temperature_c=29.0, pm25=30.0))

        current_data = {
            "weather": {"status": "ok", "temperature_c": 31.5},
            "air_quality": {"status": "ok", "pm25": 22.0},
        }
        trend = storage.compute_trend_24h(13.08, 80.27, current_data)
        self.assertIsNotNone(trend)
        self.assertEqual(trend["temperature_c"]["current"], 31.5)
        self.assertEqual(trend["temperature_c"]["previous"], 29.0)
        self.assertEqual(trend["temperature_c"]["change"], "+2.5")
        self.assertEqual(trend["pm25"]["change"], "-8.0")

    def test_compute_trend_24h_none_when_no_history(self):
        trend = storage.compute_trend_24h(13.08, 80.27, {"weather": {"temperature_c": 30.0}})
        self.assertIsNone(trend)

    def test_prune_old_snapshots_removes_stale_rows(self):
        old_time = datetime.now(timezone.utc) - timedelta(days=100)
        recent_time = datetime.now(timezone.utc)
        storage.save_snapshot(13.08, 80.27, "Old", self._snapshot(_iso(old_time)))
        storage.save_snapshot(13.08, 80.27, "Recent", self._snapshot(_iso(recent_time)))

        deleted = storage.prune_old_snapshots(retention_days=90)
        self.assertEqual(deleted, 1)

        rows = storage.get_history(13.08, 80.27, "1970-01-01T00:00:00Z", _iso(datetime.now(timezone.utc) + timedelta(days=1)))
        self.assertEqual(len(rows), 1)

    def test_log_alert_dedupes_within_cooldown(self):
        alert = {"id": "pm25_unhealthy", "severity": "high", "message": "test", "triggered_at": _iso(datetime.now(timezone.utc)), "value": 60.0}
        first = storage.log_alert(13.08, 80.27, alert, cooldown_minutes=60)
        second = storage.log_alert(13.08, 80.27, alert, cooldown_minutes=60)
        self.assertTrue(first)
        self.assertFalse(second)

        history = storage.get_alert_history(13.08, 80.27)
        self.assertEqual(len(history), 1)

    def test_is_healthy_true_with_valid_db(self):
        self.assertTrue(storage.is_healthy())

    def test_is_healthy_false_with_unwritable_path(self):
        storage.DB_PATH = os.path.join(self._tmp_path + "_nonexistent_dir", "db.sqlite")
        self.assertFalse(storage.is_healthy())

    def test_prune_old_alerts_removes_stale_rows(self):
        old_time = datetime.now(timezone.utc) - timedelta(days=100)
        recent_time = datetime.now(timezone.utc)
        conn = storage._connect()
        conn.execute(
            "INSERT INTO alerts_log (lat, lon, rule_id, severity, message, triggered_at, value) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (13.08, 80.27, "old_rule", "high", "old", _iso(old_time), json.dumps(1.0)),
        )
        conn.execute(
            "INSERT INTO alerts_log (lat, lon, rule_id, severity, message, triggered_at, value) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (13.08, 80.27, "recent_rule", "high", "recent", _iso(recent_time), json.dumps(2.0)),
        )
        conn.commit()
        conn.close()

        deleted = storage.prune_old_alerts(retention_days=90)
        self.assertEqual(deleted, 1)

        remaining = storage.get_alert_history(13.08, 80.27)
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0]["rule_id"], "recent_rule")

    def test_log_alert_allows_after_cooldown_expires(self):
        old_alert = {
            "id": "pm25_unhealthy", "severity": "high", "message": "old",
            "triggered_at": _iso(datetime.now(timezone.utc) - timedelta(minutes=120)), "value": 60.0,
        }
        conn = storage._connect()
        conn.execute(
            "INSERT INTO alerts_log (lat, lon, rule_id, severity, message, triggered_at, value) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (13.08, 80.27, "pm25_unhealthy", "high", "old", old_alert["triggered_at"], json.dumps(60.0)),
        )
        conn.commit()
        conn.close()

        new_alert = {"id": "pm25_unhealthy", "severity": "high", "message": "new", "triggered_at": _iso(datetime.now(timezone.utc)), "value": 70.0}
        logged = storage.log_alert(13.08, 80.27, new_alert, cooldown_minutes=60)
        self.assertTrue(logged)


if __name__ == "__main__":
    unittest.main()
