"""
Unit and Integration Tests for FastAPI Application (app.py)
Tests /health, /, /environment, input validation, and mocked responses.
"""

import os
import sys
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app


class TestFastAPIApp(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    def test_root_endpoint(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("service", data)
        self.assertEqual(data["version"], "2.0.0")
        self.assertIn("documentation", data)

    def test_health_endpoint(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertIn("concurrency", data)
        self.assertIn("history_store_status", data)
        self.assertIn("alert_webhook", data)
        self.assertEqual(data["phase"], 2)

    def test_environment_invalid_coordinates_returns_400(self):
        # Lat > 90
        response = self.client.get("/environment?lat=120.0&lon=80.0")
        self.assertEqual(response.status_code, 400)
        detail = response.json().get("detail", {})
        self.assertIn("Latitude must be between -90 and 90", detail.get("message", ""))

        # Lon > 180
        response2 = self.client.get("/environment?lat=13.0&lon=250.0")
        self.assertEqual(response2.status_code, 400)
        detail2 = response2.json().get("detail", {})
        self.assertIn("Longitude must be between -180 and 180", detail2.get("message", ""))

    @patch("app.get_environmental_snapshot")
    def test_environment_success(self, mock_snapshot):
        mock_snapshot.return_value = {
            "location": {"name": "Chennai Coast", "lat": 13.08, "lon": 80.27},
            "generated_at": "2026-09-03T10:00:00Z",
            "data": {
                "weather": {"status": "ok", "temperature_c": 33.0},
                "marine": {"status": "ok", "wave_height_m": 0.8},
                "air_quality": {"status": "ok", "pm25": 22.0},
                "climate_baseline": {"status": "ok", "solar_radiation_kwh_m2": 5.8},
            },
            "meta": {
                "confidence": "high — all sources responded successfully",
                "failed_sources": [],
                "total_latency_ms": 1200.5,
                "source_latencies_ms": {
                    "open-meteo": 450.0,
                    "open-meteo-marine": 520.0,
                    "openaq": 1200.0,
                    "nasa-power": 610.0,
                },
            },
        }

        response = self.client.get("/environment?lat=13.08&lon=80.27&name=Chennai%20Coast")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["location"]["name"], "Chennai Coast")
        self.assertEqual(data["data"]["weather"]["temperature_c"], 33.0)
        self.assertIn("total_latency_ms", data["meta"])
        self.assertEqual(data["meta"]["confidence"], "high — all sources responded successfully")


if __name__ == "__main__":
    unittest.main()
