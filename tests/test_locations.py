"""Unit tests for the Phase 2B locations registry (locations.py)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from locations import get_all_locations, find_location, reload_locations


class TestLocationsRegistry(unittest.TestCase):
    def test_registry_has_at_least_five_locations(self):
        locs = get_all_locations()
        self.assertGreaterEqual(len(locs), 5)

    def test_every_location_has_required_fields(self):
        for loc in get_all_locations():
            self.assertIn("name", loc)
            self.assertIn("lat", loc)
            self.assertIn("lon", loc)
            self.assertIsInstance(loc["lat"], (int, float))
            self.assertIsInstance(loc["lon"], (int, float))
            self.assertTrue(-90.0 <= loc["lat"] <= 90.0)
            self.assertTrue(-180.0 <= loc["lon"] <= 180.0)

    def test_chennai_is_registered(self):
        loc = find_location("Chennai Coast")
        self.assertIsNotNone(loc)
        self.assertAlmostEqual(loc["lat"], 13.08, places=1)
        self.assertAlmostEqual(loc["lon"], 80.27, places=1)

    def test_find_location_case_insensitive(self):
        self.assertIsNotNone(find_location("chennai coast"))

    def test_find_unknown_location_returns_none(self):
        self.assertIsNone(find_location("Nonexistent Place"))

    def test_registry_names_are_unique(self):
        names = [loc["name"] for loc in get_all_locations()]
        self.assertEqual(len(names), len(set(names)))

    def test_reload_locations_returns_same_data(self):
        original = get_all_locations()
        reloaded = reload_locations()
        self.assertEqual(len(original), len(reloaded))


if __name__ == "__main__":
    unittest.main()
