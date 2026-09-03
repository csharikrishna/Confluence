"""
Phase 2B — Locations Registry

A simple static, file-backed list of registered coastal points. This is deliberately
not a database table (yet) — per the Phase 2 plan, this is "really just stop hardcoding
Chennai," not a new subsystem. Swapping this for a `locations` table later is a
drop-in change since every consumer goes through get_all_locations().
"""

import json
import os

LOCATIONS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locations.json")

_CACHE = None


def get_all_locations():
    """Return the full registry as a list of {name, lat, lon, region} dicts."""
    global _CACHE
    if _CACHE is None:
        with open(LOCATIONS_PATH, "r", encoding="utf-8") as f:
            _CACHE = json.load(f)
    return _CACHE


def find_location(name):
    """Case-insensitive lookup of a registered location by name, or None."""
    for loc in get_all_locations():
        if loc["name"].lower() == str(name).lower():
            return loc
    return None


def reload_locations():
    """Force re-read of locations.json from disk (mainly useful for tests)."""
    global _CACHE
    _CACHE = None
    return get_all_locations()
