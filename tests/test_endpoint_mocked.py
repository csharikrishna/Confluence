"""
Unit Test Suite with Mocking (Group D - Task #11 & #12)
Tests endpoint normalization, sanity-checking, coordinate validation,
partial failure handling, and latency logging completely offline.
"""

import os
import sys
import unittest
import requests
from unittest.mock import patch, MagicMock

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from env_intelligence_test import (
    get_environmental_snapshot,
    fetch_weather,
    fetch_marine,
    fetch_air_quality,
    fetch_climate_baseline,
    validate_coordinates,
    validate_environmental_data,
    normalize_iso_utc,
)


class TestEnvironmentalIntelligence(unittest.TestCase):

    # -----------------------------------------------------------------------
    # Unit tests for helper functions
    # -----------------------------------------------------------------------

    def test_coordinate_validation(self):
        # Valid coordinates
        valid, _ = validate_coordinates(13.08, 80.27)
        self.assertTrue(valid)
        valid, _ = validate_coordinates(-90, 180)
        self.assertTrue(valid)
        valid, _ = validate_coordinates(0, 0)
        self.assertTrue(valid)

        # Invalid coordinates
        valid, err = validate_coordinates(95.0, 80.0)
        self.assertFalse(valid)
        self.assertIn("Latitude must be between -90 and 90", err)

        valid, err = validate_coordinates(13.0, 200.0)
        self.assertFalse(valid)
        self.assertIn("Longitude must be between -180 and 180", err)

        valid, err = validate_coordinates("abc", 80.0)
        self.assertFalse(valid)
        self.assertIn("must be numeric", err)

    def test_timestamp_normalization(self):
        # ISO formats
        self.assertEqual(normalize_iso_utc("2026-09-03T07:15"), "2026-09-03T07:15:00Z")
        self.assertEqual(normalize_iso_utc("2026-09-03T07:15:30"), "2026-09-03T07:15:30Z")
        self.assertEqual(normalize_iso_utc("2026-09-03T07:15:00Z"), "2026-09-03T07:15:00Z")
        self.assertEqual(normalize_iso_utc("20260903"), "20260903T00:00:00Z")
        self.assertIsNone(normalize_iso_utc(None))

    # -----------------------------------------------------------------------
    # Dedicated unit tests for validate_environmental_data (Task #8)
    # -----------------------------------------------------------------------

    def test_validate_clean_data_returns_no_warnings(self):
        clean_data = {
            "weather": {"status": "ok", "temperature_c": 32.0, "humidity_pct": 65.0, "pressure_hpa": 1010.0, "wind_speed_kmh": 12.0, "precipitation_mm": 0.0},
            "marine": {"status": "ok", "sea_surface_temp_c": 29.0, "wave_height_m": 0.8},
            "air_quality": {"status": "ok", "pm25": 25.0, "pm10": 45.0, "o3": 20.0, "no2": 15.0, "so2": 5.0, "co": 1.0},
            "climate_baseline": {"status": "ok", "solar_radiation_kwh_m2": 5.5},
        }
        self.assertEqual(validate_environmental_data(clean_data), [])

    def test_validate_weather_temperature_bounds(self):
        # Above maximum threshold (60°C)
        hot_data = {"weather": {"status": "ok", "temperature_c": 75.0}}
        warn_hot = validate_environmental_data(hot_data)
        self.assertEqual(len(warn_hot), 1)
        self.assertIn("Temperature 75.0°C outside physical bounds", warn_hot[0])

        # Below minimum threshold (-50°C)
        cold_data = {"weather": {"status": "ok", "temperature_c": -65.0}}
        warn_cold = validate_environmental_data(cold_data)
        self.assertEqual(len(warn_cold), 1)
        self.assertIn("Temperature -65.0°C outside physical bounds", warn_cold[0])

    def test_validate_weather_humidity_and_pressure_bounds(self):
        # Humidity > 100% or < 0%
        hum_high = {"weather": {"status": "ok", "humidity_pct": 125.0}}
        warn_hum = validate_environmental_data(hum_high)
        self.assertEqual(len(warn_hum), 1)
        self.assertIn("Humidity 125.0% outside physical bounds", warn_hum[0])

        hum_neg = {"weather": {"status": "ok", "humidity_pct": -5.0}}
        warn_neg = validate_environmental_data(hum_neg)
        self.assertEqual(len(warn_neg), 1)

        # Pressure out of bounds (<850 or >1090)
        p_low = {"weather": {"status": "ok", "pressure_hpa": 800.0}}
        self.assertEqual(len(validate_environmental_data(p_low)), 1)
        p_high = {"weather": {"status": "ok", "pressure_hpa": 1150.0}}
        self.assertEqual(len(validate_environmental_data(p_high)), 1)

    def test_validate_negative_wind_and_rain(self):
        wind_neg = {"weather": {"status": "ok", "wind_speed_kmh": -10.0}}
        warn_w = validate_environmental_data(wind_neg)
        self.assertEqual(len(warn_w), 1)
        self.assertIn("Wind speed -10.0 km/h cannot be negative", warn_w[0])

        rain_neg = {"weather": {"status": "ok", "precipitation_mm": -2.0}}
        warn_r = validate_environmental_data(rain_neg)
        self.assertEqual(len(warn_r), 1)
        self.assertIn("Precipitation -2.0 mm cannot be negative", warn_r[0])

    def test_validate_marine_bounds(self):
        sst_hot = {"marine": {"status": "ok", "sea_surface_temp_c": 50.0}}
        warn_sst = validate_environmental_data(sst_hot)
        self.assertEqual(len(warn_sst), 1)
        self.assertIn("Sea surface temperature 50.0°C outside physical bounds", warn_sst[0])

        wave_neg = {"marine": {"status": "ok", "wave_height_m": -1.5}}
        warn_wave = validate_environmental_data(wave_neg)
        self.assertEqual(len(warn_wave), 1)
        self.assertIn("Wave height -1.5 m cannot be negative", warn_wave[0])

    def test_validate_air_quality_negative_pollutants(self):
        for pol in ["pm25", "pm10", "o3", "no2", "so2", "co"]:
            bad_data = {"air_quality": {"status": "ok", pol: -15.0}}
            warns = validate_environmental_data(bad_data)
            self.assertEqual(len(warns), 1, f"Failed to flag negative {pol}")
            self.assertIn(f"Air quality pollutant {pol}=-15.0 cannot be negative", warns[0])

    def test_validate_climate_negative_solar(self):
        solar_neg = {"climate_baseline": {"status": "ok", "solar_radiation_kwh_m2": -4.0}}
        warns = validate_environmental_data(solar_neg)
        self.assertEqual(len(warns), 1)
        self.assertIn("Solar radiation -4.0 kWh/m² cannot be negative", warns[0])

    # -----------------------------------------------------------------------
    # Mocked API fetcher tests
    # -----------------------------------------------------------------------

    @patch("requests.get")
    def test_mocked_fetch_weather_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "current": {
                "temperature_2m": 31.5,
                "wind_speed_10m": 12.4,
                "wind_direction_10m": 180,
                "relative_humidity_2m": 60,
                "pressure_msl": 1008.2,
                "precipitation": 0.0,
                "time": "2026-09-03T10:00",
            }
        }
        mock_get.return_value = mock_resp

        result = fetch_weather(13.08, 80.27)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["temperature_c"], 31.5)
        self.assertEqual(result["observed_at"], "2026-09-03T10:00:00Z")
        self.assertIn("latency_ms", result)

    @patch("requests.get")
    def test_mocked_fetch_marine_landlocked(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "current": {
                "wave_height": None,
                "wave_period": None,
                "wave_direction": None,
                "sea_surface_temperature": None,
                "time": "2026-09-03T10:00",
            }
        }
        mock_get.return_value = mock_resp

        result = fetch_marine(28.61, 77.21)
        self.assertEqual(result["status"], "ok")
        self.assertIsNone(result["wave_height_m"])
        self.assertIsNotNone(result["note"])

    @patch("requests.get")
    def test_mocked_fetch_air_quality_success(self, mock_get):
        # Mock step 1 (/locations) and step 2 (/latest)
        loc_resp = MagicMock()
        loc_resp.status_code = 200
        loc_resp.json.return_value = {
            "results": [
                {
                    "id": 11578,
                    "name": "Mock Station",
                    "datetimeLast": {"utc": "2026-09-03T09:00:00Z"},
                    "sensors": [
                        {"id": 101, "parameter": {"name": "pm25"}},
                        {"id": 102, "parameter": {"name": "pm10"}},
                        {"id": 103, "parameter": {"name": "o3"}},
                        {"id": 104, "parameter": {"name": "no2"}},
                    ],
                }
            ]
        }

        latest_resp = MagicMock()
        latest_resp.status_code = 200
        latest_resp.json.return_value = {
            "results": [
                {"sensorsId": 101, "value": 18.5, "datetime": {"utc": "2026-09-03T09:00:00Z"}},
                {"sensorsId": 102, "value": 35.0, "datetime": {"utc": "2026-09-03T09:00:00Z"}},
                {"sensorsId": 103, "value": 22.1, "datetime": {"utc": "2026-09-03T09:00:00Z"}},
                {"sensorsId": 104, "value": 12.0, "datetime": {"utc": "2026-09-03T09:00:00Z"}},
            ]
        }

        mock_get.side_effect = [loc_resp, latest_resp]

        result = fetch_air_quality(13.08, 80.27, api_key="dummy_key")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["pm25"], 18.5)
        self.assertEqual(result["pm10"], 35.0)
        self.assertEqual(result["aqi_category"], "moderate")
        self.assertIsNone(result["so2"])  # Missing pollutant returned as None (#9)
        self.assertIn("latency_ms", result)

    @patch("requests.get")
    def test_mocked_fetch_climate_baseline_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "properties": {
                "parameter": {
                    "ALLSKY_SFC_SW_DWN": {"20260830": -999.0, "20260829": 5.8},
                    "T2M": {"20260830": 30.2},
                    "WS10M": {"20260830": 3.4},
                }
            }
        }
        mock_get.return_value = mock_resp

        result = fetch_climate_baseline(13.08, 80.27)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["solar_radiation_kwh_m2"], 5.8)
        self.assertEqual(result["avg_temperature_c"], 30.2)
        self.assertEqual(result["observed_at"], "2026-08-29T00:00:00Z")

    # -----------------------------------------------------------------------
    # Integration test with mocked partial failure
    # -----------------------------------------------------------------------

    @patch("env_intelligence_test.fetch_weather")
    @patch("env_intelligence_test.fetch_marine")
    @patch("env_intelligence_test.fetch_air_quality")
    @patch("env_intelligence_test.fetch_climate_baseline")
    def test_get_environmental_snapshot_partial_failure(self, mock_climate, mock_aq, mock_marine, mock_weather):
        mock_weather.return_value = {"source": "open-meteo", "status": "ok", "temperature_c": 30.0, "latency_ms": 100}
        mock_marine.return_value = {"source": "open-meteo-marine", "status": "ok", "wave_height_m": 1.0, "latency_ms": 120}
        # Simulate OpenAQ failing
        mock_aq.return_value = {"source": "openaq", "status": "error", "error": "Connection refused", "latency_ms": 500}
        mock_climate.return_value = {"source": "nasa-power", "status": "ok", "solar_radiation_kwh_m2": 5.0, "observed_at": "2026-08-28T00:00:00Z", "latency_ms": 150}

        snapshot = get_environmental_snapshot(13.08, 80.27)
        self.assertIn("partial", snapshot["meta"]["confidence"])
        self.assertEqual(snapshot["meta"]["failed_sources"], ["openaq"])
        self.assertIn("openaq", snapshot["meta"]["source_latencies_ms"])
        self.assertEqual(snapshot["data"]["weather"]["status"], "ok")
        self.assertEqual(snapshot["data"]["air_quality"]["status"], "error")

    # -----------------------------------------------------------------------
    # Tests for Malformed & Non-JSON Upstream Responses (Gap #3)
    # -----------------------------------------------------------------------

    @patch("requests.get")
    def test_mocked_fetch_air_quality_html_502_error(self, mock_get):
        # Simulate Cloudflare HTML 502 Bad Gateway response
        mock_resp = MagicMock()
        mock_resp.status_code = 502
        mock_resp.text = "<html><body><h1>502 Bad Gateway</h1><p>Cloudflare</p></body></html>"
        mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError("502 Server Error: Bad Gateway")
        mock_get.return_value = mock_resp

        result = fetch_air_quality(13.08, 80.27, api_key="test_key")
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["source"], "openaq")
        self.assertIn("502 Server Error", result["error"])

    @patch("requests.get")
    def test_mocked_fetch_air_quality_malformed_non_json_200(self, mock_get):
        # Simulate upstream returning HTTP 200 but corrupted non-JSON text
        import json
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "Error: Upstream database connection timeout occurred"
        mock_resp.json.side_effect = json.decoder.JSONDecodeError("Expecting value", mock_resp.text, 0)
        mock_get.return_value = mock_resp

        result = fetch_air_quality(13.08, 80.27, api_key="test_key")
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["source"], "openaq")
        self.assertIn("Expecting value", result["error"])

    @patch("env_intelligence_test.fetch_weather")
    @patch("env_intelligence_test.fetch_marine")
    @patch("env_intelligence_test.fetch_air_quality")
    @patch("env_intelligence_test.fetch_climate_baseline")
    def test_snapshot_malformed_upstream_does_not_crash_pipeline(self, mock_climate, mock_aq, mock_marine, mock_weather):
        # Simulate weather, marine, climate ok; OpenAQ returns corrupted error
        mock_weather.return_value = {"source": "open-meteo", "status": "ok", "temperature_c": 31.0, "latency_ms": 100}
        mock_marine.return_value = {"source": "open-meteo-marine", "status": "ok", "wave_height_m": 0.9, "latency_ms": 110}
        mock_aq.return_value = {"source": "openaq", "status": "error", "error": "JSONDecodeError: Expecting value: line 1 column 1", "latency_ms": 250}
        mock_climate.return_value = {"source": "nasa-power", "status": "ok", "solar_radiation_kwh_m2": 5.2, "observed_at": "2026-08-28T00:00:00Z", "latency_ms": 120}

        # Must NOT raise unhandled exception
        snapshot = get_environmental_snapshot(13.08, 80.27, bypass_cache=True)
        self.assertEqual(snapshot["data"]["weather"]["status"], "ok")
        self.assertEqual(snapshot["data"]["air_quality"]["status"], "error")
        self.assertEqual(snapshot["meta"]["failed_sources"], ["openaq"])
        self.assertIn("partial", snapshot["meta"]["confidence"])


if __name__ == "__main__":
    unittest.main()

