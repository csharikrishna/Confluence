"""
Stress-Testing & Robustness Suite (Group B & C)
Executes Tasks #4, #5, #6, #7 from the Environmental Intelligence Test Plan.

Run from anywhere: python scripts/stress_test.py
"""

import os
import sys
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from environmental_data import (
    get_environmental_snapshot,
    fetch_weather,
    fetch_marine,
    fetch_air_quality,
    fetch_sun_and_lighting,
    fetch_elevation,
    fetch_climate_baseline,
    fetch_seismic_risk,
    LOCATION,
    OPENAQ_API_KEY,
)

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPORT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stress_test_report.json")


def run_tests():
    report = {
        "task_4_kill_each_api": {},
        "task_5_remote_location_no_openaq": {},
        "task_6_edge_coordinates": {},
        "task_7_timeout_test": {},
    }

    lat, lon = LOCATION["lat"], LOCATION["lon"]

    print("=" * 75)
    print("RUNNING TASK #4: Kill Each API One At A Time (7 Independent Runs)")
    print("=" * 75)

    source_name_map = {
        "weather": "open-meteo",
        "marine": "open-meteo-marine",
        "air_quality": "openaq",
        "sun_and_lighting": "sunrise-sunset.org",
        "terrain": "open-meteo-elevation",
        "climate_baseline": "nasa-power",
        "seismic_risk": "usgs-earthquake",
    }

    sources = list(source_name_map.keys())
    for killed in sources:
        print(f"\n--> Testing failure isolation when killing '{killed}'...")
        w = fetch_weather(lat, lon, base_url="https://invalid-host-weather.test/fail") if killed == "weather" else fetch_weather(lat, lon)
        m = fetch_marine(lat, lon, base_url="https://invalid-host-marine.test/fail") if killed == "marine" else fetch_marine(lat, lon)
        aq = fetch_air_quality(lat, lon, base_url="https://invalid-host-openaq.test/fail") if killed == "air_quality" else fetch_air_quality(lat, lon, api_key=OPENAQ_API_KEY)
        sun = fetch_sun_and_lighting(lat, lon, base_url="https://invalid-host-sun.test/fail") if killed == "sun_and_lighting" else fetch_sun_and_lighting(lat, lon)
        terr = fetch_elevation(lat, lon, base_url="https://invalid-host-elevation.test/fail") if killed == "terrain" else fetch_elevation(lat, lon)
        cb = fetch_climate_baseline(lat, lon, base_url="https://invalid-host-nasa.test/fail") if killed == "climate_baseline" else fetch_climate_baseline(lat, lon)
        seis = fetch_seismic_risk(lat, lon, base_url="https://invalid-host-seismic.test/fail") if killed == "seismic_risk" else fetch_seismic_risk(lat, lon)

        all_7 = [w, m, aq, sun, terr, cb, seis]
        data = {
            "weather": w,
            "marine": m,
            "air_quality": aq,
            "sun_and_lighting": sun,
            "terrain": terr,
            "climate_baseline": cb,
            "seismic_risk": seis,
        }
        failed = [s["source"] for s in all_7 if s.get("status") == "error"]

        expected_failed = source_name_map[killed]
        passed = (failed == [expected_failed])
        other_6_ok = all(s.get('status') == 'ok' for s in all_7 if s['source'] != expected_failed)

        print(f"    Expected failed: [{expected_failed}], Actual failed: {failed}")
        print(f"    Other 6 sources status ok: {other_6_ok}")
        print(f"    Result: {'[PASS]' if (passed and other_6_ok) else '[FAIL]'}")

        report["task_4_kill_each_api"][f"kill_{killed}"] = {
            "passed": passed and other_6_ok,
            "failed_sources": failed,
            "error_detail": data[killed].get("error"),
        }

    print("\n" + "=" * 75)
    print("RUNNING TASK #5: Remote Location / Mid-Ocean Coordinates (No OpenAQ Station)")
    print("=" * 75)
    # Mid-Indian Ocean coordinates: 5.0 N, 85.0 E
    mid_ocean_lat, mid_ocean_lon = 5.0, 85.0
    print(f"Querying mid-Indian Ocean ({mid_ocean_lat}, {mid_ocean_lon})...")
    ocean_snapshot = get_environmental_snapshot(mid_ocean_lat, mid_ocean_lon, name="Mid Indian Ocean")
    aq_status = ocean_snapshot["data"]["air_quality"].get("status")
    aq_err = ocean_snapshot["data"]["air_quality"].get("error")
    weather_status = ocean_snapshot["data"]["weather"].get("status")
    marine_status = ocean_snapshot["data"]["marine"].get("status")

    task_5_pass = (
        aq_status == "error"
        and "No monitoring stations found" in (aq_err or "")
        and weather_status == "ok"
        and marine_status == "ok"
    )
    print(f"    OpenAQ Status: {aq_status} ({aq_err})")
    print(f"    Weather Status: {weather_status}, Marine Status: {marine_status}")
    print(f"    Result: {'[PASS]' if task_5_pass else '[FAIL]'}")

    report["task_5_remote_location_no_openaq"] = {
        "passed": task_5_pass,
        "aq_status": aq_status,
        "aq_error": aq_err,
        "failed_sources": ocean_snapshot["meta"]["failed_sources"],
    }

    print("\n" + "=" * 75)
    print("RUNNING TASK #6: Invalid & Edge-Case Coordinates")
    print("=" * 75)

    # 6a. Out of bounds coordinates (200, 500)
    print("6a. Testing out-of-bounds coordinates (lat=200, lon=500)...")
    oob_snapshot = get_environmental_snapshot(200, 500, name="Invalid World")
    oob_pass = (
        oob_snapshot["meta"]["confidence"].startswith("low — invalid coordinates")
        and "all" in oob_snapshot["meta"]["failed_sources"]
    )
    print(f"    Meta confidence: {oob_snapshot['meta'].get('confidence')}")
    print(f"    Error: {oob_snapshot['meta'].get('error')}")
    print(f"    Result: {'[PASS]' if oob_pass else '[FAIL]'}")

    # 6b. (0, 0) Mid-ocean (Null Island)
    print("\n6b. Testing (0, 0) coordinate (Gulf of Guinea / Null Island)...")
    null_isl = get_environmental_snapshot(0.0, 0.0, name="Null Island")
    null_isl_pass = (
        null_isl["data"]["weather"].get("status") == "ok"
        and null_isl["data"]["marine"].get("status") == "ok"
    )
    print(f"    Weather: {null_isl['data']['weather'].get('status')}, Marine: {null_isl['data']['marine'].get('status')}")
    print(f"    Result: {'[PASS]' if null_isl_pass else '[FAIL]'}")

    # 6c. Landlocked location: Delhi (28.61, 77.21)
    print("\n6c. Testing landlocked coordinates: Delhi (28.61, 77.21)...")
    delhi_snapshot = get_environmental_snapshot(28.61, 77.21, name="Delhi NCR")
    marine_data = delhi_snapshot["data"]["marine"]
    delhi_pass = (
        marine_data.get("status") == "ok"
        and marine_data.get("wave_height_m") is None
        and marine_data.get("note") is not None
        and delhi_snapshot["data"]["weather"].get("status") == "ok"
    )
    print(f"    Marine status: {marine_data.get('status')}, Wave: {marine_data.get('wave_height_m')}, Note: {marine_data.get('note')}")
    print(f"    Result: {'[PASS]' if delhi_pass else '[FAIL]'}")

    report["task_6_edge_coordinates"] = {
        "out_of_bounds_200_500": {"passed": oob_pass, "error": oob_snapshot["meta"].get("error")},
        "null_island_0_0": {"passed": null_isl_pass},
        "landlocked_delhi": {
            "passed": delhi_pass,
            "marine_note": marine_data.get("note"),
            "wave_height": marine_data.get("wave_height_m"),
        },
    }

    print("\n" + "=" * 75)
    print("RUNNING TASK #7: Aggressive Timeout Stress-Test (TIMEOUT = 0.001s)")
    print("=" * 75)
    print("Querying with timeout = 0.001 seconds...")
    timeout_snapshot = get_environmental_snapshot(lat, lon, name="Timeout Test", timeout=0.001)
    total_sources = len(timeout_snapshot["data"])
    failed_sources = timeout_snapshot["meta"]["failed_sources"]
    all_failed = len(failed_sources) == total_sources
    confidence = timeout_snapshot["meta"]["confidence"]
    timeout_pass = all_failed and ("low — all sources failed" in confidence)

    print(f"    Failed sources ({len(failed_sources)}/{total_sources}): {failed_sources}")
    print(f"    Confidence: {confidence}")
    print(f"    Result: {'[PASS]' if timeout_pass else '[FAIL]'}")

    report["task_7_timeout_test"] = {
        "passed": timeout_pass,
        "failed_sources": failed_sources,
        "confidence": confidence,
    }

    print("\n" + "=" * 75)
    print("SUMMARY OF STRESS-TEST RESULTS")
    print("=" * 75)
    all_tasks_passed = (
        all(r["passed"] for r in report["task_4_kill_each_api"].values())
        and report["task_5_remote_location_no_openaq"]["passed"]
        and report["task_6_edge_coordinates"]["out_of_bounds_200_500"]["passed"]
        and report["task_6_edge_coordinates"]["null_island_0_0"]["passed"]
        and report["task_6_edge_coordinates"]["landlocked_delhi"]["passed"]
        and report["task_7_timeout_test"]["passed"]
    )
    print(f"OVERALL STRESS-TEST RESULT: {'ALL PASS [100%]' if all_tasks_passed else 'SOME FAILED'}")

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"Detailed report saved to {REPORT_PATH}\n")


if __name__ == "__main__":
    run_tests()
