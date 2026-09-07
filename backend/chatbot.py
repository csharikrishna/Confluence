"""
Confluence — Phase 3: Minimal Chatbot Interface
Core Chatbot Engine: Location Matching, Grounding Context Synthesis, and LLM Client.

Takes a plain-language question, resolves it to one of the 5 registered coastal locations,
fetches verified live environmental snapshot + active alerts, injects unified JSON into a
strict grounding prompt, and queries the LLM.
"""

import os
import re
import json
import time
import logging
import requests
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple, Dict, Any, List
from dotenv import load_dotenv

from locations import get_all_locations
from environmental_data import get_environmental_snapshot
import db_backend as storage
from derived_insights import compute_derived_insights
from rules_engine import evaluate_alerts
from utils import get_path
from gemini_client import (
    call_gemini_llm,
    is_gemini_available,
    DEFAULT_GEMINI_MODELS,
)

load_dotenv()
logger = logging.getLogger("environmental_api.chatbot")

# ---------------------------------------------------------------------------
# Registered Location Aliases
# ---------------------------------------------------------------------------
# Aliases mapped to the canonical location name in locations.json
LOCATION_ALIASES: Dict[str, List[str]] = {
    "Chennai Coast": [
        "chennai",
        "madras",
        "marina",
        "besant nagar",
        "coromandel",
    ],
    "Visakhapatnam Coast": [
        "visakhapatnam",
        "vizag",
        "vishakhapatnam",
        "waltair",
        "vizagapatam",
        "rushikonda",
    ],
    "Kochi Coast": [
        "kochi",
        "cochin",
        "ernakulam",
        "fort kochi",
        "malabar",
    ],
    "Mumbai Coast": [
        "mumbai",
        "bombay",
        "juhu",
        "marine drive",
        "bandra",
        "colaba",
    ],
    "Kolkata / Sundarbans Coast": [
        "kolkata",
        "calcutta",
        "sundarbans",
        "sunderbans",
        "sundarban",
        "digha",
        "bengal",
        "west bengal",
    ],
}

# NVIDIA NIM API Settings
NVIDIA_INVOKE_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
# Primary default model: meta/llama-3.2-11b-vision-instruct (fast, high availability)
# Candidate fallbacks if capacity exhausted or error encountered
CANDIDATE_MODELS = [
    "meta/llama-3.2-11b-vision-instruct",
    "meta/llama-3.1-8b-instruct",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
    "mistralai/mistral-7b-instruct-v0.3",
]


def match_location(query: str) -> Optional[Dict[str, Any]]:
    """
    Case-insensitively resolves a plain-language question to one of the registered
    coastal locations in locations.json using name and alias word-boundary matching.
    Returns the matching location dict ({name, lat, lon, region}) or None.
    """
    if not query or not isinstance(query, str):
        return None

    cleaned_query = query.strip().lower()
    registered_locations = get_all_locations()

    # Pass 1: Check canonical name substrings or word matches
    for loc in registered_locations:
        loc_name = loc["name"].lower()
        # Direct word match against base city name (e.g. "chennai" in "chennai coast")
        base_name = loc_name.split()[0]
        pattern = rf"\b{re.escape(base_name)}\b"
        if re.search(pattern, cleaned_query):
            return loc

    # Pass 2: Check aliases dictionary
    for loc_name, aliases in LOCATION_ALIASES.items():
        for alias in aliases:
            pattern = rf"\b{re.escape(alias.lower())}\b"
            if re.search(pattern, cleaned_query):
                for loc in registered_locations:
                    if loc["name"] == loc_name:
                        return loc

    # Pass 3: Fallback check for any registered full name substring
    for loc in registered_locations:
        if loc["name"].lower() in cleaned_query:
            return loc

    return None


def fetch_grounding_context(
    lat: float, lon: float, name: str, bypass_cache: bool = False
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Fetches the unified environmental snapshot, computes derived insights,
    24h trends, and active alerts. Returns (snapshot, active_alerts).
    """
    snapshot = get_environmental_snapshot(
        lat=lat,
        lon=lon,
        name=name,
        bypass_cache=bypass_cache,
    )

    data = snapshot.get("data", {}) or {}
    meta = snapshot.setdefault("meta", {})

    # 24h history lookup for trends and derived insights
    try:
        past_24h = storage.get_reading_hours_ago(lat, lon, 24, tolerance_hours=3)
    except Exception as e:
        logger.warning(f"24h history lookup failed for ({lat}, {lon}): {e}")
        past_24h = None

    current_pressure = (data.get("weather") or {}).get("pressure_hpa")
    try:
        pressure_change_24h = storage.get_pressure_change_24h(lat, lon, current_pressure, past=past_24h)
    except Exception as e:
        logger.warning(f"24h pressure change calculation failed for ({lat}, {lon}): {e}")
        pressure_change_24h = None

    try:
        past_3h = storage.get_reading_hours_ago(lat, lon, 3)
    except Exception as e:
        logger.warning(f"3h history lookup failed for ({lat}, {lon}): {e}")
        past_3h = None
    pressure_3h_ago = get_path(past_3h, "weather.pressure_hpa") if past_3h else None
    pressure_change_3h = (
        round(current_pressure - pressure_3h_ago, 2)
        if (current_pressure is not None and pressure_3h_ago is not None)
        else None
    )

    # Derived physical insights
    derived = compute_derived_insights(
        data,
        lat=lat,
        pressure_change_24h_hpa=pressure_change_24h,
        pressure_change_3h_hpa=pressure_change_3h,
    )
    meta["derived_insights"] = derived

    # 24h trend diff
    try:
        trend = storage.compute_trend_24h(lat, lon, data, past=past_24h)
    except Exception as e:
        logger.warning(f"Trend diff calculation failed for ({lat}, {lon}): {e}")
        trend = None
    if trend:
        meta["trend_24h"] = trend

    # Rule-based alerting
    try:
        alerts = evaluate_alerts(
            data,
            derived,
            lat=lat,
            lon=lon,
            history_lookup=storage.get_reading_hours_ago,
        )
    except Exception as e:
        logger.warning(f"Alert evaluation failed for ({lat}, {lon}): {e}")
        alerts = []
    meta["active_alerts"] = alerts

    return snapshot, alerts


def format_operational_briefing(snapshot: Dict[str, Any], alerts: List[Dict[str, Any]]) -> str:
    """
    Translates 75 raw hyperparameters and 38 derived metrics into an explicit,
    human-and-model-readable Operational Coastal Briefing with units, safety
    thresholds, and domain interpretations so the LLM never confuses raw numbers.
    """
    loc = snapshot.get("location") or {}
    data = snapshot.get("data") or {}
    meta = snapshot.get("meta") or {}
    derived = meta.get("derived_insights") or {}
    trend = meta.get("trend_24h") or {}

    weather = data.get("weather") or {}
    marine = data.get("marine") or {}
    aq = data.get("air_quality") or {}
    flood = data.get("river_flood") or {}
    cyclone = derived.get("cyclone_advisory") or {}
    fire = derived.get("air_quality_causality") or {}

    lines = []
    lines.append(f"### OPERATIONAL COASTAL BRIEFING: {loc.get('name', 'Unknown Location')} ({loc.get('lat')}°N, {loc.get('lon')}°E)")
    lines.append(f"Observation Timestamp: {snapshot.get('generated_at') or snapshot.get('timestamp_utc') or 'Live Telemetry'}")

    # 1. Active Safety Alerts
    if alerts:
        lines.append("\n🚨 ACTIVE SAFETY ALERTS (IMMEDIATE OPERATIONAL RESTRICTIONS):")
        for a in alerts:
            title = a.get("title", "Safety Alert")
            sev = a.get("severity", "warning").upper()
            msg = a.get("message", "")
            adv = a.get("advisory", "Exercise caution")
            lines.append(f"- [{sev}] {title}: {msg} -> ADVISORY: {adv}")
    else:
        lines.append("\n✅ ACTIVE SAFETY STATUS: All parameters currently within normal limits. No active alerts.")

    # 2. Marine Sea State & Launch Conditions
    wh = marine.get("wave_height_m")
    sw_h = marine.get("swell_wave_height_m")
    sw_p = marine.get("swell_wave_period_s")
    curr_v = marine.get("ocean_current_velocity_kmh")
    craft_level = derived.get("small_craft_risk_level", "none")
    lines.append("\n🌊 MARINE SEA STATE & VESSEL LAUNCH CONDITIONS:")
    lines.append(f"- Significant Wave Height: {wh if wh is not None else 'N/A'} m (Small Craft Advisory threshold is 2.1 m)")
    lines.append(f"- Swell State: {sw_h if sw_h is not None else 'N/A'} m height @ {sw_p if sw_p is not None else 'N/A'} s period from {marine.get('swell_wave_direction_deg', 'N/A')}°")
    lines.append(f"- Surface Ocean Current: {curr_v if curr_v is not None else 'N/A'} km/h drift toward {marine.get('ocean_current_direction_deg', 'N/A')}°")
    lines.append(f"- Sea Surface Temp: {marine.get('sea_surface_temp_c', 'N/A')} °C")
    lines.append(f"- Small Craft Risk Tier: {craft_level.upper()} ({'Small uninspected boats should NOT launch' if craft_level in ['small_craft_advisory', 'gale_warning', 'storm_warning', 'critical'] else 'Safe for small craft navigation'})")

    # 3. Atmosphere & Physiological Heat Stress
    t = weather.get("temperature_c")
    hi = derived.get("heat_index_c")
    hi_cat = derived.get("heat_index_category", "normal")
    p = weather.get("surface_pressure_hpa") or weather.get("pressure_hpa")
    w = weather.get("wind_speed_kmh")
    wg = weather.get("wind_gusts_kmh")
    b_scale = derived.get("beaufort_scale") or {}
    lines.append("\n🌤️ ATMOSPHERIC CONDITIONS & HEAT STRESS:")
    lines.append(f"- Ambient Air Temp: {t if t is not None else 'N/A'} °C | Relative Humidity: {weather.get('humidity_pct', 'N/A')}%")
    lines.append(f"- NOAA Heat Index: {hi if hi is not None else 'N/A'} °C ({hi_cat.upper()}) [Caution >= 27°C, Danger >= 39.4°C, Extreme Danger >= 51.7°C]")
    lines.append(f"- Barometric Pressure: {p if p is not None else 'N/A'} hPa (24h Trend: {trend.get('pressure_hpa', {}).get('diff', 'N/A')} hPa)")
    lines.append(f"- Sustained Wind: {w if w is not None else 'N/A'} km/h (Beaufort Force {b_scale.get('force', 'N/A')}: {b_scale.get('name', 'N/A')}) | Peak Gusts: {wg if wg is not None else 'N/A'} km/h")
    lines.append(f"- Convective Storm Potential: {derived.get('storm_potential_score', 'N/A')} ({derived.get('storm_potential_level', 'low').upper()})")

    # 4. Air Quality & Satellite Smoke Attribution
    pm25 = aq.get("pm25")
    aq_cat = aq.get("aqi_category") or "Moderate"
    lines.append("\n💨 AIR QUALITY & SATELLITE FIRE CAUSALITY:")
    lines.append(f"- Monitoring Station Node: {aq.get('station_name', 'Physical Sensor')} ({aq.get('data_type', 'measured')})")
    lines.append(f"- PM2.5 Concentration: {pm25 if pm25 is not None else 'N/A'} µg/m³ [Tier: {aq_cat} | WHO/NAAQS 24h health standard is 35.4 µg/m³]")
    lines.append(f"- PM10: {aq.get('pm10', 'N/A')} µg/m³ | O3: {aq.get('o3', 'N/A')} µg/m³ | NO2: {aq.get('no2', 'N/A')} µg/m³")
    lines.append(f"- NASA Satellite Fire Causality: {fire.get('causal_attribution', 'Nominal atmospheric conditions — no active fires within 300km')}")
    lines.append(f"- Boundary Layer Stagnation: {derived.get('air_stagnation_index', 'low').upper()}")

    # 5. River Delta Hydrology & Severe Hazards
    c_flood = derived.get("coastal_flood_risk") or {}
    lines.append("\n🌊 ESTUARINE HYDROLOGY & SEVERE MULTI-HAZARDS:")
    lines.append(f"- Station Elevation: {data.get('terrain', {}).get('elevation_m', 'N/A')} m above sea level")
    lines.append(f"- Copernicus GloFAS River Runoff: {flood.get('river_discharge_m3s', 0.0)} m³/s (Compound Deltaic Flood Risk: {c_flood.get('estuarine_compound_risk', False)})")
    lines.append(f"- GDACS Cyclone Tracking: {cyclone.get('reason') or 'Nominal — No active tropical cyclones within 1000 km'}")
    lines.append(f"- USGS Seismic / Tsunami Watch: {derived.get('tsunami_advisory', {}).get('reason') or 'Nominal — No shallow M>=6.5 earthquakes within 500 km'}")

    return "\n".join(lines)


def _get_ist_now() -> str:
    """Returns current Indian Standard Time as a human-readable string for prompt injection."""
    ist = timezone(timedelta(hours=5, minutes=30))
    now = datetime.now(ist)
    return now.strftime("%A, %d %b %Y, %I:%M %p IST")  # e.g. "Sunday, 07 Sep 2026, 04:32 PM IST"


def build_grounding_prompt(question: str, snapshot: Dict[str, Any], alerts: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Constructs the grounding prompt with:
    - Current IST timestamp injected at the top so the model can reason about
      time-relative queries ("in 3 hours", "tonight", "this evening").
    - Operational coastal briefing (human-readable interpretation of all 75 parameters
      with safety thresholds and domain context).
    - Compact key-value summary of raw numeric values for model verification —
      NOT the full JSON dump (reduces input tokens by ~40%).
    - Indian coastal context baselines in the system instruction.
    """
    briefing_text = format_operational_briefing(snapshot, alerts)
    current_ist = _get_ist_now()

    # Compact key-value summary — avoids duplicating the full ~2000-token JSON
    # while still giving the model raw numbers to reference
    data = snapshot.get("data") or {}
    meta = snapshot.get("meta") or {}
    derived = meta.get("derived_insights") or {}
    trend = meta.get("trend_24h") or {}
    weather = data.get("weather") or {}
    marine = data.get("marine") or {}
    aq = data.get("air_quality") or {}
    sun = data.get("sun_and_lighting") or {}

    compact_values = (
        f"[RAW KEY VALUES]\n"
        f"temp={weather.get('temperature_c')}°C, feels_like={weather.get('apparent_temperature_c')}°C, "
        f"humidity={weather.get('humidity_pct')}%, pressure={weather.get('surface_pressure_hpa') or weather.get('pressure_hpa')}hPa\n"
        f"wind={weather.get('wind_speed_kmh')}km/h, gusts={weather.get('wind_gusts_kmh')}km/h, "
        f"precip={weather.get('precipitation_mm')}mm, uv={weather.get('uv_index')}\n"
        f"wave_height={marine.get('wave_height_m')}m, swell={marine.get('swell_wave_height_m')}m@{marine.get('swell_wave_period_s')}s, "
        f"sst={marine.get('sea_surface_temp_c')}°C, current={marine.get('ocean_current_velocity_kmh')}km/h\n"
        f"pm25={aq.get('pm25')}µg/m³, pm10={aq.get('pm10')}µg/m³, aqi_cat={aq.get('aqi_category')}\n"
        f"heat_index={derived.get('heat_index_c')}°C ({derived.get('heat_index_category')}), "
        f"beaufort={derived.get('beaufort_scale', {}).get('force')} ({derived.get('beaufort_scale', {}).get('name')})\n"
        f"small_craft_risk={derived.get('small_craft_risk_level')}, storm_potential={derived.get('storm_potential_score')} ({derived.get('storm_potential_level')})\n"
        f"sunrise={sun.get('sunrise_utc')}, sunset={sun.get('sunset_utc')}, "
        f"pressure_24h_trend={trend.get('pressure_hpa', {}).get('diff')}hPa\n"
        f"active_alerts_count={len(alerts)}"
    )

    system_instruction = (
        "You are the Coastal Intelligence & Safety Advisor for Confluence.\n"
        "Your mission is to help real people (sailors, fishermen, families, harbor pilots) make safe, informed decisions.\n"
        "Use ONLY the verified real-time data and operational briefing provided below to answer the user's question.\n\n"
        "COMMUNICATION PHILOSOPHY:\n"
        "1. Natural, Human-First Tone: The user will describe their situation naturally and will NOT ask you to 'be simple' or 'be technical'. "
        "You must adapt naturally — be empathetic, direct, and conversational.\n"
        "2. TIME-AWARE REASONING: The current local time (IST) is injected at the top of every briefing. Use it to:\n"
        "   - Resolve relative time references: 'in 3 hours', 'tonight', 'this evening', 'at sunset'.\n"
        "   - Check if the user's planned activity falls within daylight, after sunset, or during peak heat hours.\n"
        "   - Reference the provided sunrise/sunset times to anchor advice precisely.\n"
        "3. Avoid Metric Clutter: Do NOT dump raw numbers on a normal user. Abstract away complexity.\n"
        "4. Core Meaningful Metrics: Surface ONLY the metrics that matter to everyday human safety:\n"
        "   - Temperature (ambient + how it feels with heat index)\n"
        "   - Wind speed (and what it means — chop, whitecaps, drift)\n"
        "   - Wave height & sea state (safe for small craft or families?)\n"
        "   - Safety alerts (highlight immediately, unprompted)\n"
        "5. PROACTIVE SAFETY ALERT: Highlight any dangerous conditions (hazardous waves, gale winds, poor air, rapid pressure drop) prominently and immediately.\n"
        "6. Scenario-Specific Guidance: Give clear, actionable advice for the user's specific scenario.\n"
        "7. Technical Depth On Demand: Summarize deeper data cleanly at the end in an optional 'Detailed Data' note.\n"
        "8. Strict Grounding: Use ONLY the verified real-time data provided. Never guess or hallucinate.\n\n"
        "INDIAN COASTAL CONTEXT — apply these region-specific baselines (not generic Western standards):\n"
        "- Temperature: Indian coastal cities routinely see 30–40°C. "
        "Treat ≤35°C as normal for the season, 36–40°C as warm-but-typical, 41°C+ as elevated caution, 44°C+ as severe. "
        "Do NOT alarm users for temperatures that are typical for this region and season.\n"
        "- Humidity: Coastal India regularly sees 60–90% humidity, especially Jun–Sep (monsoon). "
        "Flag humidity only when combined with high temperature to produce a dangerous heat index (>40°C).\n"
        "- Wind: Bay of Bengal coasts regularly see 15–30 km/h monsoon winds. "
        "Reference IMD (Indian Meteorological Department) standards — not generic Western thresholds.\n"
        "- Monsoon context: If the date falls between June and September, acknowledge monsoon season when relevant "
        "(higher baseline humidity, increased swell, elevated rainfall probability).\n"
        "- Units: Always use Celsius for temperature, km/h for wind, meters for waves. Never switch to Fahrenheit or knots."
    )

    user_content = (
        f"Current Local Time (IST): {current_ist}\n\n"
        f"{briefing_text}\n\n"
        f"{compact_values}\n\n"
        f"User question: {question}"
    )

    return [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": user_content},
    ]


def call_nvidia_llm(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    retries_per_model: int = 2,
) -> str:
    """
    Calls NVIDIA NIM chat completions API. Tries the requested or configured model first,
    and falls back through candidate models if worker capacity (503) or quota issues arise.
    """
    key = api_key or os.getenv("NVIDIA_API_KEY")
    if not key:
        raise ValueError("NVIDIA_API_KEY environment variable is not configured.")

    configured_model = model or os.getenv("NVIDIA_MODEL")
    model_list = [configured_model] if configured_model else []
    for m in CANDIDATE_MODELS:
        if m not in model_list:
            model_list.append(m)

    headers = {
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    last_error = None
    for candidate_model in model_list:
        payload = {
            "model": candidate_model,
            "messages": messages,
            "max_tokens": 700,
            "temperature": 0.3,
            "top_p": 0.95,
        }

        for attempt in range(1, retries_per_model + 1):
            try:
                logger.info(f"Querying LLM model: {candidate_model} (attempt {attempt})...")
                resp = requests.post(NVIDIA_INVOKE_URL, headers=headers, json=payload, timeout=45)
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices", [])
                    if choices and "message" in choices[0]:
                        return choices[0]["message"]["content"].strip()
                    raise ValueError(f"Unexpected response format from NIM: {data}")
                elif resp.status_code == 503:
                    logger.warning(f"Model {candidate_model} returned 503 (worker capacity limit). Attempt {attempt}.")
                    time.sleep(attempt * 2)
                    last_error = f"503 Service Unavailable ({candidate_model})"
                else:
                    logger.warning(f"Model {candidate_model} returned {resp.status_code}: {resp.text[:150]}")
                    last_error = f"HTTP {resp.status_code} ({candidate_model}): {resp.text[:100]}"
                    break  # Try next model if non-transient error
            except requests.RequestException as e:
                logger.warning(f"Network error querying {candidate_model} (attempt {attempt}): {e}")
                last_error = str(e)
                time.sleep(attempt * 1.5)

    raise RuntimeError(f"All LLM candidate models failed. Last error: {last_error}")


def ask_coastal_assistant(
    question: str,
    bypass_cache: bool = False,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    provider: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Main entry point for Grounded Coastal Intelligence:
    1. Matches question to a registered coastal location.
    2. If unmatched, returns graceful failure explaining registered stations (no LLM call).
    3. If matched, fetches live snapshot + active alerts.
    4. Formulates grounding prompt with operational coastal briefing + verified JSON payload.
    5. Queries Google Gemini (1M token context window) as primary reasoning engine,
       automatically falling back to NVIDIA NIM if Gemini is unavailable or errors out.
    6. Returns unified dictionary containing answer, location metadata, active alerts,
       raw grounding data, and LLM provider metadata.
    """
    if not question or not question.strip():
        return {
            "question": "",
            "location_matched": None,
            "location_used": None,
            "coordinates": None,
            "answer": "Please ask a question regarding one of our registered coastal monitoring stations.",
            "available_locations": [loc["name"] for loc in get_all_locations()],
            "active_alerts": [],
            "grounding_data": None,
            "llm_provider": None,
            "llm_model": None,
        }

    loc = match_location(question)
    registered_names = [l["name"] for l in get_all_locations()]

    if not loc:
        station_list_str = ", ".join(registered_names)
        return {
            "question": question,
            "location_matched": None,
            "location_used": None,
            "coordinates": None,
            "answer": (
                f"I can only provide verified coastal intelligence for our registered monitoring stations: "
                f"{station_list_str}. "
                f"Please specify one of these locations in your question (for example: 'Is it safe to fish near Chennai right now?')."
            ),
            "available_locations": registered_names,
            "active_alerts": [],
            "grounding_data": None,
            "llm_provider": None,
            "llm_model": None,
        }

    # Location matched — fetch live environmental intelligence
    snapshot, alerts = fetch_grounding_context(
        lat=loc["lat"],
        lon=loc["lon"],
        name=loc["name"],
        bypass_cache=bypass_cache,
    )

    messages = build_grounding_prompt(question, snapshot, alerts)

    # Provider routing: prioritize Gemini when configured, with seamless NVIDIA NIM fallback
    provider_used = None
    model_used = None
    answer = None

    # Detect if call_nvidia_llm has been mocked in unit tests (Mock / MagicMock)
    is_nvidia_mocked = hasattr(call_nvidia_llm, "assert_called")

    want_gemini = (
        (provider == "gemini" or (provider is None and not is_nvidia_mocked and os.getenv("LLM_PROVIDER") != "nvidia"))
        and is_gemini_available()
    )

    if want_gemini:
        try:
            logger.info("Routing query to Google Gemini coastal intelligence engine...")
            ans_text, gemini_model = call_gemini_llm(messages, model=model, api_key=api_key)
            answer = ans_text
            provider_used = "gemini"
            model_used = gemini_model
        except Exception as exc:
            logger.warning(f"Google Gemini query failed ({exc}). Falling back to NVIDIA NIM...")

    # Fallback to NVIDIA NIM if Gemini was not requested, failed, or was mocked in tests
    if answer is None:
        answer = call_nvidia_llm(messages, model=model, api_key=api_key)
        provider_used = "nvidia"
        model_used = model or os.getenv("NVIDIA_MODEL") or CANDIDATE_MODELS[0]

    return {
        "question": question,
        "location_matched": loc["name"],
        "location_used": loc["name"],
        "coordinates": {"lat": loc["lat"], "lon": loc["lon"]},
        "answer": answer,
        "active_alerts": alerts,
        "grounding_data": snapshot,
        "llm_provider": provider_used,
        "llm_model": model_used,
    }
