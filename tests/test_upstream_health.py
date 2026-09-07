"""
Unit and Integration Tests for Upstream Health Monitoring (upstream_health.py & app.py)
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app
import upstream_health


class TestUpstreamHealth(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    @patch("upstream_health.requests.get")
    def test_get_upstream_health_success(self, mock_get):
        # Mock successful response
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp

        health = upstream_health.get_upstream_health()
        self.assertEqual(health["overall_status"], "healthy")
        self.assertEqual(health["healthy_count"], 10)
        self.assertEqual(health["total_count"], 10)
        self.assertEqual(len(health["providers"]), 10)
        self.assertIn("average_latency_ms", health)
        self.assertIn("timestamp", health)

        provider_ids = [p["id"] for p in health["providers"]]
        self.assertIn("open_meteo_weather", provider_ids)
        self.assertIn("open_meteo_marine", provider_ids)
        self.assertIn("openaq_sensors", provider_ids)
        self.assertIn("usgs_seismic", provider_ids)
        self.assertIn("nasa_power", provider_ids)
        self.assertIn("sunrise_sunset", provider_ids)
        self.assertIn("open_elevation", provider_ids)
        self.assertIn("open_meteo_flood", provider_ids)
        self.assertIn("gdacs_disaster", provider_ids)
        self.assertIn("nasa_firms", provider_ids)

    @patch("upstream_health.requests.get")
    def test_get_upstream_health_degraded(self, mock_get):
        # Simulate rate-limit 429
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_get.return_value = mock_resp

        health = upstream_health.get_upstream_health()
        self.assertIn(health["overall_status"], ["degraded", "outage"])
        for p in health["providers"]:
            self.assertEqual(p["status"], "degraded")
            self.assertEqual(p["http_code"], 429)

    @patch("app.check_all_upstream_health")
    def test_api_health_upstream_endpoint(self, mock_get_health):
        mock_get_health.return_value = {
            "timestamp": "2026-09-06T12:00:00Z",
            "overall_status": "healthy",
            "healthy_count": 7,
            "total_count": 7,
            "average_latency_ms": 112.5,
            "providers": [
                {
                    "id": "open_meteo_weather",
                    "name": "Open-Meteo Weather",
                    "category": "Atmospheric & Weather",
                    "status": "healthy",
                    "latency_ms": 95.0,
                    "http_code": 200,
                    "historical_uptime": 99.98,
                    "details": "Active • Verified Telemetry",
                    "docs_url": "https://open-meteo.com/en/docs",
                }
            ]
        }

        res = self.client.get("/api/health/upstream")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["overall_status"], "healthy")
        self.assertEqual(data["healthy_count"], 7)


if __name__ == "__main__":
    unittest.main()
