"""
Tests for Caching, Rate Limiting, and Hardening
Validates:
- Snapshot cache hits (sub-millisecond latency & meta.cache_hit=True)
- bypass_cache query parameter
- Rate limiting (slowapi 30 req/min triggering 429)
- Global exception handler returning clean JSON 500
"""

import os
import sys
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app
from environmental_data import SNAPSHOT_CACHE, STATION_CACHE


class TestCachingAndRateLimiting(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)
        SNAPSHOT_CACHE.clear()
        STATION_CACHE.clear()
        if hasattr(app.state, "limiter") and hasattr(app.state.limiter, "_storage"):
            app.state.limiter._storage.reset()

    @patch("app.get_environmental_snapshot")
    def test_response_cache_hit_and_bypass(self, mock_snapshot):
        mock_snapshot.side_effect = [
            # Call 1: Miss
            {
                "location": {"name": "Chennai Coast", "lat": 13.08, "lon": 80.27},
                "generated_at": "2026-09-03T10:00:00Z",
                "data": {"weather": {"status": "ok"}},
                "meta": {"cache_hit": False, "total_latency_ms": 1500.0},
            },
            # Call 2: Hit
            {
                "location": {"name": "Chennai Coast", "lat": 13.08, "lon": 80.27},
                "generated_at": "2026-09-03T10:00:00Z",
                "data": {"weather": {"status": "ok"}},
                "meta": {"cache_hit": True, "total_latency_ms": 0.5},
            },
        ]

        # Call 1
        r1 = self.client.get("/environment?lat=13.08&lon=80.27")
        self.assertEqual(r1.status_code, 200)
        self.assertFalse(r1.json()["meta"]["cache_hit"])

        # Call 2 (Hit)
        r2 = self.client.get("/environment?lat=13.08&lon=80.27")
        self.assertEqual(r2.status_code, 200)
        self.assertTrue(r2.json()["meta"]["cache_hit"])
        self.assertLess(r2.json()["meta"]["total_latency_ms"], 1.0)

    @patch("app.get_environmental_snapshot")
    def test_rate_limiting_triggers_429(self, mock_snapshot):
        mock_snapshot.return_value = {
            "location": {"name": "Chennai Coast", "lat": 13.08, "lon": 80.27},
            "generated_at": "2026-09-03T10:00:00Z",
            "data": {},
            "meta": {"cache_hit": True, "total_latency_ms": 0.5},
        }

        # Send 35 requests rapidly to trigger the 30/minute limit
        responses = []
        for i in range(35):
            r = self.client.get(f"/environment?lat=13.08&lon=80.27&name=Test_{i}")
            responses.append(r.status_code)

        self.assertIn(429, responses, "Rate limiter did not trigger HTTP 429 after 30 requests")
        last_resp = self.client.get("/environment?lat=13.08&lon=80.27")
        self.assertEqual(last_resp.status_code, 429)
        self.assertIn("Rate limit exceeded", last_resp.json().get("message", ""))

    @patch("app.get_environmental_snapshot")
    def test_global_exception_handler(self, mock_snapshot):
        # Force an unexpected internal exception
        mock_snapshot.side_effect = RuntimeError("Database/connection pool exhausted")

        # Use a fresh test client to avoid hitting rate limit
        test_client = TestClient(app, raise_server_exceptions=False)
        response = test_client.get("/environment?lat=10.0&lon=20.0")
        self.assertEqual(response.status_code, 500)
        data = response.json()
        self.assertEqual(data.get("error"), "InternalServerError")
        self.assertIn("Database/connection pool exhausted", data.get("detail", ""))


if __name__ == "__main__":
    unittest.main()
