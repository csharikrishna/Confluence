"""
Unit tests for the physics-informed derived_insights module (Phase 2C support).
Validates formula correctness against known reference values, plus graceful
handling of missing/partial upstream data.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from derived_insights import (
    heat_index_c,
    heat_index_category,
    dew_point_c,
    fog_risk,
    beaufort_scale,
    imd_cyclone_category,
    small_craft_risk,
    storm_potential_score,
    storm_potential_level,
    rapid_pressure_fall,
    air_stagnation_index,
    coastal_flood_risk,
    tsunami_caution,
    compute_derived_insights,
)

# NWS-equivalent tiers at or above Small Craft Advisory (i.e. "don't launch").
_ADVISORY_OR_WORSE = ("small_craft_advisory", "gale_warning", "storm_warning", "hurricane_force_warning")


class TestHeatIndex(unittest.TestCase):
    def test_below_threshold_returns_ambient(self):
        # Below 26.7C the regression doesn't apply; ambient temp passes through.
        self.assertEqual(heat_index_c(20.0, 80.0), 20.0)

    def test_hot_humid_known_reference(self):
        # 35C / 70% RH ~ 95F / 70% RH -> NOAA heat index is well into the 40s C (danger band).
        hi = heat_index_c(35.0, 70.0)
        self.assertIsNotNone(hi)
        self.assertGreater(hi, 35.0)  # heat index must exceed ambient temp at this humidity
        self.assertLess(hi, 60.0)

    def test_low_humidity_correction_lowers_result(self):
        # NOAA's published correction: RH<13% in the 80-112F range subtracts from
        # the base regression, which alone overstates heat index at low humidity.
        # 37.8C/10% RH: base regression gives 34.9C, corrected gives 34.5C.
        self.assertEqual(heat_index_c(37.8, 10.0), 34.5)

    def test_high_humidity_correction_raises_result(self):
        # NOAA's published correction: RH>85% in the 80-87F range adds to the base
        # regression, which alone understates heat index at high humidity.
        # 29.4C/90% RH: base regression gives 38.5C, corrected gives 38.6C.
        self.assertEqual(heat_index_c(29.4, 90.0), 38.6)

    def test_mid_range_humidity_unaffected_by_corrections(self):
        # Neither correction applies at moderate humidity (13-85%) — confirms the
        # corrections are properly scoped, not applied unconditionally.
        self.assertEqual(heat_index_c(35.0, 70.0), 50.3)

    def test_missing_inputs_return_none(self):
        self.assertIsNone(heat_index_c(None, 80.0))
        self.assertIsNone(heat_index_c(35.0, None))

    def test_category_bands(self):
        self.assertEqual(heat_index_category(25.0), "normal")
        self.assertEqual(heat_index_category(29.0), "caution")
        self.assertEqual(heat_index_category(35.0), "extreme_caution")
        self.assertEqual(heat_index_category(45.0), "danger")
        self.assertEqual(heat_index_category(55.0), "extreme_danger")
        self.assertIsNone(heat_index_category(None))


class TestDewPointAndFog(unittest.TestCase):
    def test_dew_point_below_ambient(self):
        dp = dew_point_c(30.0, 60.0)
        self.assertIsNotNone(dp)
        self.assertLess(dp, 30.0)

    def test_dew_point_saturated_air_equals_ambient(self):
        # At 100% RH, dew point == ambient temperature.
        dp = dew_point_c(25.0, 100.0)
        self.assertAlmostEqual(dp, 25.0, delta=0.2)

    def test_fog_risk_high_when_saturated_and_calm(self):
        result = fog_risk(20.0, 98.0, 3.0)
        self.assertEqual(result["risk"], "high")

    def test_fog_risk_low_when_dry_or_windy(self):
        result = fog_risk(35.0, 40.0, 25.0)
        self.assertEqual(result["risk"], "low")

    def test_fog_risk_unknown_on_missing_data(self):
        result = fog_risk(None, None, None)
        self.assertEqual(result["risk"], "unknown")


class TestSmallCraftRisk(unittest.TestCase):
    """Bands now align to official NWS coastal marine warning tiers: Small Craft
    Advisory (18-33kt / 33.3-61.1 km/h), Gale Warning (34-47kt), Storm Warning
    (48-63kt), Hurricane Force Wind Warning (>=64kt) — see derived_insights.py
    header constants for the exact cited kt->km/h conversions.
    """

    def test_calm_conditions_below_any_warning(self):
        result = small_craft_risk(wave_height_m=0.5, wind_speed_kmh=10.0)
        self.assertEqual(result["level"], "none")

    def test_monsoon_squall_reaches_small_craft_advisory(self):
        # Day 2 monsoon-squall fixture: wind 42.5 km/h (~23kt), wave 2.85m.
        # 23kt sits squarely in the 18-33kt Small Craft Advisory band.
        result = small_craft_risk(wave_height_m=2.85, wind_speed_kmh=42.5)
        self.assertEqual(result["level"], "small_craft_advisory")
        self.assertIn(result["level"], _ADVISORY_OR_WORSE)

    def test_unknown_when_no_data(self):
        result = small_craft_risk(wave_height_m=None, wind_speed_kmh=None)
        self.assertEqual(result["level"], "unknown")

    def test_gusts_considered_even_if_sustained_wind_low(self):
        # Gust of 70 km/h (~38kt) falls in the 34-47kt Gale Warning band.
        result = small_craft_risk(wave_height_m=0.3, wind_speed_kmh=10.0, wind_gusts_kmh=70.0)
        self.assertEqual(result["level"], "gale_warning")

    def test_hurricane_force_wind_triggers_top_tier(self):
        result = small_craft_risk(wave_height_m=1.0, wind_speed_kmh=130.0)
        self.assertEqual(result["level"], "hurricane_force_warning")


class TestStormPotential(unittest.TestCase):
    def test_none_pressure_returns_none(self):
        self.assertIsNone(storm_potential_score(None, 10.0, 50.0))

    def test_low_pressure_high_gusts_scores_high(self):
        score = storm_potential_score(pressure_hpa=990.0, wind_gusts_kmh=70.0, cloud_cover_pct=90.0)
        self.assertGreaterEqual(score, 0.8)
        self.assertEqual(storm_potential_level(score), "severe")

    def test_calm_high_pressure_scores_low(self):
        score = storm_potential_score(pressure_hpa=1015.0, wind_gusts_kmh=10.0, cloud_cover_pct=20.0)
        self.assertEqual(score, 0.0)
        self.assertEqual(storm_potential_level(score), "low")

    def test_falling_3h_pressure_raises_score(self):
        # This is the "single strongest storm precursor" per the function's own
        # docstring — confirm it actually changes the outcome, not just accepted
        # and silently ignored.
        base = storm_potential_score(pressure_hpa=1010.0, wind_gusts_kmh=10.0, cloud_cover_pct=20.0)
        with_fall = storm_potential_score(pressure_hpa=1010.0, wind_gusts_kmh=10.0, cloud_cover_pct=20.0, pressure_change_3h_hpa=-4.0)
        self.assertGreater(with_fall, base)

    def test_compute_derived_insights_wires_3h_pressure_change_into_storm_score(self):
        # Regression: storm_potential_score's pressure_change_3h_hpa parameter
        # previously had no caller anywhere in the codebase — always defaulted to
        # None despite being described as the strongest precursor signal.
        data = {"weather": {"status": "ok", "pressure_hpa": 1010.0, "wind_gusts_kmh": 10.0, "cloud_cover_pct": 20.0}}
        without_fall = compute_derived_insights(data)
        with_fall = compute_derived_insights(data, pressure_change_3h_hpa=-4.0)
        self.assertGreater(with_fall["storm_potential_score"], without_fall["storm_potential_score"])


class TestAirStagnation(unittest.TestCase):
    def test_stagnant_calm_polluted_is_high(self):
        self.assertEqual(air_stagnation_index(wind_speed_kmh=3.0, pm25=80.0, precipitation_mm=0.0), "high")

    def test_windy_is_low_regardless_of_pollution(self):
        self.assertEqual(air_stagnation_index(wind_speed_kmh=25.0, pm25=200.0, precipitation_mm=0.0), "low")

    def test_none_wind_returns_none(self):
        self.assertIsNone(air_stagnation_index(None, 50.0))


class TestCoastalFloodRisk(unittest.TestCase):
    def test_low_elevation_high_seas_is_severe_or_high(self):
        result = coastal_flood_risk(elevation_m=2.0, wave_height_m=3.0, wind_speed_kmh=50.0, pressure_hpa=995.0)
        self.assertIn(result["level"], ("high", "severe"))

    def test_high_elevation_calm_seas_is_low(self):
        result = coastal_flood_risk(elevation_m=50.0, wave_height_m=0.3, wind_speed_kmh=10.0, pressure_hpa=1015.0)
        self.assertEqual(result["level"], "low")

    def test_none_elevation_returns_none(self):
        self.assertIsNone(coastal_flood_risk(None, 1.0, 10.0, 1010.0))

    def test_inverse_barometer_surge_computed_from_pressure_deficit(self):
        # 1013.25 - 993.25 = 20 hPa deficit -> ~20cm via the inverse barometer effect (~1cm/hPa).
        result = coastal_flood_risk(elevation_m=3.0, wave_height_m=0.5, wind_speed_kmh=10.0, pressure_hpa=993.25)
        self.assertAlmostEqual(result["inverse_barometer_surge_cm"], 20.0, delta=0.1)

    def test_high_pressure_gives_zero_surge(self):
        result = coastal_flood_risk(elevation_m=3.0, wave_height_m=0.5, wind_speed_kmh=10.0, pressure_hpa=1020.0)
        self.assertEqual(result["inverse_barometer_surge_cm"], 0.0)


class TestBeaufortScale(unittest.TestCase):
    def test_calm_is_force_zero(self):
        self.assertEqual(beaufort_scale(0.5)["force"], 0)

    def test_known_boundary_values(self):
        self.assertEqual(beaufort_scale(42.5)["name"], "strong breeze")  # force 6
        self.assertEqual(beaufort_scale(150.0)["force"], 12)  # hurricane

    def test_none_returns_none(self):
        self.assertIsNone(beaufort_scale(None))


class TestImdCycloneCategory(unittest.TestCase):
    def test_below_depression_threshold_returns_none(self):
        # IMD's scale only starts classifying synoptic systems from ~31 km/h.
        self.assertIsNone(imd_cyclone_category(20.0))

    def test_depression_band(self):
        self.assertEqual(imd_cyclone_category(40.0), "depression")

    def test_severe_cyclonic_storm_band(self):
        self.assertEqual(imd_cyclone_category(100.0), "severe_cyclonic_storm")

    def test_super_cyclonic_storm_top_band(self):
        self.assertEqual(imd_cyclone_category(250.0), "super_cyclonic_storm")

    def test_none_input_returns_none(self):
        self.assertIsNone(imd_cyclone_category(None))


class TestRapidPressureFall(unittest.TestCase):
    def test_missing_inputs_return_none(self):
        self.assertIsNone(rapid_pressure_fall(None, 13.08))
        self.assertIsNone(rapid_pressure_fall(-10.0, None))

    def test_large_fall_at_low_latitude_flagged_against_floor(self):
        # At ~13N the latitude-normalized threshold is tiny; the 3 hPa floor applies.
        result = rapid_pressure_fall(-8.0, 13.08)
        self.assertTrue(result["rapid_fall"])
        self.assertGreaterEqual(result["latitude_normalized_threshold_hpa"], 3.0)

    def test_small_fall_not_flagged(self):
        result = rapid_pressure_fall(-1.0, 13.08)
        self.assertFalse(result["rapid_fall"])

    def test_rising_pressure_not_flagged(self):
        result = rapid_pressure_fall(5.0, 13.08)
        self.assertFalse(result["rapid_fall"])

    def test_higher_latitude_has_higher_threshold(self):
        low_lat = rapid_pressure_fall(-10.0, 13.08)
        high_lat = rapid_pressure_fall(-10.0, 45.0)
        self.assertGreater(high_lat["latitude_normalized_threshold_hpa"], low_lat["latitude_normalized_threshold_hpa"])


class TestTsunamiCaution(unittest.TestCase):
    def test_large_quake_low_elevation_triggers_advisory(self):
        result = tsunami_caution(max_magnitude=7.2, elevation_m=4.0)
        self.assertTrue(result["advisory"])
        self.assertIsNotNone(result["reason"])

    def test_shallow_depth_confirms_advisory(self):
        result = tsunami_caution(max_magnitude=7.2, elevation_m=4.0, depth_km=15.0)
        self.assertTrue(result["advisory"])
        self.assertIn("shallow focus", result["reason"])

    def test_deep_focus_quake_suppresses_advisory(self):
        # A deep-focus quake (>=70km, USGS's own "shallow" cutoff) rarely produces
        # a significant surface tsunami even at high magnitude.
        result = tsunami_caution(max_magnitude=7.5, elevation_m=4.0, depth_km=250.0)
        self.assertFalse(result["advisory"])

    def test_large_quake_high_elevation_no_advisory(self):
        result = tsunami_caution(max_magnitude=7.2, elevation_m=200.0)
        self.assertFalse(result["advisory"])

    def test_no_quake_data_no_advisory(self):
        result = tsunami_caution(None, 4.0)
        self.assertFalse(result["advisory"])


class TestComputeDerivedInsights(unittest.TestCase):
    def test_empty_data_does_not_crash(self):
        result = compute_derived_insights({})
        self.assertIsNone(result["heat_index_c"])
        self.assertIn("methodology_note", result)

    def test_none_data_does_not_crash(self):
        result = compute_derived_insights(None)
        self.assertIsInstance(result, dict)

    def test_partial_data_only_populates_available_domains(self):
        data = {"weather": {"status": "ok", "temperature_c": 33.0, "humidity_pct": 60.0}}
        result = compute_derived_insights(data)
        self.assertIsNotNone(result["heat_index_c"])
        self.assertEqual(result["small_craft_risk_level"], "unknown")  # no marine domain

    def test_monsoon_squall_fixture_flags_multiple_risks(self):
        # Mirrors model_grounding_comparison_day2.json conditions.
        data = {
            "weather": {
                "status": "ok",
                "temperature_c": 26.2,
                "humidity_pct": 94,
                "wind_speed_kmh": 42.5,
                "pressure_hpa": 998.2,
                "precipitation_mm": 54.0,
            },
            "marine": {"status": "ok", "wave_height_m": 2.85},
            "air_quality": {"status": "ok", "pm25": 14.2},
            "terrain": {"status": "ok", "elevation_m": 6.0},
        }
        result = compute_derived_insights(data)
        self.assertIn(result["small_craft_risk_level"], _ADVISORY_OR_WORSE)
        self.assertIn(result["storm_potential_level"], ("moderate", "high", "severe"))
        self.assertEqual(result["beaufort_scale"]["name"], "strong breeze")  # 42.5 km/h -> Beaufort force 6


if __name__ == "__main__":
    unittest.main()
