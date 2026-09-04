"""
Unit tests for the Phase 2C rules engine (rules_engine.py).
Uses the real alert_rules.json config plus the Phase 1 Day 2 monsoon-squall
grounding scenario as a known-good test case, per the Phase 2 plan's suggested
test approach.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rules_engine import evaluate_alerts, load_rules
from derived_insights import compute_derived_insights

# Inlined rather than loaded from model_grounding_comparison_day2.json: that
# file is a generated demo artifact matched by .gitignore's
# "model_grounding_comparison*.json" pattern, so it's never actually committed
# — a test that depended on reading it would fail on any fresh clone/CI
# checkout. This is the same real Day 2 monsoon-squall reading (Chennai Coast,
# 2026-10-18T06:30:00Z), just self-contained.
DAY2_MONSOON_SQUALL_DATA = {
    "weather": {
        "temperature_c": 26.2,
        "wind_speed_kmh": 42.5,
        "wind_direction_deg": 65,
        "humidity_pct": 94,
        "pressure_hpa": 998.2,
        "precipitation_mm": 54.0,
        "source": "open-meteo",
        "observed_at": "2026-10-18T06:15:00Z",
        "status": "ok",
    },
    "marine": {
        "sea_surface_temp_c": 27.8,
        "wave_height_m": 2.85,
        "wave_period_s": 6.1,
        "wave_direction_deg": 70,
        "note": None,
        "source": "open-meteo-marine",
        "observed_at": "2026-10-18T06:15:00Z",
        "status": "ok",
    },
    "air_quality": {
        "station_name": "Royapuram, Chennai - TNPCB",
        "pm25": 14.2,
        "pm10": 22.0,
        "o3": 8.5,
        "no2": 6.2,
        "so2": 2.1,
        "co": 0.45,
        "aqi_category": "good",
        "source": "openaq",
        "observed_at": "2026-10-18T06:00:00Z",
        "status": "ok",
    },
    "climate_baseline": {
        "solar_radiation_kwh_m2": 1.85,
        "avg_temperature_c": 28.5,
        "avg_wind_speed_ms": 6.8,
        "source": "nasa-power",
        "observed_at": "2026-10-15T00:00:00Z",
        "status": "ok",
    },
}


class TestRulesEngineBasics(unittest.TestCase):
    def test_rules_config_loads_and_is_nonempty(self):
        rules = load_rules(force_reload=True)
        self.assertIsInstance(rules, list)
        self.assertGreater(len(rules), 0)
        for rule in rules:
            self.assertIn("id", rule)
            self.assertIn("operator", rule)
            self.assertIn("severity", rule)

    def test_calm_data_triggers_nothing(self):
        # Explicit false-positive check per the Phase 2 "done" criteria.
        data = {
            "weather": {
                "status": "ok", "temperature_c": 28.0, "humidity_pct": 65.0,
                "wind_speed_kmh": 12.0, "wind_gusts_kmh": 18.0, "pressure_hpa": 1012.0,
                "precipitation_mm": 0.0, "cloud_cover_pct": 30.0,
            },
            "marine": {"status": "ok", "wave_height_m": 0.6},
            "air_quality": {"status": "ok", "pm25": 18.0},
            "terrain": {"status": "ok", "elevation_m": 40.0},
            "seismic_risk": {"status": "ok", "max_magnitude": None, "recent_events_7d_count": 0},
        }
        derived = compute_derived_insights(data)
        alerts = evaluate_alerts(data, derived)
        self.assertEqual(alerts, [], f"Expected no alerts on calm data, got: {alerts}")

    def test_empty_data_does_not_crash(self):
        alerts = evaluate_alerts({}, compute_derived_insights({}))
        self.assertEqual(alerts, [])


class TestKnownScenarios(unittest.TestCase):
    def test_day2_monsoon_squall_triggers_do_not_launch_style_alerts(self):
        data = DAY2_MONSOON_SQUALL_DATA
        derived = compute_derived_insights(data)
        alerts = evaluate_alerts(data, derived)

        alert_ids = {a["id"] for a in alerts}
        self.assertIn("small_craft_unsafe", alert_ids, f"Expected small_craft_unsafe, got: {alert_ids}")
        self.assertIn("strong_sustained_wind", alert_ids, f"Expected strong_sustained_wind, got: {alert_ids}")
        self.assertIn("heavy_rain_flood_risk", alert_ids, f"Expected heavy_rain_flood_risk, got: {alert_ids}")

        small_craft = next(a for a in alerts if a["id"] == "small_craft_unsafe")
        self.assertEqual(small_craft["value"], "small_craft_advisory")
        self.assertIn("vessel", small_craft["message"].lower())

    def test_day2_squall_air_quality_is_fine_no_pm25_alert(self):
        # Day 2 data has pm25=14.2 (good) — must NOT trigger air quality alerts.
        data = DAY2_MONSOON_SQUALL_DATA
        derived = compute_derived_insights(data)
        alerts = evaluate_alerts(data, derived)
        alert_ids = {a["id"] for a in alerts}
        self.assertNotIn("pm25_unhealthy", alert_ids)
        self.assertNotIn("pm25_very_unhealthy", alert_ids)


class TestTrendRules(unittest.TestCase):
    def test_trend_rule_fires_on_injected_history(self):
        current_data = {"weather": {"status": "ok", "temperature_c": 36.0}}
        derived = compute_derived_insights(current_data)

        def fake_history(lat, lon, hours_ago):
            return {"weather": {"temperature_c": 29.0}}

        alerts = evaluate_alerts(current_data, derived, lat=13.08, lon=80.27, history_lookup=fake_history)
        alert_ids = {a["id"] for a in alerts}
        self.assertIn("trend_temp_spike_3h", alert_ids)

    def test_trend_rule_skipped_when_no_history_available(self):
        current_data = {"weather": {"status": "ok", "temperature_c": 36.0}}
        derived = compute_derived_insights(current_data)

        def no_history(lat, lon, hours_ago):
            return None

        alerts = evaluate_alerts(current_data, derived, lat=13.08, lon=80.27, history_lookup=no_history)
        self.assertNotIn("trend_temp_spike_3h", {a["id"] for a in alerts})

    def test_trend_rule_skipped_without_lat_lon_or_lookup(self):
        current_data = {"weather": {"status": "ok", "temperature_c": 36.0}}
        derived = compute_derived_insights(current_data)
        alerts = evaluate_alerts(current_data, derived)  # no lat/lon/history_lookup given
        self.assertNotIn("trend_temp_spike_3h", {a["id"] for a in alerts})

    def test_trend_ratio_rule_fires_on_doubling(self):
        current_data = {"air_quality": {"status": "ok", "pm25": 80.0}}
        derived = compute_derived_insights(current_data)

        def fake_history(lat, lon, hours_ago):
            return {"air_quality": {"pm25": 35.0}}

        alerts = evaluate_alerts(current_data, derived, lat=13.08, lon=80.27, history_lookup=fake_history)
        self.assertIn("trend_pm25_doubling_3h", {a["id"] for a in alerts})


class TestSeismicAndCategoricalRules(unittest.TestCase):
    def test_tsunami_caution_rule_fires(self):
        data = {
            "seismic_risk": {"status": "ok", "max_magnitude": 7.0, "recent_events_7d_count": 1},
            "terrain": {"status": "ok", "elevation_m": 3.0},
        }
        derived = compute_derived_insights(data)
        alerts = evaluate_alerts(data, derived)
        alert = next((a for a in alerts if a["id"] == "seismic_tsunami_caution"), None)
        self.assertIsNotNone(alert)
        self.assertIn("M7.0", alert["message"])

    def test_air_stagnation_categorical_rule(self):
        data = {
            "weather": {"status": "ok", "wind_speed_kmh": 3.0, "precipitation_mm": 0.0},
            "air_quality": {"status": "ok", "pm25": 90.0},
        }
        derived = compute_derived_insights(data)
        self.assertEqual(derived["air_stagnation_index"], "high")
        alerts = evaluate_alerts(data, derived)
        self.assertIn("air_stagnation_high", {a["id"] for a in alerts})


if __name__ == "__main__":
    unittest.main()
