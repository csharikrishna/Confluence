"""
Unit tests for the MongoDB Atlas storage backend (mongo_storage.py) — the
recommended durable alternative to SQLite. Mocks the pymongo collection
objects directly (no real Atlas cluster needed for these); a real local
MongoDB container is used separately to catch anything mocks would miss,
the same way a real CouchDB container caught a real bug earlier.
"""

import os
import sys
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import mongo_storage as mongo


def _iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class TestSafeHostDesc(unittest.TestCase):
    def test_masks_credentials_from_connection_string(self):
        with patch.object(mongo, "MONGODB_URI", "mongodb+srv://user:secretpw@cluster0.abcde.mongodb.net/?retryWrites=true"):
            desc = mongo._safe_host_desc()
        self.assertNotIn("secretpw", desc)
        self.assertNotIn("user", desc)
        self.assertIn("cluster0.abcde.mongodb.net", desc)

    def test_not_configured_when_uri_unset(self):
        with patch.object(mongo, "MONGODB_URI", None):
            self.assertEqual(mongo._safe_host_desc(), "mongodb (not configured)")

    def test_plain_uri_without_credentials_shows_real_host(self):
        # Regression: found live against a real local mongod — the original
        # naive string-splitting parser mistook the "mongodb://" scheme prefix
        # itself for the host when no "user:pass@" segment was present,
        # producing "mongodb@mongodb:" instead of "mongodb@localhost:27017".
        with patch.object(mongo, "MONGODB_URI", "mongodb://localhost:27017"):
            desc = mongo._safe_host_desc()
        self.assertEqual(desc, "mongodb@localhost:27017")


class TestRequirePymongo(unittest.TestCase):
    def test_raises_clearly_when_pymongo_unavailable(self):
        with patch.object(mongo, "_PYMONGO_AVAILABLE", False):
            with self.assertRaises(RuntimeError) as ctx:
                mongo._require_pymongo()
            self.assertIn("pymongo", str(ctx.exception))

    def test_raises_clearly_when_uri_unset(self):
        with patch.object(mongo, "_PYMONGO_AVAILABLE", True), patch.object(mongo, "MONGODB_URI", None):
            with self.assertRaises(RuntimeError) as ctx:
                mongo._require_pymongo()
            self.assertIn("MONGODB_URI", str(ctx.exception))


class MongoTestCase(unittest.TestCase):
    """Base: mocks _snapshots()/_alerts() so tests never need a real client."""

    def setUp(self):
        self.snapshots = MagicMock()
        self.alerts = MagicMock()
        self._patchers = [
            patch("mongo_storage._snapshots", return_value=self.snapshots),
            patch("mongo_storage._alerts", return_value=self.alerts),
        ]
        for p in self._patchers:
            p.start()

    def tearDown(self):
        for p in self._patchers:
            p.stop()


class TestSaveSnapshot(MongoTestCase):
    def test_save_snapshot_inserts_expected_document_shape(self):
        snapshot = {"generated_at": "2026-09-03T10:00:00Z", "data": {"weather": {"temperature_c": 30.0}}}
        mongo.save_snapshot(13.08, 80.27, "Chennai Coast", snapshot)

        self.snapshots.insert_one.assert_called_once()
        doc = self.snapshots.insert_one.call_args[0][0]
        self.assertEqual(doc["lat"], 13.08)
        self.assertEqual(doc["lon"], 80.27)
        self.assertEqual(doc["name"], "Chennai Coast")
        self.assertEqual(doc["snapshot"], snapshot)


class TestGetHistory(MongoTestCase):
    def test_get_history_builds_range_query_and_parses_docs(self):
        docs = [
            {"timestamp": "2026-09-03T09:00:00Z", "snapshot": {"data": {"weather": {"temperature_c": 30.0}}}},
            {"timestamp": "2026-09-03T10:00:00Z", "snapshot": {"data": {"weather": {"temperature_c": 31.0}}}},
        ]
        cursor = MagicMock()
        cursor.sort.return_value.limit.return_value = docs
        self.snapshots.find.return_value = cursor

        rows = mongo.get_history(13.08, 80.27, "2026-09-03T00:00:00Z", "2026-09-03T23:59:59Z")

        query = self.snapshots.find.call_args[0][0]
        self.assertEqual(query["lat"], 13.08)
        self.assertEqual(query["timestamp"], {"$gte": "2026-09-03T00:00:00Z", "$lte": "2026-09-03T23:59:59Z"})
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["data"]["weather"]["temperature_c"], 30.0)

    def test_get_history_with_field_extracts_value(self):
        docs = [{"timestamp": "2026-09-03T09:00:00Z", "snapshot": {"data": {"weather": {"temperature_c": 32.5}}}}]
        cursor = MagicMock()
        cursor.sort.return_value.limit.return_value = docs
        self.snapshots.find.return_value = cursor

        rows = mongo.get_history(13.08, 80.27, "2026-09-03T00:00:00Z", "2026-09-03T23:59:59Z", field="weather.temperature_c")
        self.assertEqual(rows[0]["value"], 32.5)


class TestGetReadingHoursAgo(MongoTestCase):
    def test_picks_closest_document_to_target_time(self):
        target = datetime.now(timezone.utc) - timedelta(hours=24)
        docs = [
            {"timestamp": _iso(target - timedelta(hours=2)), "snapshot": {"data": {"weather": {"temperature_c": 25.0}}}},
            {"timestamp": _iso(target - timedelta(minutes=10)), "snapshot": {"data": {"weather": {"temperature_c": 28.0}}}},
            {"timestamp": _iso(target + timedelta(hours=2)), "snapshot": {"data": {"weather": {"temperature_c": 33.0}}}},
        ]
        cursor = MagicMock()
        cursor.sort.return_value = docs
        self.snapshots.find.return_value = cursor

        data = mongo.get_reading_hours_ago(13.08, 80.27, hours_ago=24, tolerance_hours=3)
        self.assertEqual(data["weather"]["temperature_c"], 28.0)

    def test_returns_none_when_no_docs(self):
        cursor = MagicMock()
        cursor.sort.return_value = []
        self.snapshots.find.return_value = cursor
        self.assertIsNone(mongo.get_reading_hours_ago(13.08, 80.27, 24))


class TestTrendAndPressureChange(unittest.TestCase):
    @patch("mongo_storage.get_reading_hours_ago")
    def test_compute_trend_24h_diffs_fields(self, mock_get_past):
        mock_get_past.return_value = {"weather": {"temperature_c": 29.0}, "air_quality": {"pm25": 30.0}}
        current = {"weather": {"temperature_c": 31.5}, "air_quality": {"pm25": 22.0}}
        trend = mongo.compute_trend_24h(13.08, 80.27, current)
        self.assertEqual(trend["temperature_c"]["change"], "+2.5")
        self.assertEqual(trend["pm25"]["change"], "-8.0")

    @patch("mongo_storage.get_reading_hours_ago")
    def test_compute_trend_24h_none_when_no_history(self, mock_get_past):
        mock_get_past.return_value = None
        self.assertIsNone(mongo.compute_trend_24h(13.08, 80.27, {"weather": {"temperature_c": 30.0}}))

    @patch("mongo_storage.get_reading_hours_ago")
    def test_get_pressure_change_24h(self, mock_get_past):
        mock_get_past.return_value = {"weather": {"pressure_hpa": 1005.0}}
        change = mongo.get_pressure_change_24h(13.08, 80.27, current_pressure_hpa=998.0)
        self.assertEqual(change, -7.0)

    def test_get_pressure_change_24h_none_when_current_missing(self):
        self.assertIsNone(mongo.get_pressure_change_24h(13.08, 80.27, None))


class TestLogAlert(MongoTestCase):
    def test_log_alert_inserts_when_no_existing_match(self):
        self.alerts.find_one.return_value = None
        alert = {"id": "pm25_unhealthy", "severity": "high", "message": "test", "triggered_at": "2026-09-03T10:00:00Z", "value": 60.0}

        result = mongo.log_alert(13.08, 80.27, alert)
        self.assertTrue(result)
        self.alerts.insert_one.assert_called_once()

    def test_log_alert_skips_when_existing_match_found(self):
        self.alerts.find_one.return_value = {"_id": "existing"}
        alert = {"id": "pm25_unhealthy", "severity": "high", "message": "test", "triggered_at": "2026-09-03T10:00:00Z", "value": 60.0}

        result = mongo.log_alert(13.08, 80.27, alert)
        self.assertFalse(result)
        self.alerts.insert_one.assert_not_called()


class TestGetAlertHistory(MongoTestCase):
    def test_no_location_filter_queries_all(self):
        cursor = MagicMock()
        cursor.sort.return_value.limit.return_value = []
        self.alerts.find.return_value = cursor

        mongo.get_alert_history()
        query = self.alerts.find.call_args[0][0]
        self.assertEqual(query, {})

    def test_sorts_descending_and_respects_limit_via_pymongo(self):
        # Unlike CouchDB, MongoDB's find().sort().limit() never rejects the
        # query for lacking a matching index — this asserts we actually use
        # that native sort/limit rather than reimplementing it in Python.
        cursor = MagicMock()
        cursor.sort.return_value.limit.return_value = []
        self.alerts.find.return_value = cursor

        mongo.get_alert_history(13.08, 80.27, limit=5)
        cursor.sort.assert_called_once_with("triggered_at", mongo.DESCENDING)
        cursor.sort.return_value.limit.assert_called_once_with(5)


class TestPruneOldSnapshots(MongoTestCase):
    def test_prune_returns_deleted_count(self):
        result = MagicMock()
        result.deleted_count = 3
        self.snapshots.delete_many.return_value = result

        deleted = mongo.prune_old_snapshots(retention_days=90)
        self.assertEqual(deleted, 3)


class TestIsHealthy(unittest.TestCase):
    @patch("mongo_storage._get_client")
    def test_healthy_on_successful_ping(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        self.assertTrue(mongo.is_healthy())
        mock_client.admin.command.assert_called_once_with("ping")

    @patch("mongo_storage._get_client", side_effect=Exception("connection refused"))
    def test_unhealthy_on_exception(self, mock_get_client):
        self.assertFalse(mongo.is_healthy())


if __name__ == "__main__":
    unittest.main()
