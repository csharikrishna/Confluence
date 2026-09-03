"""
Remote Live Deployment Verification Suite
Use this script to verify the live deployed service (e.g. Render / Railway):
  $env:API_BASE_URL = "https://your-app.onrender.com"
  pytest tests/test_live_remote.py -v
"""

import os
import time
import requests
import unittest

BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


class TestLiveDeployment(unittest.TestCase):

    def test_01_health_check(self):
        url = f"{BASE_URL}/health"
        r = requests.get(url, timeout=20)
        self.assertEqual(r.status_code, 200, f"Expected 200 from {url}, got {r.status_code}: {r.text}")
        data = r.json()
        self.assertEqual(data.get("status"), "healthy")
        self.assertEqual(data.get("service"), "environmental-intelligence-api")

    def test_02_environment_endpoint(self):
        url = f"{BASE_URL}/environment"
        params = {"lat": 13.08, "lon": 80.27, "name": "Chennai Coast"}
        r = requests.get(url, params=params, timeout=25)
        self.assertEqual(r.status_code, 200, f"Expected 200 from {url}, got {r.status_code}: {r.text}")
        data = r.json()
        self.assertIn("location", data)
        self.assertIn("data", data)
        self.assertIn("meta", data)
        self.assertIn(data["meta"]["confidence"], [
            "high — all sources responded successfully",
            "partial — openaq failed, other sources ok",
        ])

    def test_03_cache_hit_on_subsequent_request(self):
        url = f"{BASE_URL}/environment"
        params = {"lat": 13.08, "lon": 80.27, "name": "Chennai Coast"}
        # Immediate follow-up query should hit cache
        r = requests.get(url, params=params, timeout=10)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data["meta"].get("cache_hit"), "Expected cache_hit to be true on repeated query")
        self.assertLess(data["meta"].get("total_latency_ms", 9999), 100.0, "Expected sub-100ms response on cached hit")

    def test_04_invalid_coordinates_rejected(self):
        url = f"{BASE_URL}/environment"
        params = {"lat": 120.0, "lon": 80.27}
        r = requests.get(url, params=params, timeout=10)
        self.assertEqual(r.status_code, 400)


if __name__ == "__main__":
    unittest.main()
