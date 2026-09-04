"""
Unit tests for the optional CouchDB storage backend (couchdb_storage.py).
No live CouchDB is available in this environment, so every HTTP call is
mocked — these tests validate the request shapes (Mango selectors, doc
structure, bulk-delete payloads) and response parsing, not real CouchDB
wire-compatibility. Verify against an actual instance before relying on this
backend in production (see docs/PHASE2_WALKTHROUGH.md).
"""

import os
import sys
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import couchdb_storage as cdb


def _iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _mock_response(status_code=200, json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        import requests
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(f"{status_code} error")
    return resp


class TestInitDb(unittest.TestCase):
    @patch("couchdb_storage.requests.post")
    @patch("couchdb_storage.requests.put")
    def test_init_db_creates_databases_and_indexes(self, mock_put, mock_post):
        mock_put.return_value = _mock_response(201)
        mock_post.return_value = _mock_response(200, {"result": "created"})

        cdb.init_db()

        self.assertEqual(mock_put.call_count, 2)  # both databases
        # _index calls plus the prune_old_snapshots _find call
        self.assertGreaterEqual(mock_post.call_count, 2)

    @patch("couchdb_storage.requests.post")
    @patch("couchdb_storage.requests.put")
    def test_init_db_tolerates_already_existing_databases(self, mock_put, mock_post):
        mock_put.return_value = _mock_response(412)  # Precondition Failed = already exists
        mock_post.return_value = _mock_response(200, {"docs": []})

        cdb.init_db()  # must not raise


class TestSaveSnapshot(unittest.TestCase):
    @patch("couchdb_storage.requests.post")
    def test_save_snapshot_posts_expected_document_shape(self, mock_post):
        mock_post.return_value = _mock_response(201, {"ok": True})

        snapshot = {"generated_at": "2026-09-03T10:00:00Z", "data": {"weather": {"temperature_c": 30.0}}}
        cdb.save_snapshot(13.08, 80.27, "Chennai Coast", snapshot)

        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        doc = kwargs["json"]
        self.assertEqual(doc["lat"], 13.08)
        self.assertEqual(doc["lon"], 80.27)
        self.assertEqual(doc["name"], "Chennai Coast")
        self.assertEqual(doc["snapshot"], snapshot)
        self.assertTrue(doc["_id"].startswith("snapshot:13.08:80.27:"))


class TestGetHistory(unittest.TestCase):
    @patch("couchdb_storage.requests.post")
    def test_get_history_builds_range_selector_and_parses_docs(self, mock_post):
        docs = [
            {"timestamp": "2026-09-03T09:00:00Z", "snapshot": {"data": {"weather": {"temperature_c": 30.0}}}},
            {"timestamp": "2026-09-03T10:00:00Z", "snapshot": {"data": {"weather": {"temperature_c": 31.0}}}},
        ]
        mock_post.return_value = _mock_response(200, {"docs": docs})

        rows = cdb.get_history(13.08, 80.27, "2026-09-03T00:00:00Z", "2026-09-03T23:59:59Z")

        _, kwargs = mock_post.call_args
        selector = kwargs["json"]["selector"]
        self.assertEqual(selector["lat"], 13.08)
        self.assertEqual(selector["timestamp"], {"$gte": "2026-09-03T00:00:00Z", "$lte": "2026-09-03T23:59:59Z"})
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["data"]["weather"]["temperature_c"], 30.0)

    @patch("couchdb_storage.requests.post")
    def test_get_history_with_field_extracts_value(self, mock_post):
        docs = [{"timestamp": "2026-09-03T09:00:00Z", "snapshot": {"data": {"weather": {"temperature_c": 32.5}}}}]
        mock_post.return_value = _mock_response(200, {"docs": docs})

        rows = cdb.get_history(13.08, 80.27, "2026-09-03T00:00:00Z", "2026-09-03T23:59:59Z", field="weather.temperature_c")
        self.assertEqual(rows[0]["value"], 32.5)

    @patch("couchdb_storage.requests.post")
    def test_get_history_empty_result(self, mock_post):
        mock_post.return_value = _mock_response(200, {"docs": []})
        rows = cdb.get_history(13.08, 80.27, "2000-01-01T00:00:00Z", "2000-01-02T00:00:00Z")
        self.assertEqual(rows, [])


class TestGetReadingHoursAgo(unittest.TestCase):
    @patch("couchdb_storage.requests.post")
    def test_picks_closest_document_to_target_time(self, mock_post):
        target = datetime.now(timezone.utc) - timedelta(hours=24)
        docs = [
            {"timestamp": _iso(target - timedelta(hours=2)), "snapshot": {"data": {"weather": {"temperature_c": 25.0}}}},
            {"timestamp": _iso(target - timedelta(minutes=10)), "snapshot": {"data": {"weather": {"temperature_c": 28.0}}}},
            {"timestamp": _iso(target + timedelta(hours=2)), "snapshot": {"data": {"weather": {"temperature_c": 33.0}}}},
        ]
        mock_post.return_value = _mock_response(200, {"docs": docs})

        data = cdb.get_reading_hours_ago(13.08, 80.27, hours_ago=24, tolerance_hours=3)
        self.assertEqual(data["weather"]["temperature_c"], 28.0)  # the -10min row is closest

    @patch("couchdb_storage.requests.post")
    def test_returns_none_when_no_docs(self, mock_post):
        mock_post.return_value = _mock_response(200, {"docs": []})
        self.assertIsNone(cdb.get_reading_hours_ago(13.08, 80.27, 24))


class TestTrendAndPressureChange(unittest.TestCase):
    @patch("couchdb_storage.get_reading_hours_ago")
    def test_compute_trend_24h_diffs_fields(self, mock_get_past):
        mock_get_past.return_value = {"weather": {"temperature_c": 29.0}, "air_quality": {"pm25": 30.0}}
        current = {"weather": {"temperature_c": 31.5}, "air_quality": {"pm25": 22.0}}

        trend = cdb.compute_trend_24h(13.08, 80.27, current)
        self.assertEqual(trend["temperature_c"]["change"], "+2.5")
        self.assertEqual(trend["pm25"]["change"], "-8.0")

    @patch("couchdb_storage.get_reading_hours_ago")
    def test_compute_trend_24h_none_when_no_history(self, mock_get_past):
        mock_get_past.return_value = None
        self.assertIsNone(cdb.compute_trend_24h(13.08, 80.27, {"weather": {"temperature_c": 30.0}}))

    @patch("couchdb_storage.get_reading_hours_ago")
    def test_get_pressure_change_24h(self, mock_get_past):
        mock_get_past.return_value = {"weather": {"pressure_hpa": 1005.0}}
        change = cdb.get_pressure_change_24h(13.08, 80.27, current_pressure_hpa=998.0)
        self.assertEqual(change, -7.0)

    def test_get_pressure_change_24h_none_when_current_missing(self):
        self.assertIsNone(cdb.get_pressure_change_24h(13.08, 80.27, None))


class TestLogAlert(unittest.TestCase):
    @patch("couchdb_storage.requests.post")
    def test_log_alert_inserts_when_no_existing_match(self, mock_post):
        # First call: _find (empty) ; second call: insert doc.
        mock_post.side_effect = [_mock_response(200, {"docs": []}), _mock_response(201, {"ok": True})]

        alert = {"id": "pm25_unhealthy", "severity": "high", "message": "test", "triggered_at": "2026-09-03T10:00:00Z", "value": 60.0}
        result = cdb.log_alert(13.08, 80.27, alert)
        self.assertTrue(result)
        self.assertEqual(mock_post.call_count, 2)

    @patch("couchdb_storage.requests.post")
    def test_log_alert_skips_when_existing_match_found(self, mock_post):
        mock_post.return_value = _mock_response(200, {"docs": [{"_id": "alert:13.08:80.27:pm25_unhealthy:abcd1234"}]})

        alert = {"id": "pm25_unhealthy", "severity": "high", "message": "test", "triggered_at": "2026-09-03T10:00:00Z", "value": 60.0}
        result = cdb.log_alert(13.08, 80.27, alert)
        self.assertFalse(result)
        self.assertEqual(mock_post.call_count, 1)  # only the _find, no insert


class TestGetAlertHistory(unittest.TestCase):
    """Regression coverage for a real bug found by testing against a live
    CouchDB instance: Mango's _find rejects `sort` unless a matching index
    exists for that exact selector+sort shape (confirmed live — sorting by
    triggered_at alone doesn't match the (lat, lon, rule_id, triggered_at)
    index). get_alert_history must NOT pass `sort` to _find, and must sort
    the results in Python instead.
    """

    @patch("couchdb_storage.requests.post")
    def test_does_not_pass_sort_to_mango_find(self, mock_post):
        mock_post.return_value = _mock_response(200, {"docs": []})
        cdb.get_alert_history(13.08, 80.27)

        _, kwargs = mock_post.call_args
        self.assertNotIn("sort", kwargs["json"])

    @patch("couchdb_storage.requests.post")
    def test_sorts_results_by_triggered_at_descending_in_python(self, mock_post):
        docs = [
            {"lat": 13.08, "lon": 80.27, "rule_id": "a", "triggered_at": "2026-09-01T00:00:00Z", "value": 1},
            {"lat": 13.08, "lon": 80.27, "rule_id": "b", "triggered_at": "2026-09-03T00:00:00Z", "value": 2},
            {"lat": 13.08, "lon": 80.27, "rule_id": "c", "triggered_at": "2026-09-02T00:00:00Z", "value": 3},
        ]
        mock_post.return_value = _mock_response(200, {"docs": docs})

        result = cdb.get_alert_history(13.08, 80.27)
        self.assertEqual([r["rule_id"] for r in result], ["b", "c", "a"])

    @patch("couchdb_storage.requests.post")
    def test_respects_limit_after_sorting(self, mock_post):
        docs = [{"lat": 13.08, "lon": 80.27, "rule_id": f"r{i}", "triggered_at": f"2026-09-0{i}T00:00:00Z"} for i in range(1, 6)]
        mock_post.return_value = _mock_response(200, {"docs": docs})

        result = cdb.get_alert_history(13.08, 80.27, limit=2)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["rule_id"], "r5")  # most recent first

    @patch("couchdb_storage.requests.post")
    def test_no_location_filter_queries_all(self, mock_post):
        mock_post.return_value = _mock_response(200, {"docs": []})
        cdb.get_alert_history()

        _, kwargs = mock_post.call_args
        selector = kwargs["json"]["selector"]
        self.assertNotIn("lat", selector)
        self.assertNotIn("lon", selector)


class TestPruneOldSnapshots(unittest.TestCase):
    @patch("couchdb_storage.requests.post")
    def test_prune_bulk_deletes_stale_docs(self, mock_post):
        stale_docs = [
            {"_id": "snapshot:13.08:80.27:old1", "_rev": "1-abc"},
            {"_id": "snapshot:13.08:80.27:old2", "_rev": "1-def"},
        ]
        mock_post.side_effect = [_mock_response(200, {"docs": stale_docs}), _mock_response(201, [{"ok": True}, {"ok": True}])]

        deleted = cdb.prune_old_snapshots(retention_days=90)
        self.assertEqual(deleted, 2)

        _, kwargs = mock_post.call_args
        bulk_docs = kwargs["json"]["docs"]
        self.assertTrue(all(d["_deleted"] is True for d in bulk_docs))

    @patch("couchdb_storage.requests.post")
    def test_prune_no_stale_docs_returns_zero(self, mock_post):
        mock_post.return_value = _mock_response(200, {"docs": []})
        self.assertEqual(cdb.prune_old_snapshots(), 0)


class TestPruneOldAlerts(unittest.TestCase):
    """alerts_log needs the same retention pruning as snapshots — without it,
    the alerts database grows unbounded forever.
    """

    @patch("couchdb_storage.requests.post")
    def test_prune_bulk_deletes_stale_alert_docs(self, mock_post):
        stale_docs = [{"_id": "alert:13.08:80.27:pm25_unhealthy:old1", "_rev": "1-abc"}]
        mock_post.side_effect = [_mock_response(200, {"docs": stale_docs}), _mock_response(201, [{"ok": True}])]

        deleted = cdb.prune_old_alerts(retention_days=90)
        self.assertEqual(deleted, 1)

        _, kwargs = mock_post.call_args
        bulk_docs = kwargs["json"]["docs"]
        self.assertTrue(all(d["_deleted"] is True for d in bulk_docs))

    @patch("couchdb_storage.requests.post")
    def test_prune_no_stale_alerts_returns_zero(self, mock_post):
        mock_post.return_value = _mock_response(200, {"docs": []})
        self.assertEqual(cdb.prune_old_alerts(), 0)


class TestIsHealthy(unittest.TestCase):
    @patch("couchdb_storage.requests.get")
    def test_healthy_on_200(self, mock_get):
        mock_get.return_value = _mock_response(200)
        self.assertTrue(cdb.is_healthy())

    @patch("couchdb_storage.requests.get", side_effect=Exception("connection refused"))
    def test_unhealthy_on_exception(self, mock_get):
        self.assertFalse(cdb.is_healthy())


if __name__ == "__main__":
    unittest.main()
