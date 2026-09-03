"""
Mocked integration tests for the Phase 2 API surface: /locations,
/environment/history, /alerts, and the new meta fields on /environment
(derived_insights, trend_24h, active_alerts). No live network calls — every
upstream fetch goes through a patched get_environmental_snapshot, and storage
is redirected to an isolated temp SQLite file per test.
"""

import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import storage
from app import app


def _iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


SQUALL_SNAPSHOT = {
    "location": {"name": "Chennai Coast", "lat": 13.08, "lon": 80.27},
    "generated_at": "2026-10-18T06:30:00Z",
    "data": {
        "weather": {
            "status": "ok", "temperature_c": 26.2, "humidity_pct": 94,
            "wind_speed_kmh": 42.5, "pressure_hpa": 998.2, "precipitation_mm": 54.0,
        },
        "marine": {"status": "ok", "wave_height_m": 2.85},
        "air_quality": {"status": "ok", "pm25": 14.2},
    },
    "meta": {"confidence": "high — all sources responded successfully", "failed_sources": [], "cache_hit": False, "total_latency_ms": 900.0},
}

CALM_SNAPSHOT = {
    "location": {"name": "Test Point", "lat": 13.08, "lon": 80.27},
    "generated_at": "2026-09-03T10:00:00Z",
    "data": {
        "weather": {"status": "ok", "temperature_c": 28.0, "humidity_pct": 60.0, "wind_speed_kmh": 10.0, "pressure_hpa": 1012.0, "precipitation_mm": 0.0},
        "marine": {"status": "ok", "wave_height_m": 0.5},
        "air_quality": {"status": "ok", "pm25": 15.0},
    },
    "meta": {"confidence": "high — all sources responded successfully", "failed_sources": [], "cache_hit": False, "total_latency_ms": 800.0},
}


class Phase2EndpointTestCase(unittest.TestCase):
    def setUp(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self._tmp_path = path
        self._orig_db_path = storage.DB_PATH
        storage.DB_PATH = path
        storage.init_db()

        self.client = TestClient(app)
        if hasattr(app.state, "limiter") and hasattr(app.state.limiter, "_storage"):
            app.state.limiter._storage.reset()

    def tearDown(self):
        storage.DB_PATH = self._orig_db_path
        try:
            os.remove(self._tmp_path)
        except OSError:
            pass


class TestLocationsEndpoint(Phase2EndpointTestCase):
    def test_locations_endpoint_returns_registry(self):
        r = self.client.get("/locations")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertGreaterEqual(data["count"], 5)
        names = {loc["name"] for loc in data["locations"]}
        self.assertIn("Chennai Coast", names)


class TestEnvironmentMetaAdditions(Phase2EndpointTestCase):
    @patch("app.get_environmental_snapshot")
    def test_environment_includes_derived_insights_and_active_alerts(self, mock_snapshot):
        mock_snapshot.return_value = dict(SQUALL_SNAPSHOT)

        r = self.client.get("/environment?lat=13.08&lon=80.27&name=Chennai%20Coast")
        self.assertEqual(r.status_code, 200)
        data = r.json()

        self.assertIn("derived_insights", data["meta"])
        self.assertIn("small_craft_risk_level", data["meta"]["derived_insights"])

        self.assertIn("active_alerts", data["meta"])
        alert_ids = {a["id"] for a in data["meta"]["active_alerts"]}
        self.assertIn("small_craft_unsafe", alert_ids)

    @patch("app.get_environmental_snapshot")
    def test_environment_calm_data_has_no_active_alerts(self, mock_snapshot):
        mock_snapshot.return_value = dict(CALM_SNAPSHOT)

        r = self.client.get("/environment?lat=13.08&lon=80.27")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["meta"]["active_alerts"], [])

    @patch("app.get_environmental_snapshot")
    def test_environment_persists_fresh_snapshot_to_history(self, mock_snapshot):
        snap = dict(CALM_SNAPSHOT)
        snap["generated_at"] = _iso(datetime.now(timezone.utc))
        mock_snapshot.return_value = snap

        r = self.client.get("/environment?lat=13.08&lon=80.27")
        self.assertEqual(r.status_code, 200)

        now = datetime.now(timezone.utc)
        rows = storage.get_history(
            13.08, 80.27,
            _iso(now - timedelta(minutes=5)),
            _iso(now + timedelta(minutes=5)),
        )
        self.assertEqual(len(rows), 1)

    @patch("app.get_environmental_snapshot")
    def test_environment_cache_hit_is_not_persisted(self, mock_snapshot):
        cached = dict(CALM_SNAPSHOT)
        cached["meta"] = dict(CALM_SNAPSHOT["meta"])
        cached["meta"]["cache_hit"] = True
        mock_snapshot.return_value = cached

        r = self.client.get("/environment?lat=13.08&lon=80.27")
        self.assertEqual(r.status_code, 200)

        now = datetime.now(timezone.utc)
        rows = storage.get_history(
            13.08, 80.27,
            _iso(now - timedelta(minutes=5)),
            _iso(now + timedelta(minutes=5)),
        )
        self.assertEqual(len(rows), 0)

    @patch("app.get_environmental_snapshot")
    def test_environment_includes_trend_when_history_exists(self, mock_snapshot):
        past_time = datetime.now(timezone.utc) - timedelta(hours=24)
        past_snapshot = dict(CALM_SNAPSHOT)
        past_snapshot["generated_at"] = _iso(past_time)
        storage.save_snapshot(13.08, 80.27, "Test Point", past_snapshot)

        current = dict(CALM_SNAPSHOT)
        current["data"] = dict(CALM_SNAPSHOT["data"])
        current["data"]["weather"] = dict(CALM_SNAPSHOT["data"]["weather"])
        current["data"]["weather"]["temperature_c"] = 31.0
        mock_snapshot.return_value = current

        r = self.client.get("/environment?lat=13.08&lon=80.27")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("trend_24h", data["meta"])
        self.assertEqual(data["meta"]["trend_24h"]["temperature_c"]["current"], 31.0)
        self.assertEqual(data["meta"]["trend_24h"]["temperature_c"]["previous"], 28.0)


class TestHistoryEndpoint(Phase2EndpointTestCase):
    def test_history_returns_stored_readings(self):
        now = datetime.now(timezone.utc)
        storage.save_snapshot(13.08, 80.27, "Chennai Coast", dict(CALM_SNAPSHOT, generated_at=_iso(now)))

        r = self.client.get(
            "/environment/history",
            params={
                "lat": 13.08, "lon": 80.27,
                "start": _iso(now - timedelta(hours=1)),
                "end": _iso(now + timedelta(hours=1)),
            },
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["count"], 1)

    def test_history_with_field_filter(self):
        now = datetime.now(timezone.utc)
        storage.save_snapshot(13.08, 80.27, "Chennai Coast", dict(CALM_SNAPSHOT, generated_at=_iso(now)))

        r = self.client.get(
            "/environment/history",
            params={"lat": 13.08, "lon": 80.27, "field": "weather.temperature_c"},
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["history"][0]["value"], 28.0)

    def test_history_defaults_to_last_7_days_when_no_range_given(self):
        r = self.client.get("/environment/history", params={"lat": 13.08, "lon": 80.27})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("start", data)
        self.assertIn("end", data)

    def test_history_invalid_coordinates_returns_400(self):
        r = self.client.get("/environment/history", params={"lat": 999.0, "lon": 80.27})
        self.assertEqual(r.status_code, 400)

    def test_history_start_after_end_returns_400(self):
        now = datetime.now(timezone.utc)
        r = self.client.get(
            "/environment/history",
            params={
                "lat": 13.08, "lon": 80.27,
                "start": _iso(now),
                "end": _iso(now - timedelta(days=1)),
            },
        )
        self.assertEqual(r.status_code, 400)


class TestAlertsEndpoint(Phase2EndpointTestCase):
    @patch("app.get_environmental_snapshot")
    def test_alerts_single_location_query(self, mock_snapshot):
        mock_snapshot.return_value = dict(SQUALL_SNAPSHOT)

        r = self.client.get("/alerts?lat=13.08&lon=80.27")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["locations_checked"], 1)
        self.assertGreater(data["active_alert_count"], 0)
        self.assertIn("location", data["active_alerts"][0])

    @patch("app.get_environmental_snapshot")
    def test_alerts_full_registry_scan(self, mock_snapshot):
        mock_snapshot.return_value = dict(SQUALL_SNAPSHOT)

        r = self.client.get("/alerts")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertGreaterEqual(data["locations_checked"], 5)
        self.assertGreater(data["active_alert_count"], 0)

    @patch("app.get_environmental_snapshot")
    def test_alerts_calm_conditions_return_none(self, mock_snapshot):
        mock_snapshot.return_value = dict(CALM_SNAPSHOT)

        r = self.client.get("/alerts")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["active_alert_count"], 0)

    def test_alerts_lat_without_lon_returns_400(self):
        r = self.client.get("/alerts?lat=13.08")
        self.assertEqual(r.status_code, 400)


if __name__ == "__main__":
    unittest.main()
