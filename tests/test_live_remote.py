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

    @classmethod
    def setUpClass(cls):
        try:
            r = requests.get(f"{BASE_URL}/health", timeout=5)
            if r.status_code != 200:
                raise unittest.SkipTest(f"Server at {BASE_URL} returned status {r.status_code}. Skipping remote live tests.")
        except Exception as e:
            raise unittest.SkipTest(f"Live server at {BASE_URL} is not reachable ({e}). Skipping remote live tests.")

    def test_01_health_check(self):
        url = f"{BASE_URL}/health"
        r = requests.get(url, timeout=20)
        self.assertEqual(r.status_code, 200, f"Expected 200 from {url}, got {r.status_code}: {r.text}")
        data = r.json()
        self.assertEqual(data.get("status"), "healthy")
        self.assertEqual(data.get("service"), "environmental-intelligence-api")

    def test_02_environment_endpoint(self):
        url = f"{BASE_URL}/environment"
        params = {"lat": 13.08, "lon": 80.27, "name": "Chennai Coast", "bypass_cache": "true"}
        r = requests.get(url, params=params, timeout=25)
        self.assertEqual(r.status_code, 200, f"Expected 200 from {url}, got {r.status_code}: {r.text}")
        data = r.json()
        self.assertIn("location", data)
        self.assertIn("data", data)
        self.assertIn("meta", data)
        self.assertIn("river_flood", data["data"])
        self.assertIn("cyclone_tracking", data["data"])
        self.assertIn("thermal_hotspots", data["data"])
        self.assertIn(data["data"]["river_flood"]["status"], ["ok", "error"])
        self.assertIn(data["data"]["cyclone_tracking"]["status"], ["ok", "error"])
        self.assertIn(data["data"]["thermal_hotspots"]["status"], ["ok", "error"])
        if data["data"]["air_quality"].get("status") == "ok":
            self.assertIn(data["data"]["air_quality"].get("data_type"), ["measured", "modeled"])
        self.assertTrue(
            data["meta"]["confidence"].startswith("high") or data["meta"]["confidence"].startswith("partial"),
            f"Unexpected confidence string: {data['meta']['confidence']}"
        )
        self.assertIn("cyclone_advisory", data.get("meta", {}).get("derived_insights", {}))
        self.assertIn("air_quality_causality", data.get("meta", {}).get("derived_insights", {}))

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

    def test_05_openaq_fallback_remote(self):
        """Query offshore coordinates where OpenAQ has no ground station (e.g. 10.0, 72.0)
        and verify that the Open-Meteo Modeled Air Quality fallback fires with modeled provenance."""
        url = f"{BASE_URL}/environment"
        params = {"lat": 10.0, "lon": 72.0, "name": "Lakshadweep Offshore", "bypass_cache": "true"}
        r = requests.get(url, params=params, timeout=25)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        aq = data.get("data", {}).get("air_quality", {})
        self.assertEqual(aq.get("status"), "ok")
        self.assertEqual(aq.get("source"), "open-meteo-air-quality-modeled")
        self.assertEqual(aq.get("data_type"), "modeled")
        self.assertIsNotNone(aq.get("pm25"))

    def test_06_river_flood_discharge_kolkata(self):
        """Query Kolkata delta coordinates (22.57, 88.36) where GloFAS river basin is mapped
        and verify active river discharge data is populated."""
        url = f"{BASE_URL}/environment"
        params = {"lat": 22.57, "lon": 88.36, "name": "Kolkata Hooghly Estuary", "bypass_cache": "true"}
        r = requests.get(url, params=params, timeout=25)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        rf = data.get("data", {}).get("river_flood", {})
        self.assertEqual(rf.get("status"), "ok")
        self.assertTrue(rf.get("applicable"))
        self.assertIsNotNone(rf.get("river_discharge_m3s"))
        self.assertGreater(rf.get("river_discharge_m3s"), 0.0)

    def test_07_cyclone_tracking_gdacs_remote(self):
        """Verify GDACS cyclone feed responds live and structures cyclone tracking data."""
        url = f"{BASE_URL}/environment"
        params = {"lat": 13.08, "lon": 80.27, "name": "Chennai Coast", "bypass_cache": "true"}
        r = requests.get(url, params=params, timeout=25)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        ct = data.get("data", {}).get("cyclone_tracking", {})
        self.assertIn(ct.get("status"), ["ok", "error"])
        if ct.get("status") == "ok":
            self.assertIn("active_cyclones_count", ct)
            self.assertIn("nearest_cyclone_name", ct)
            self.assertIn("nearest_cyclone_distance_km", ct)
            self.assertIn("cyclone_alert_level", ct)
            advisory = data.get("meta", {}).get("derived_insights", {}).get("cyclone_advisory", {})
            self.assertIn("level", advisory)

    def test_08_thermal_hotspots_firms_remote(self):
        """Verify NASA FIRMS thermal hotspot feed responds live and computes causality."""
        url = f"{BASE_URL}/environment"
        params = {"lat": 22.57, "lon": 88.36, "name": "Kolkata Hooghly Estuary", "bypass_cache": "true"}
        r = requests.get(url, params=params, timeout=25)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        th = data.get("data", {}).get("thermal_hotspots", {})
        self.assertIn(th.get("status"), ["ok", "error"])
        if th.get("status") == "ok":
            self.assertIn("hotspot_count", th)
            self.assertIn("fire_detected", th)
            self.assertIn("search_radius_km", th)
            causality = data.get("meta", {}).get("derived_insights", {}).get("air_quality_causality", {})
            self.assertIn("biomass_burning_detected", causality)
            self.assertIn("causal_attribution", causality)

    def test_09_upstream_health_ten_providers(self):
        """Verify the /api/health/upstream endpoint lists all 10 distinct providers."""
        url = f"{BASE_URL}/api/health/upstream"
        r = requests.get(url, timeout=25)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data.get("total_providers"), 10)
        provider_ids = [p["id"] for p in data.get("providers", [])]
        self.assertIn("gdacs_disaster", provider_ids)
        self.assertIn("nasa_firms", provider_ids)


if __name__ == "__main__":
    unittest.main()

