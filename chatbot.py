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
from typing import Optional, Tuple, Dict, Any, List
from dotenv import load_dotenv

from locations import get_all_locations
from environmental_data import get_environmental_snapshot
import db_backend as storage
from derived_insights import compute_derived_insights
from rules_engine import evaluate_alerts
from utils import get_path

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


def build_grounding_prompt(question: str, snapshot: Dict[str, Any], alerts: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Constructs the strict grounding prompt adhering to Phase 3 specification:
    'You are a coastal conditions assistant. Use ONLY the data below to answer.
    If the data doesn't cover something, say so — don't guess.'
    """
    context_payload = {
        "location": snapshot.get("location"),
        "timestamp_utc": snapshot.get("timestamp_utc"),
        "environmental_data": snapshot.get("data"),
        "derived_insights": (snapshot.get("meta") or {}).get("derived_insights"),
        "trend_24h": (snapshot.get("meta") or {}).get("trend_24h"),
        "active_alerts": alerts,
    }

    context_json = json.dumps(context_payload, indent=2, ensure_ascii=False)

    system_instruction = (
        "You are an expert coastal environmental assistant for Confluence. "
        "Use ONLY the verified real-time data provided below to answer the user's question.\n"
        "Guidelines:\n"
        "1. Strictly ground your answer in the provided numbers (temperatures, wind speeds, wave heights, PM2.5, tides, seismic data, etc.).\n"
        "2. If the data does not cover something, state so plainly — do not guess or hallucinate.\n"
        "3. PROACTIVE SAFETY ALERT: If there are any active alerts or dangerous marine/weather conditions (e.g. hazardous wave heights, gale winds, poor air quality, rapid pressure drop), highlight them prominently and immediately unprompted.\n"
        "4. Provide clear, practical advice for fishermen, boaters, coastal residents, or tourists based on the data.\n"
        "5. Keep the response concise, authoritative, and well-structured with bullet points where appropriate."
    )

    user_content = (
        f"VERIFIED REAL-TIME COASTAL DATA & ALERTS:\n"
        f"```json\n{context_json}\n```\n\n"
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
            "max_tokens": 1024,
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
) -> Dict[str, Any]:
    """
    Main entry point for Phase 3:
    1. Matches question to a registered coastal location.
    2. If unmatched, returns graceful failure explaining registered stations (no LLM call).
    3. If matched, fetches live snapshot + active alerts.
    4. Formulates grounding prompt and queries LLM.
    5. Returns unified dictionary containing answer, location metadata, active alerts,
       and raw grounding data.
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
        }

    # Location matched — fetch live environmental intelligence
    snapshot, alerts = fetch_grounding_context(
        lat=loc["lat"],
        lon=loc["lon"],
        name=loc["name"],
        bypass_cache=bypass_cache,
    )

    messages = build_grounding_prompt(question, snapshot, alerts)
    answer = call_nvidia_llm(messages, model=model, api_key=api_key)

    return {
        "question": question,
        "location_matched": loc["name"],
        "location_used": loc["name"],
        "coordinates": {"lat": loc["lat"], "lon": loc["lon"]},
        "answer": answer,
        "active_alerts": alerts,
        "grounding_data": snapshot,
    }
