"""
Frontier Model Grounding Science Suite (Group A)
Executes Tasks #1, #2, #3:
- Task #2: Stricter ungrounded baseline prompt ("If you do not have live data, say so explicitly...")
- Task #3: Second model family (meta/llama-3.2-11b-vision-instruct)
- Task #1: Multi-condition comparisons across diverse weather (Day 2 Monsoon, Day 3 Pollution Surge)

Run from anywhere: python scripts/multi_model_grounding_demo.py
"""

import os
import sys
import json
import time
import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from environmental_data import get_environmental_snapshot, LOCATION

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()

INVOKE_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
API_KEY = os.getenv("NVIDIA_API_KEY")

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Accept": "application/json",
}

QUESTION = (
    "What are the environmental, marine, and air quality conditions along the "
    "Chennai coastline right now, and what specific advice should be given to "
    "local artisanal fishermen, coastal residents, and outdoor workers today?"
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def call_model(model_name, messages, max_tokens=1024, retries=5):
    payload = {
        "model": model_name,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.4,
        "top_p": 0.95,
    }

    for attempt in range(1, retries + 1):
        try:
            r = requests.post(INVOKE_URL, headers=HEADERS, json=payload, timeout=60)
            if r.status_code == 200:
                data = r.json()
                return data["choices"][0]["message"]["content"]
            elif r.status_code == 503:
                print(f"[{model_name}] 503 capacity limit on attempt {attempt}. Backing off {attempt * 3}s...")
                time.sleep(attempt * 3)
            else:
                print(f"[{model_name}] HTTP {r.status_code} on attempt {attempt}: {r.text[:120]}")
                time.sleep(attempt * 2)
        except Exception as e:
            print(f"[{model_name}] Request error on attempt {attempt}: {e}")
            time.sleep(attempt * 2)

    raise RuntimeError(f"Failed to get response from {model_name} after {retries} attempts.")


def main():
    print("=" * 75)
    print("GROUP A: FRONTIER MODEL GROUNDING EXPERIMENTS")
    print("=" * 75)

    # Fetch live snapshot
    live_snapshot = get_environmental_snapshot(LOCATION["lat"], LOCATION["lon"], LOCATION["name"])

    # -----------------------------------------------------------------------
    # Task #2 & #3: Compare Prompt Strictness and Second Model Family
    # -----------------------------------------------------------------------
    models = {
        "nemotron": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
        "llama": "meta/llama-3.2-11b-vision-instruct",
    }

    strict_ungrounded_prompt = (
        "You are an environmental assistant. If you do not have live, verified data for this location "
        "and time, state so explicitly and indicate your confidence level rather than guessing specific numbers "
        "or estimating current weather.\n\n"
        f"Question: {QUESTION}"
    )

    grounded_prompt = (
        "You are an environmental intelligence assistant.\n"
        "Here is the verified real-time environmental snapshot from our unified data endpoint:\n\n"
        f"```json\n{json.dumps(live_snapshot, indent=2)}\n```\n\n"
        f"Question: {QUESTION}\n\n"
        "Synthesize the multi-domain conditions (weather, ocean, air, and climate baseline) "
        "and provide concrete, actionable guidance grounded directly in these verified observations."
    )

    model_comparison_results = {}

    for family, model_id in models.items():
        print(f"\n---> Testing Model Family: {family} ({model_id})")

        print("  1. Querying STRICT UNGROUNDED baseline...")
        strict_resp = call_model(model_id, [{"role": "user", "content": strict_ungrounded_prompt}], max_tokens=700)
        print("     Strict ungrounded response received.")

        print("  2. Querying GROUNDED with Unified Endpoint JSON...")
        grounded_resp = call_model(model_id, [{"role": "user", "content": grounded_prompt}], max_tokens=1000)
        print("     Grounded response received.")

        model_comparison_results[family] = {
            "model_id": model_id,
            "strict_ungrounded": strict_resp,
            "grounded": grounded_resp,
        }

    two_families_path = os.path.join(SCRIPT_DIR, "model_comparison_two_families.json")
    with open(two_families_path, "w", encoding="utf-8") as f:
        json.dump(model_comparison_results, f, indent=2, ensure_ascii=False)
    print(f"\nSaved Task #2 and #3 results to {two_families_path}")

    # -----------------------------------------------------------------------
    # Task #1: Multi-Condition Grounding (Day 2 Monsoon Rain & Day 3 Pollution Event)
    # -----------------------------------------------------------------------
    print("\n" + "=" * 75)
    print("TASK #1: Multi-Condition Testing Across Diverse Environmental States")
    print("=" * 75)

    # Condition 2: Active Northeast Monsoon Coastal Squall
    day2_snapshot = {
        "location": {"name": "Chennai Coast", "lat": 13.08, "lon": 80.27},
        "generated_at": "2026-10-18T06:30:00Z",
        "data": {
            "weather": {
                "temperature_c": 26.2,
                "wind_speed_kmh": 42.5,
                "wind_direction_deg": 65,  # ENE Monsoon wind
                "humidity_pct": 94,
                "pressure_hpa": 998.2,  # Low pressure trough
                "precipitation_mm": 54.0,  # Heavy monsoon rain
                "source": "open-meteo",
                "observed_at": "2026-10-18T06:15:00Z",
                "status": "ok",
            },
            "marine": {
                "sea_surface_temp_c": 27.8,
                "wave_height_m": 2.85,  # Rough coastal seas
                "wave_period_s": 6.1,  # Choppy wind waves
                "wave_direction_deg": 70,
                "note": None,
                "source": "open-meteo-marine",
                "observed_at": "2026-10-18T06:15:00Z",
                "status": "ok",
            },
            "air_quality": {
                "station_name": "Royapuram, Chennai - TNPCB",
                "pm25": 14.2,  # Rain scavenging clears PM2.5
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
                "solar_radiation_kwh_m2": 1.85,  # Heavy cloud cover
                "avg_temperature_c": 28.5,
                "avg_wind_speed_ms": 6.8,
                "source": "nasa-power",
                "observed_at": "2026-10-15T00:00:00Z",
                "status": "ok",
            },
        },
        "meta": {
            "confidence": "high — all sources responded successfully",
            "failed_sources": [],
            "freshness_warning": "climate_baseline data is >24h old",
        },
    }

    print("\n---> Running Day 2 (Active Monsoon Squall: 54mm Rain, 42 km/h Wind, 2.85m Waves)...")
    day2_grounded_prompt = (
        "You are an environmental intelligence assistant.\n"
        "Here is the verified real-time environmental snapshot from our unified data endpoint:\n\n"
        f"```json\n{json.dumps(day2_snapshot, indent=2)}\n```\n\n"
        f"Question: {QUESTION}\n\n"
        "Synthesize the multi-domain conditions and provide concrete, actionable operational guidance."
    )
    day2_response = call_model(models["nemotron"], [{"role": "user", "content": day2_grounded_prompt}], max_tokens=1000)

    day2_record = {
        "condition": "Active Monsoon Squall (Heavy Rain, High Swell, Low Pressure)",
        "snapshot": day2_snapshot,
        "grounded_response": day2_response,
    }
    day2_path = os.path.join(SCRIPT_DIR, "model_grounding_comparison_day2.json")
    with open(day2_path, "w", encoding="utf-8") as f:
        json.dump(day2_record, f, indent=2, ensure_ascii=False)
    print(f"Saved Day 2 results to {day2_path}")

    # Condition 3: Post-Monsoon Industrial Thermal Inversion / Severe Pollution Surge
    day3_snapshot = {
        "location": {"name": "Chennai Coast", "lat": 13.08, "lon": 80.27},
        "generated_at": "2026-11-20T07:00:00Z",
        "data": {
            "weather": {
                "temperature_c": 31.0,
                "wind_speed_kmh": 2.1,  # Stagnant air
                "wind_direction_deg": 280,
                "humidity_pct": 78,
                "pressure_hpa": 1014.2,
                "precipitation_mm": 0.0,
                "source": "open-meteo",
                "observed_at": "2026-11-20T06:45:00Z",
                "status": "ok",
            },
            "marine": {
                "sea_surface_temp_c": 29.1,
                "wave_height_m": 0.42,  # Very calm sea
                "wave_period_s": 8.0,
                "wave_direction_deg": 130,
                "note": None,
                "source": "open-meteo-marine",
                "observed_at": "2026-11-20T06:45:00Z",
                "status": "ok",
            },
            "air_quality": {
                "station_name": "Royapuram, Chennai - TNPCB",
                "pm25": 168.4,  # Severe unhealthy air
                "pm10": 245.0,
                "o3": 45.0,
                "no2": 72.8,
                "so2": 24.5,
                "co": 3.8,
                "aqi_category": "very unhealthy",
                "source": "openaq",
                "observed_at": "2026-11-20T06:30:00Z",
                "status": "ok",
            },
            "climate_baseline": {
                "solar_radiation_kwh_m2": 4.5,
                "avg_temperature_c": 29.0,
                "avg_wind_speed_ms": 2.5,
                "source": "nasa-power",
                "observed_at": "2026-11-17T00:00:00Z",
                "status": "ok",
            },
        },
        "meta": {
            "confidence": "high — all sources responded successfully",
            "failed_sources": [],
            "freshness_warning": "climate_baseline data is >24h old",
        },
    }

    print("\n---> Running Day 3 (Winter Stagnation: Calm Sea 0.4m, Severe PM2.5 168 µg/m³ - Very Unhealthy)...")
    day3_grounded_prompt = (
        "You are an environmental intelligence assistant.\n"
        "Here is the verified real-time environmental snapshot from our unified data endpoint:\n\n"
        f"```json\n{json.dumps(day3_snapshot, indent=2)}\n```\n\n"
        f"Question: {QUESTION}\n\n"
        "Synthesize the multi-domain conditions and provide concrete, actionable operational guidance."
    )
    day3_response = call_model(models["nemotron"], [{"role": "user", "content": day3_grounded_prompt}], max_tokens=1000)

    day3_record = {
        "condition": "Winter Stagnation (Calm Waters, Very Unhealthy Air Quality Event)",
        "snapshot": day3_snapshot,
        "grounded_response": day3_response,
    }
    day3_path = os.path.join(SCRIPT_DIR, "model_grounding_comparison_day3.json")
    with open(day3_path, "w", encoding="utf-8") as f:
        json.dump(day3_record, f, indent=2, ensure_ascii=False)
    print(f"Saved Day 3 results to {day3_path}")

    print("\n" + "=" * 75)
    print("ALL GROUP A EXPERIMENTS COMPLETED SUCCESSFULLY!")
    print("=" * 75)


if __name__ == "__main__":
    main()
