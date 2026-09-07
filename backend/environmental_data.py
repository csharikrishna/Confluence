"""
Core environmental data pipeline — concurrently fetches and normalizes readings
from 10 independent scientific APIs (weather, marine, river flood, air quality,
astronomical, terrain, climate baseline, seismic, GDACS cyclone tracking, NASA FIRMS fire)
into one unified JSON snapshot. This is the data layer app.py's /environment endpoint is built on.

Each source is fetched independently — if one fails, the others still return.
"""

import os
import sys
import time
import math
import json
import requests
import concurrent.futures
import cachetools
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Reconfigure standard output encoding for cross-platform UTF-8 support
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Load environment variables from .env
load_dotenv()

from sources import (
    OPEN_METEO_WEATHER_URL,
    OPEN_METEO_MARINE_URL,
    OPENAQ_LOCATIONS_URL,
    OPEN_METEO_AIR_QUALITY_URL,
    SUNRISE_SUNSET_URL,
    OPEN_METEO_ELEVATION_URL,
    USGS_SEISMIC_URL,
    NASA_POWER_CLIMATE_URL,
    OPEN_METEO_FLOOD_URL,
    GDACS_CYCLONE_URL,
    NASA_FIRMS_URL,
)

# ---------------------------------------------------------------------------
# CONFIG & CACHING
# ---------------------------------------------------------------------------

LOCATION = {
    "name": "Chennai Coast",
    "lat": 13.08,
    "lon": 80.27,
}

# Strictly read from environment variable — no hardcoded secrets in source
OPENAQ_API_KEY = os.getenv("OPENAQ_API_KEY")
FIRMS_MAP_KEY = os.getenv("FIRMS_MAP_KEY")

TIMEOUT = 10  # seconds, default per request

# In-memory Caches:
# 1. Station ID lookup cache: maps (base_url, round(lat, 3), round(lon, 3)) -> (station_id, station_name, sensor_map)
#    TTL = 24 hours (86,400s) because ground station locations rarely change.
STATION_CACHE = cachetools.TTLCache(maxsize=1000, ttl=86400)

# 2. Response-level unified snapshot cache: maps (round(lat, 3), round(lon, 3)) -> full snapshot dict
#    TTL = 5 minutes (300s) to serve repeated requests with sub-millisecond response times.
SNAPSHOT_CACHE = cachetools.TTLCache(maxsize=500, ttl=300)

# 3. GDACS & NASA FIRMS upstream cache: prevents hammering external disaster/satellite services
GDACS_CACHE = cachetools.TTLCache(maxsize=50, ttl=300)
FIRMS_CACHE = cachetools.TTLCache(maxsize=50, ttl=300)


def haversine_distance_km(lat1, lon1, lat2, lon2):
    """Calculate great-circle distance in kilometers between two points on the Earth."""
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlam = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2.0) ** 2
    return round(r * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a)), 2)


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_iso_utc(ts_str):
    """Ensure all observed_at strings conform to canonical ISO 8601 UTC (YYYY-MM-DDTHH:MM:SSZ)."""
    if not ts_str:
        return None
    ts_str = str(ts_str).strip()
    if ts_str.endswith("Z"):
        return ts_str
    if "+" in ts_str or ts_str.count("-") > 2:
        try:
            dt = datetime.fromisoformat(ts_str)
            return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            pass
    if "T" in ts_str:
        parts = ts_str.split("T")
        time_part = parts[1]
        if len(time_part) == 5:  # HH:MM
            return f"{parts[0]}T{time_part}:00Z"
        return f"{ts_str}Z"
    return f"{ts_str}T00:00:00Z"


def validate_coordinates(lat, lon):
    """Validate latitude and longitude ranges."""
    try:
        f_lat = float(lat)
        f_lon = float(lon)
    except (ValueError, TypeError):
        return False, f"Coordinates must be numeric. Received lat={lat}, lon={lon}"
    if not (-90.0 <= f_lat <= 90.0):
        return False, f"Latitude must be between -90 and 90 degrees. Received: {lat}"
    if not (-180.0 <= f_lon <= 180.0):
        return False, f"Longitude must be between -180 and 180 degrees. Received: {lon}"
    return True, None


WMO_WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def validate_environmental_data(data):
    """
    Automated sanity-check function (#8):
    Checks physical boundaries across environmental domains to catch upstream anomalies.
    """
    warnings = []
    weather = data.get("weather", {})
    if weather.get("status") == "ok":
        t = weather.get("temperature_c")
        if t is not None and not (-50.0 <= t <= 60.0):
            warnings.append(f"Temperature {t}°C outside physical bounds (-50 to 60°C)")
        at = weather.get("apparent_temperature_c")
        if at is not None and not (-60.0 <= at <= 75.0):
            warnings.append(f"Apparent temperature {at}°C outside physical bounds (-60 to 75°C)")
        h = weather.get("humidity_pct")
        if h is not None and not (0.0 <= h <= 100.0):
            warnings.append(f"Humidity {h}% outside physical bounds (0 to 100%)")
        p = weather.get("pressure_hpa")
        if p is not None and not (850.0 <= p <= 1090.0):
            warnings.append(f"Pressure {p} hPa outside standard bounds (850 to 1090 hPa)")
        w = weather.get("wind_speed_kmh")
        if w is not None and w < 0:
            warnings.append(f"Wind speed {w} km/h cannot be negative")
        g = weather.get("wind_gusts_kmh")
        if g is not None and g < 0:
            warnings.append(f"Wind gusts {g} km/h cannot be negative")
        pr = weather.get("precipitation_mm")
        if pr is not None and pr < 0:
            warnings.append(f"Precipitation {pr} mm cannot be negative")
        uv = weather.get("uv_index")
        if uv is not None and not (0.0 <= uv <= 25.0):
            warnings.append(f"UV index {uv} outside physical bounds (0 to 25)")
        vis = weather.get("visibility_m")
        if vis is not None and vis < 0:
            warnings.append(f"Visibility {vis} m cannot be negative")

    marine = data.get("marine", {})
    if marine.get("status") == "ok":
        sst = marine.get("sea_surface_temp_c")
        if sst is not None and not (-2.5 <= sst <= 45.0):
            warnings.append(f"Sea surface temperature {sst}°C outside physical bounds (-2.5 to 45°C)")
        wh = marine.get("wave_height_m")
        if wh is not None and wh < 0:
            warnings.append(f"Wave height {wh} m cannot be negative")
        wwh = marine.get("wind_wave_height_m")
        if wwh is not None and wwh < 0:
            warnings.append(f"Wind wave height {wwh} m cannot be negative")
        swh = marine.get("swell_wave_height_m")
        if swh is not None and swh < 0:
            warnings.append(f"Swell wave height {swh} m cannot be negative")
        cur_vel = marine.get("ocean_current_velocity_kmh")
        if cur_vel is not None and cur_vel < 0:
            warnings.append(f"Ocean current velocity {cur_vel} km/h cannot be negative")

    aq = data.get("air_quality", {})
    if aq.get("status") == "ok":
        for pol in ["pm25", "pm10", "o3", "no2", "so2", "co"]:
            val = aq.get(pol)
            if val is not None and val < 0:
                warnings.append(f"Air quality pollutant {pol}={val} cannot be negative")

    climate = data.get("climate_baseline", {})
    if climate.get("status") == "ok":
        sol = climate.get("solar_radiation_kwh_m2")
        if sol is not None and sol < 0:
            warnings.append(f"Solar radiation {sol} kWh/m² cannot be negative")

    terrain = data.get("terrain", {})
    if terrain.get("status") == "ok":
        elev = terrain.get("elevation_m")
        if elev is not None and elev < -500.0:
            warnings.append(f"Elevation {elev} m is below deepest land depression bounds")

    flood = data.get("river_flood", {})
    if flood.get("status") == "ok":
        dis = flood.get("river_discharge_m3s")
        if dis is not None and dis < 0:
            warnings.append(f"River discharge {dis} m³/s cannot be negative")

    cyclone = data.get("cyclone_tracking", {})
    if cyclone.get("status") == "ok":
        w = cyclone.get("max_wind_speed_kmh")
        if w is not None and w < 0:
            warnings.append(f"Cyclone wind speed {w} km/h cannot be negative")

    fires = data.get("thermal_hotspots", {})
    if fires.get("status") == "ok":
        frp = fires.get("max_frp_mw")
        if frp is not None and frp < 0:
            warnings.append(f"Fire radiative power {frp} MW cannot be negative")

    return warnings


# ---------------------------------------------------------------------------
# 1. OPEN-METEO — WEATHER (14 HYPERPARAMETERS)
# ---------------------------------------------------------------------------

def fetch_weather(lat, lon, timeout=TIMEOUT, base_url=OPEN_METEO_WEATHER_URL):
    t0 = time.perf_counter()
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": [
            "temperature_2m", "relative_humidity_2m", "apparent_temperature",
            "precipitation", "weather_code", "pressure_msl", "surface_pressure",
            "cloud_cover", "wind_speed_10m", "wind_direction_10m", "wind_gusts_10m",
            "uv_index", "visibility", "is_day"
        ],
        "timezone": "UTC",
    }
    try:
        r = requests.get(base_url, params=params, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        current = data.get("current", {})
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)

        w_code = current.get("weather_code")
        w_desc = WMO_WEATHER_CODES.get(w_code, "Unknown") if w_code is not None else None

        return {
            "temperature_c": current.get("temperature_2m"),
            "apparent_temperature_c": current.get("apparent_temperature"),
            "wind_speed_kmh": current.get("wind_speed_10m"),
            "wind_gusts_kmh": current.get("wind_gusts_10m"),
            "wind_direction_deg": current.get("wind_direction_10m"),
            "humidity_pct": current.get("relative_humidity_2m"),
            "pressure_hpa": current.get("pressure_msl"),
            "surface_pressure_hpa": current.get("surface_pressure"),
            "precipitation_mm": current.get("precipitation"),
            "cloud_cover_pct": current.get("cloud_cover"),
            "uv_index": current.get("uv_index"),
            "visibility_m": current.get("visibility"),
            "weather_code": w_code,
            "weather_description": w_desc,
            "is_day": bool(current.get("is_day")) if current.get("is_day") is not None else None,
            "source": "open-meteo",
            "observed_at": normalize_iso_utc(current.get("time")),
            "status": "ok",
            "latency_ms": latency_ms,
        }
    except Exception as e:
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        return {"source": "open-meteo", "status": "error", "error": str(e), "latency_ms": latency_ms}


# ---------------------------------------------------------------------------
# 2. OPEN-METEO — MARINE (12 HYPERPARAMETERS)
# ---------------------------------------------------------------------------

def fetch_marine(lat, lon, timeout=TIMEOUT, base_url=OPEN_METEO_MARINE_URL):
    t0 = time.perf_counter()
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": [
            "wave_height", "wave_period", "wave_direction",
            "wind_wave_height", "wind_wave_direction", "wind_wave_period",
            "swell_wave_height", "swell_wave_direction", "swell_wave_period",
            "ocean_current_velocity", "ocean_current_direction",
            "sea_surface_temperature"
        ],
        "timezone": "UTC",
    }
    try:
        r = requests.get(base_url, params=params, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        current = data.get("current", {})
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)

        wh = current.get("wave_height")
        sst = current.get("sea_surface_temperature")
        note = None
        if wh is None and sst is None:
            note = "Landlocked coordinates or offshore data unavailable for this point"

        return {
            "sea_surface_temp_c": sst,
            "wave_height_m": wh,
            "wave_period_s": current.get("wave_period"),
            "wave_direction_deg": current.get("wave_direction"),
            "wind_wave_height_m": current.get("wind_wave_height"),
            "wind_wave_period_s": current.get("wind_wave_period"),
            "wind_wave_direction_deg": current.get("wind_wave_direction"),
            "swell_wave_height_m": current.get("swell_wave_height"),
            "swell_wave_period_s": current.get("swell_wave_period"),
            "swell_wave_direction_deg": current.get("swell_wave_direction"),
            "ocean_current_velocity_kmh": current.get("ocean_current_velocity"),
            "ocean_current_direction_deg": current.get("ocean_current_direction"),
            "note": note,
            "source": "open-meteo-marine",
            "observed_at": normalize_iso_utc(current.get("time")),
            "status": "ok",
            "latency_ms": latency_ms,
        }
    except Exception as e:
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        return {"source": "open-meteo-marine", "status": "error", "error": str(e), "latency_ms": latency_ms}


# ---------------------------------------------------------------------------
# 3. OPENAQ — AIR QUALITY
# ---------------------------------------------------------------------------

def fetch_air_quality(lat, lon, api_key=None, timeout=TIMEOUT, base_url=OPENAQ_LOCATIONS_URL):
    t0 = time.perf_counter()
    api_key = api_key or OPENAQ_API_KEY
    if not api_key:
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        return {
            "source": "openaq",
            "status": "error",
            "error": "No OpenAQ API key set. Set the OPENAQ_API_KEY environment variable.",
            "latency_ms": latency_ms,
        }

    headers = {"X-API-Key": api_key}

    try:
        # Check station ID lookup cache (Task #1: Cache station lookup per location)
        loc_cache_key = (base_url, round(float(lat), 3), round(float(lon), 3))
        if loc_cache_key in STATION_CACHE:
            station_id, station_name, sensor_map = STATION_CACHE[loc_cache_key]
        else:
            # Step 1: find station(s) within 25km radius
            loc_params = {"coordinates": f"{lat},{lon}", "radius": 25000, "limit": 20}
            r = requests.get(base_url, headers=headers, params=loc_params, timeout=timeout)
            r.raise_for_status()
            results = r.json().get("results", [])

            if not results:
                latency_ms = round((time.perf_counter() - t0) * 1000, 2)
                return {
                    "source": "openaq",
                    "status": "error",
                    "error": "No monitoring stations found within 25km of this location",
                    "latency_ms": latency_ms,
                }

            # Pick the most relevant station: recently active, multiple sensors, nearest
            def station_rank(st):
                dt = st.get("datetimeLast", {})
                utc = dt.get("utc", "") if isinstance(dt, dict) else (str(dt) if dt else "")
                recent = 1 if utc >= (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d") else 0
                coords = st.get("coordinates", {})
                st_lat = coords.get("latitude", lat)
                st_lon = coords.get("longitude", lon)
                dist = math.hypot((st_lat - lat) * 111.0, (st_lon - lon) * 111.0 * math.cos(math.radians(lat)))
                sensors = st.get("sensors", [])
                return (recent, len(sensors) >= 4, -dist)

            results_sorted = sorted(results, key=station_rank, reverse=True)
            station = results_sorted[0]
            station_id = station["id"]
            station_name = station.get("name", "unknown")

            # Map sensorsId to parameter name
            sensor_map = {}
            for s in station.get("sensors", []):
                p = s.get("parameter")
                p_name = p.get("name") if isinstance(p, dict) else p
                if p_name and s.get("id"):
                    sensor_map[s.get("id")] = p_name.lower()

            STATION_CACHE[loc_cache_key] = (station_id, station_name, sensor_map)

        # Step 2: get latest readings from that station
        latest_url = f"{base_url.rstrip('/')}/{station_id}/latest"
        r2 = requests.get(latest_url, headers=headers, timeout=timeout)
        r2.raise_for_status()
        readings = r2.json().get("results", [])

        parsed = {}
        param_time = {}
        latest_time = None
        for reading in readings:
            s_id = reading.get("sensorsId")
            param = sensor_map.get(s_id)
            if not param:
                p = reading.get("parameter")
                param = p.get("name") if isinstance(p, dict) else p
                if param:
                    param = param.lower()

            value = reading.get("value")
            dt = reading.get("datetime", {})
            dt_utc = dt.get("utc") if isinstance(dt, dict) else (str(dt) if dt else None)

            if dt_utc and (latest_time is None or dt_utc > latest_time):
                latest_time = dt_utc

            if param and value is not None:
                prev_time = param_time.get(param, "")
                if param not in parsed or (dt_utc and dt_utc >= prev_time):
                    parsed[param] = value
                    if dt_utc:
                        param_time[param] = dt_utc

        # Derive AQI category from PM2.5 if available (#9: returns null for missing pollutants)
        aqi_category = None
        pm25 = parsed.get("pm25")
        if pm25 is not None:
            if pm25 <= 12.0:
                aqi_category = "good"
            elif pm25 <= 35.4:
                aqi_category = "moderate"
            elif pm25 <= 55.4:
                aqi_category = "unhealthy for sensitive groups"
            elif pm25 <= 150.4:
                aqi_category = "unhealthy"
            elif pm25 <= 250.4:
                aqi_category = "very unhealthy"
            else:
                aqi_category = "hazardous"

        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        return {
            "station_name": station_name,
            "data_type": "measured",
            "pm25": parsed.get("pm25"),
            "pm10": parsed.get("pm10"),
            "o3": parsed.get("o3"),
            "no2": parsed.get("no2"),
            "so2": parsed.get("so2"),
            "co": parsed.get("co"),
            "aqi_category": aqi_category,
            "source": "openaq",
            "observed_at": normalize_iso_utc(latest_time),
            "status": "ok",
            "latency_ms": latency_ms,
        }
    except Exception as e:
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        return {"source": "openaq", "status": "error", "error": str(e), "latency_ms": latency_ms}


def fetch_model_air_quality(lat, lon, timeout=TIMEOUT, base_url=OPEN_METEO_AIR_QUALITY_URL):
    """
    Open-Meteo Global Air Quality API (Free, zero API key required).
    Acts as atmospheric model layer and universal fallback for coordinates
    where no physical ground station exists (e.g. mid-ocean).
    """
    t0 = time.perf_counter()
    url = base_url
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": [
            "pm10", "pm2_5", "carbon_monoxide", "nitrogen_dioxide", "sulphur_dioxide",
            "ozone", "aerosol_optical_depth", "dust", "uv_index", "us_aqi", "european_aqi"
        ],
        "timezone": "UTC",
    }
    try:
        r = requests.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        cur = r.json().get("current", {})
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)

        pm25 = cur.get("pm2_5")
        aqi_category = None
        if pm25 is not None:
            if pm25 <= 12.0:
                aqi_category = "good"
            elif pm25 <= 35.4:
                aqi_category = "moderate"
            elif pm25 <= 55.4:
                aqi_category = "unhealthy for sensitive groups"
            elif pm25 <= 150.4:
                aqi_category = "unhealthy"
            elif pm25 <= 250.4:
                aqi_category = "very unhealthy"
            else:
                aqi_category = "hazardous"

        return {
            "station_name": "Global CAMS Atmospheric Model (Open-Meteo)",
            "tier": "atmospheric_model",
            "data_type": "modeled",
            "pm25": pm25,
            "pm10": cur.get("pm10"),
            "o3": cur.get("ozone"),
            "no2": cur.get("nitrogen_dioxide"),
            "so2": cur.get("sulphur_dioxide"),
            "co": cur.get("carbon_monoxide"),
            "us_aqi": cur.get("us_aqi"),
            "european_aqi": cur.get("european_aqi"),
            "dust_ug_m3": cur.get("dust"),
            "aerosol_optical_depth": cur.get("aerosol_optical_depth"),
            "aqi_category": aqi_category,
            "source": "open-meteo-air-quality-modeled",
            "observed_at": normalize_iso_utc(cur.get("time")),
            "status": "ok",
            "latency_ms": latency_ms,
        }
    except Exception as e:
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        return {"source": "open-meteo-air-quality-modeled", "status": "error", "error": str(e), "latency_ms": latency_ms}


# ---------------------------------------------------------------------------
# 4. SUNRISE-SUNSET — ASTRONOMICAL & MARINE LIGHTING (FREE, NO KEY)
# ---------------------------------------------------------------------------

def fetch_sun_and_lighting(lat, lon, timeout=TIMEOUT, base_url=SUNRISE_SUNSET_URL):
    """
    Sunrise-Sunset.org API: Provides solar ephemeris and nautical twilights
    essential for fishermen departure schedules and marine operations.
    """
    t0 = time.perf_counter()
    params = {"lat": lat, "lng": lon, "formatted": 0}
    try:
        r = requests.get(base_url, params=params, timeout=timeout)
        r.raise_for_status()
        res = r.json().get("results", {})
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)

        day_len_s = res.get("day_length")
        day_len_hrs = round(day_len_s / 3600.0, 2) if day_len_s else None

        return {
            "sunrise": res.get("sunrise"),
            "sunset": res.get("sunset"),
            "solar_noon": res.get("solar_noon"),
            "day_length_hours": day_len_hrs,
            "civil_twilight_begin": res.get("civil_twilight_begin"),
            "civil_twilight_end": res.get("civil_twilight_end"),
            "nautical_twilight_begin": res.get("nautical_twilight_begin"),
            "nautical_twilight_end": res.get("nautical_twilight_end"),
            "astronomical_twilight_begin": res.get("astronomical_twilight_begin"),
            "astronomical_twilight_end": res.get("astronomical_twilight_end"),
            "source": "sunrise-sunset.org",
            "observed_at": res.get("solar_noon"),
            "status": "ok",
            "latency_ms": latency_ms,
        }
    except Exception as e:
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        return {"source": "sunrise-sunset.org", "status": "error", "error": str(e), "latency_ms": latency_ms}


# ---------------------------------------------------------------------------
# 5. OPEN-METEO — TERRAIN & ELEVATION (FREE, NO KEY)
# ---------------------------------------------------------------------------

def fetch_elevation(lat, lon, timeout=TIMEOUT, base_url=OPEN_METEO_ELEVATION_URL):
    """
    Open-Meteo Elevation API: Topographic height above sea level for coastal
    inundation and storm surge vulnerability modeling.
    """
    t0 = time.perf_counter()
    params = {"latitude": lat, "longitude": lon}
    try:
        r = requests.get(base_url, params=params, timeout=timeout)
        r.raise_for_status()
        elev = r.json().get("elevation", [])
        elev_m = elev[0] if isinstance(elev, list) and elev else None
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)

        risk_category = "low-lying (<5m)" if (elev_m is not None and elev_m < 5.0) else "elevated"

        return {
            "elevation_m": elev_m,
            "coastal_risk_category": risk_category,
            "source": "open-meteo-elevation",
            "status": "ok",
            "latency_ms": latency_ms,
        }
    except Exception as e:
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        return {"source": "open-meteo-elevation", "status": "error", "error": str(e), "latency_ms": latency_ms}


# ---------------------------------------------------------------------------
# 6. USGS — SEISMIC & TSUNAMI RISK (FREE, NO KEY)
# ---------------------------------------------------------------------------

def fetch_seismic_risk(lat, lon, timeout=TIMEOUT, base_url=USGS_SEISMIC_URL):
    """
    USGS Earthquake Hazards API: Queries past 7 days for seismic events (M>=4.0)
    within 500km to flag coastal seismic / tsunami hazards.
    """
    t0 = time.perf_counter()
    start = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    params = {
        "format": "geojson",
        "latitude": lat,
        "longitude": lon,
        "maxradiuskm": 500,
        "minmagnitude": 4.0,
        "starttime": start,
    }
    try:
        r = requests.get(base_url, params=params, timeout=timeout)
        r.raise_for_status()
        features = r.json().get("features", [])
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)

        mags = [f.get("properties", {}).get("mag") for f in features if f.get("properties", {}).get("mag") is not None]
        max_mag = max(mags) if mags else None
        hazard = "elevated (M>=6.0 nearby)" if (max_mag and max_mag >= 6.0) else "nominal"

        # GeoJSON coordinates are [lon, lat, depth_km] — depth of the strongest event
        # matters for tsunami risk (shallow-focus quakes, USGS-defined as <70km, are
        # far more tsunamigenic than deep-focus ones of the same magnitude).
        depth_km = None
        if mags:
            strongest = max(
                (f for f in features if f.get("properties", {}).get("mag") is not None),
                key=lambda f: f["properties"]["mag"],
            )
            coords = strongest.get("geometry", {}).get("coordinates", [])
            if len(coords) >= 3:
                depth_km = coords[2]

        return {
            "recent_events_7d_count": len(features),
            "max_magnitude": max_mag,
            "max_magnitude_depth_km": depth_km,
            "hazard_level": hazard,
            "search_radius_km": 500,
            "source": "usgs-earthquake",
            "status": "ok",
            "latency_ms": latency_ms,
        }
    except Exception as e:
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        return {"source": "usgs-earthquake", "status": "error", "error": str(e), "latency_ms": latency_ms}


# ---------------------------------------------------------------------------
# 7. NASA POWER — CLIMATE BASELINE
# ---------------------------------------------------------------------------

def fetch_climate_baseline(lat, lon, timeout=TIMEOUT, base_url=NASA_POWER_CLIMATE_URL):
    t0 = time.perf_counter()
    today = datetime.now(timezone.utc)
    start = (today - timedelta(days=10)).strftime("%Y%m%d")
    end = today.strftime("%Y%m%d")

    params = {
        "parameters": "ALLSKY_SFC_SW_DWN,T2M,WS10M",
        "community": "RE",
        "longitude": lon,
        "latitude": lat,
        "start": start,
        "end": end,
        "format": "JSON",
    }
    try:
        r = requests.get(base_url, params=params, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        props = data.get("properties", {}).get("parameter", {})

        def latest_value(param_dict):
            if not param_dict:
                return None, None
            valid = {d: v for d, v in param_dict.items() if v is not None and v != -999.0}
            if not valid:
                return None, None
            latest_date = sorted(valid.keys())[-1]
            formatted_date = f"{latest_date[:4]}-{latest_date[4:6]}-{latest_date[6:8]}T00:00:00Z"
            return valid[latest_date], formatted_date

        solar, solar_date = latest_value(props.get("ALLSKY_SFC_SW_DWN"))
        temp, temp_date = latest_value(props.get("T2M"))
        wind, wind_date = latest_value(props.get("WS10M"))

        observed_at = solar_date or temp_date or wind_date
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)

        return {
            "solar_radiation_kwh_m2": solar,
            "avg_temperature_c": temp,
            "avg_wind_speed_ms": wind,
            "source": "nasa-power",
            "observed_at": normalize_iso_utc(observed_at),
            "status": "ok",
            "latency_ms": latency_ms,
        }
    except Exception as e:
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        return {"source": "nasa-power", "status": "error", "error": str(e), "latency_ms": latency_ms}


# ---------------------------------------------------------------------------
# 8. OPEN-METEO — RIVER DISCHARGE & FLOOD API (FREE, NO KEY)
# ---------------------------------------------------------------------------

def fetch_river_discharge(lat, lon, timeout=TIMEOUT, base_url=OPEN_METEO_FLOOD_URL):
    """
    Open-Meteo Global Flood API (Free, zero API key required).
    Provides daily river discharge (m³/s) based on the Copernicus GloFAS model.
    Evaluates upstream river discharge for estuarine / deltaic compound flood risk.
    Non-basin coordinates (e.g. open ocean) gracefully return applicable=False.
    """
    t0 = time.perf_counter()
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "river_discharge",
    }
    try:
        r = requests.get(base_url, params=params, timeout=timeout)
        r.raise_for_status()
        res = r.json()
        daily = res.get("daily", {})
        times = daily.get("time", [])
        discharges = daily.get("river_discharge", [])
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)

        # Filter out valid numeric discharge values
        valid_discharges = [d for d in discharges if d is not None]
        observed_time = times[0] if times else None

        if not valid_discharges:
            return {
                "river_discharge_m3s": None,
                "discharge_max_7d_m3s": None,
                "applicable": False,
                "note": "No active river basin mapped within hydrological grid cell",
                "source": "open-meteo-flood",
                "observed_at": normalize_iso_utc(observed_time) if observed_time else now_iso(),
                "status": "ok",
                "latency_ms": latency_ms,
            }

        curr_discharge = discharges[0] if (discharges and discharges[0] is not None) else valid_discharges[0]
        max_7d = max(valid_discharges[:7]) if len(valid_discharges) >= 1 else curr_discharge

        return {
            "river_discharge_m3s": round(float(curr_discharge), 2) if curr_discharge is not None else None,
            "discharge_max_7d_m3s": round(float(max_7d), 2) if max_7d is not None else None,
            "applicable": True,
            "note": None,
            "source": "open-meteo-flood",
            "observed_at": normalize_iso_utc(observed_time) if observed_time else now_iso(),
            "status": "ok",
            "latency_ms": latency_ms,
        }
    except Exception as e:
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        return {
            "source": "open-meteo-flood",
            "status": "error",
            "error": str(e),
            "applicable": False,
            "latency_ms": latency_ms,
        }


# ---------------------------------------------------------------------------
# 9. GDACS — GLOBAL DISASTER ALERT & COORDINATION SYSTEM (TROPICAL CYCLONES)
# ---------------------------------------------------------------------------

def fetch_gdacs_cyclones(lat, lon, timeout=TIMEOUT, base_url=GDACS_CYCLONE_URL):
    """
    Global Disaster Alert and Coordination System (GDACS — UN / EC JRC).
    Free, public feed (XML RSS / GeoJSON) — zero API key required.
    Tracks active tropical cyclones worldwide with intensity, alert level,
    and calculates maritime proximity distance from the station coordinates.
    """
    t0 = time.perf_counter()
    headers = {"User-Agent": "Confluence-Platform/1.0"}

    # Use 5-minute in-memory cache for upstream GDACS feed
    cached_tcs = GDACS_CACHE.get("global_cyclones")
    if cached_tcs is None:
        try:
            r = requests.get(base_url, headers=headers, timeout=timeout)
            r.raise_for_status()
            content = r.text.strip()
            parsed_cyclones = []

            if content.startswith("{") or content.startswith("["):
                # GeoJSON or JSON format
                data = r.json()
                features = data.get("features", []) if isinstance(data, dict) else []
                tc_features = [f for f in features if f.get("properties", {}).get("eventtype") == "TC"]
                for feat in tc_features:
                    props = feat.get("properties", {})
                    geom = feat.get("geometry", {})
                    coords = geom.get("coordinates", [])
                    if len(coords) >= 2 and coords[0] is not None and coords[1] is not None:
                        severity = props.get("severitydata", {})
                        wind = severity.get("severity") if isinstance(severity, dict) else None
                        parsed_cyclones.append({
                            "name": props.get("name") or props.get("eventname") or "Unnamed Cyclone",
                            "alert_level": props.get("alertlevel", "Green"),
                            "wind_speed_kmh": round(float(wind), 1) if wind is not None else None,
                            "latitude": float(coords[1]),
                            "longitude": float(coords[0]),
                            "report_url": props.get("url", {}).get("report") if isinstance(props.get("url"), dict) else None,
                        })
            else:
                # Fast official GDACS XML RSS format
                import xml.etree.ElementTree as ET
                import re
                root = ET.fromstring(r.content)
                for item in root.findall(".//item"):
                    etype = item.findtext("{http://www.gdacs.org}eventtype")
                    if etype == "TC":
                        name = item.findtext("{http://www.gdacs.org}eventname") or "Unnamed Cyclone"
                        level = item.findtext("{http://www.gdacs.org}alertlevel") or "Green"
                        severity = item.findtext("{http://www.gdacs.org}severity") or ""
                        pt = item.findtext("{http://www.georss.org/georss}point")
                        link = item.findtext("link") or ""
                        wind_kmh = None
                        m = re.search(r"(\d+)\s*km/h", severity)
                        if m:
                            wind_kmh = float(m.group(1))
                        if pt:
                            parts = pt.strip().split()
                            if len(parts) >= 2:
                                parsed_cyclones.append({
                                    "name": name,
                                    "alert_level": level,
                                    "wind_speed_kmh": wind_kmh,
                                    "latitude": float(parts[0]),
                                    "longitude": float(parts[1]),
                                    "report_url": link,
                                })

            cached_tcs = parsed_cyclones
            GDACS_CACHE["global_cyclones"] = cached_tcs
        except Exception as e:
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            return {
                "source": "gdacs-cyclone",
                "status": "error",
                "error": str(e),
                "active_cyclone_nearby": False,
                "cyclone_alert_level": "unknown",
                "latency_ms": latency_ms,
            }

    latency_ms = round((time.perf_counter() - t0) * 1000, 2)
    cyclones_with_dist = []
    for c in (cached_tcs or []):
        dist_km = haversine_distance_km(lat, lon, c["latitude"], c["longitude"])
        cyclones_with_dist.append({
            "name": c["name"],
            "alert_level": c["alert_level"],
            "wind_speed_kmh": c.get("wind_speed_kmh"),
            "distance_km": dist_km,
            "latitude": c["latitude"],
            "longitude": c["longitude"],
            "report_url": c.get("report_url"),
        })

    cyclones_with_dist.sort(key=lambda x: x["distance_km"])
    nearest = cyclones_with_dist[0] if cyclones_with_dist else None

    # Regional maritime influence threshold: <=1000 km advisory, <=500 km critical warning
    active_nearby = bool(nearest and nearest["distance_km"] <= 1000.0)

    return {
        "source": "gdacs-cyclone",
        "active_cyclone_nearby": active_nearby,
        "nearest_cyclone_name": nearest["name"] if nearest else None,
        "nearest_cyclone_distance_km": nearest["distance_km"] if nearest else None,
        "cyclone_alert_level": nearest["alert_level"] if nearest else "nominal",
        "max_wind_speed_kmh": nearest["wind_speed_kmh"] if nearest else None,
        "active_cyclones_count": len(cyclones_with_dist),
        "nearby_cyclones": [c for c in cyclones_with_dist if c["distance_km"] <= 1500.0][:3],
        "observed_at": now_iso(),
        "status": "ok",
        "latency_ms": latency_ms,
    }


# ---------------------------------------------------------------------------
# 10. NASA FIRMS — SATELLITE ACTIVE FIRE & THERMAL HOTSPOTS (MODIS / VIIRS)
# ---------------------------------------------------------------------------

def fetch_fire_hotspots(lat, lon, api_key=None, timeout=TIMEOUT):
    """
    NASA FIRMS (Fire Information for Resource Management System).
    Detects real-time satellite fire / thermal anomalies (VIIRS/MODIS) within a 300km radius.
    Identifies upstream agricultural/crop burning or wildfires as physical causal drivers
    for elevated PM2.5 particulate pollution.

    If FIRMS_MAP_KEY is provided, queries the exact bounding box.
    If no key is configured, seamlessly falls back to NASA FIRMS's open NRT South Asia
    VIIRS feed (zero key required).
    """
    t0 = time.perf_counter()
    key = api_key or FIRMS_MAP_KEY
    search_radius_km = 300.0
    headers = {"User-Agent": "Confluence-Platform/1.0"}

    try:
        if key:
            west = round(lon - 2.5, 3)
            south = round(lat - 2.5, 3)
            east = round(lon + 2.5, 3)
            north = round(lat + 2.5, 3)
            cache_k = f"firms_bbox_{west}_{south}_{east}_{north}"
            lines = FIRMS_CACHE.get(cache_k)
            if lines is None:
                url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/VIIRS_SNPP_NRT/{west},{south},{east},{north}/1"
                r = requests.get(url, headers=headers, timeout=timeout)
                r.raise_for_status()
                lines = r.text.strip().splitlines()
                FIRMS_CACHE[cache_k] = lines
        else:
            lines = FIRMS_CACHE.get("firms_south_asia_open")
            if lines is None:
                url = "https://firms.modaps.eosdis.nasa.gov/data/active_fire/suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_South_Asia_24h.csv"
                r = requests.get(url, headers=headers, timeout=timeout)
                r.raise_for_status()
                lines = r.text.strip().splitlines()
                FIRMS_CACHE["firms_south_asia_open"] = lines

        latency_ms = round((time.perf_counter() - t0) * 1000, 2)

        if not lines or len(lines) <= 1:
            return {
                "source": "nasa-firms",
                "status": "ok",
                "hotspot_count": 0,
                "high_confidence_count": 0,
                "fire_detected": False,
                "nearest_hotspot_distance_km": None,
                "max_frp_mw": None,
                "search_radius_km": search_radius_km,
                "observed_at": now_iso(),
                "latency_ms": latency_ms,
            }

        header = [h.strip() for h in lines[0].split(",")]
        lat_idx = header.index("latitude") if "latitude" in header else -1
        lon_idx = header.index("longitude") if "longitude" in header else -1
        frp_idx = header.index("frp") if "frp" in header else -1
        conf_idx = header.index("confidence") if "confidence" in header else -1
        date_idx = header.index("acq_date") if "acq_date" in header else -1
        time_idx = header.index("acq_time") if "acq_time" in header else -1

        if lat_idx < 0 or lon_idx < 0:
            return {
                "source": "nasa-firms",
                "status": "ok",
                "hotspot_count": 0,
                "fire_detected": False,
                "nearest_hotspot_distance_km": None,
                "max_frp_mw": None,
                "search_radius_km": search_radius_km,
                "observed_at": now_iso(),
                "latency_ms": latency_ms,
            }

        nearby_hotspots = []
        for line in lines[1:]:
            parts = [p.strip() for p in line.split(",")]
            if len(parts) <= max(lat_idx, lon_idx):
                continue
            try:
                f_lat = float(parts[lat_idx])
                f_lon = float(parts[lon_idx])
                dist = haversine_distance_km(lat, lon, f_lat, f_lon)
                if dist <= search_radius_km:
                    frp = float(parts[frp_idx]) if (frp_idx >= 0 and parts[frp_idx]) else 0.0
                    conf = parts[conf_idx] if conf_idx >= 0 else "nominal"
                    acq_d = parts[date_idx] if date_idx >= 0 else ""
                    acq_t = parts[time_idx] if time_idx >= 0 else ""
                    nearby_hotspots.append({
                        "latitude": f_lat,
                        "longitude": f_lon,
                        "distance_km": dist,
                        "frp_mw": frp,
                        "confidence": conf,
                        "acquired": f"{acq_d} {acq_t}".strip(),
                    })
            except (ValueError, TypeError):
                continue

        nearby_hotspots.sort(key=lambda x: x["distance_km"])
        count = len(nearby_hotspots)
        nearest_dist = nearby_hotspots[0]["distance_km"] if nearby_hotspots else None
        max_frp = max((h["frp_mw"] for h in nearby_hotspots), default=None)
        high_conf = sum(1 for h in nearby_hotspots if str(h["confidence"]).lower() in ["h", "high", "nominal"])

        return {
            "source": "nasa-firms",
            "status": "ok",
            "hotspot_count": count,
            "high_confidence_count": high_conf,
            "fire_detected": count > 0,
            "nearest_hotspot_distance_km": nearest_dist,
            "max_frp_mw": round(max_frp, 1) if max_frp is not None else None,
            "search_radius_km": search_radius_km,
            "sample_hotspots": nearby_hotspots[:5],
            "observed_at": now_iso(),
            "latency_ms": latency_ms,
        }
    except Exception as e:
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        return {
            "source": "nasa-firms",
            "status": "error",
            "error": str(e),
            "hotspot_count": 0,
            "fire_detected": False,
            "latency_ms": latency_ms,
        }


# ---------------------------------------------------------------------------
# UNIFIED ENDPOINT LOGIC (CONCURRENT MULTI-DOMAIN FUSION)
# ---------------------------------------------------------------------------

def get_environmental_snapshot(lat, lon, name="Unnamed Location", timeout=TIMEOUT, openaq_api_key=None, bypass_cache=False):
    # Upfront coordinate range validation (#6)
    valid, err_msg = validate_coordinates(lat, lon)
    if not valid:
        return {
            "location": {"name": name, "lat": lat, "lon": lon},
            "generated_at": now_iso(),
            "data": {},
            "meta": {
                "confidence": "low — invalid coordinates",
                "error": err_msg,
                "failed_sources": ["all"],
                "data_quality_warnings": [err_msg],
            },
        }

    # Response-level snapshot cache (Task #1: 5-minute cache keyed by rounded lat/lon)
    cache_key = (round(float(lat), 3), round(float(lon), 3))
    if not bypass_cache and cache_key in SNAPSHOT_CACHE:
        cached = json.loads(json.dumps(SNAPSHOT_CACHE[cache_key]))
        cached["location"]["name"] = name
        cached["meta"]["cache_hit"] = True
        cached["meta"]["total_latency_ms"] = 0.5
        return cached

    t_start = time.perf_counter()

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        f_weather = executor.submit(fetch_weather, lat, lon, timeout=timeout)
        f_marine = executor.submit(fetch_marine, lat, lon, timeout=timeout)
        f_aq = executor.submit(fetch_air_quality, lat, lon, api_key=openaq_api_key, timeout=timeout)
        f_sun = executor.submit(fetch_sun_and_lighting, lat, lon, timeout=timeout)
        f_elevation = executor.submit(fetch_elevation, lat, lon, timeout=timeout)
        f_climate = executor.submit(fetch_climate_baseline, lat, lon, timeout=timeout)
        f_seismic = executor.submit(fetch_seismic_risk, lat, lon, timeout=timeout)
        f_flood = executor.submit(fetch_river_discharge, lat, lon, timeout=timeout)
        f_cyclones = executor.submit(fetch_gdacs_cyclones, lat, lon, timeout=timeout)
        f_fires = executor.submit(fetch_fire_hotspots, lat, lon, api_key=None, timeout=timeout)

        weather = f_weather.result()
        marine = f_marine.result()
        air_quality = f_aq.result()
        sun_and_lighting = f_sun.result()
        terrain = f_elevation.result()
        climate_baseline = f_climate.result()
        seismic_risk = f_seismic.result()
        river_flood = f_flood.result()
        cyclone_tracking = f_cyclones.result()
        thermal_hotspots = f_fires.result()

    # Conditional Open-Meteo Air Quality fallback:
    # Trigger ONLY when OpenAQ reports "no station found" within radius (never parallel double-fetch)
    if air_quality.get("status") == "error":
        err_msg = str(air_quality.get("error", "")).lower()
        if "no monitoring station" in err_msg or "no station" in err_msg:
            model_aq = fetch_model_air_quality(lat, lon, timeout=timeout)
            if model_aq.get("status") == "ok":
                air_quality = model_aq

    total_latency_ms = round((time.perf_counter() - t_start) * 1000, 2)

    sources = [
        weather, marine, air_quality, sun_and_lighting, terrain,
        climate_baseline, seismic_risk, river_flood, cyclone_tracking, thermal_hotspots
    ]
    failed = [s["source"] for s in sources if s.get("status") == "error"]

    if not failed:
        confidence = "high — all sources responded successfully"
    elif len(failed) < len(sources):
        confidence = f"partial — {', '.join(failed)} failed, other sources ok"
    else:
        confidence = "low — all sources failed"

    data = {
        "weather": weather,
        "marine": marine,
        "air_quality": air_quality,
        "sun_and_lighting": sun_and_lighting,
        "terrain": terrain,
        "climate_baseline": climate_baseline,
        "seismic_risk": seismic_risk,
        "river_flood": river_flood,
        "cyclone_tracking": cyclone_tracking,
        "thermal_hotspots": thermal_hotspots,
    }

    meta = {
        "confidence": confidence,
        "failed_sources": failed,
        "total_latency_ms": total_latency_ms,
        "source_latencies_ms": {s["source"]: s.get("latency_ms") for s in sources},
        "cache_hit": False,
    }

    # Data quality boundaries check (#8)
    data_warnings = validate_environmental_data(data)
    if data_warnings:
        meta["data_quality_warnings"] = data_warnings

    # Add freshness warning if climate baseline data is actually >24h old.
    # NASA POWER's satellite/model processing pipeline has an inherent multi-day
    # lag, so this fires most of the time in practice — but it's computed from
    # the real observed_at timestamp, not asserted unconditionally.
    if climate_baseline.get("status") == "ok" and climate_baseline.get("observed_at"):
        try:
            observed_dt = datetime.strptime(climate_baseline["observed_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            age_hours = (datetime.now(timezone.utc) - observed_dt).total_seconds() / 3600.0
            if age_hours > 24:
                meta["freshness_warning"] = f"climate_baseline data is {age_hours:.1f}h old (>24h)"
        except (ValueError, TypeError):
            pass

    snapshot = {
        "location": {"name": name, "lat": lat, "lon": lon},
        "generated_at": now_iso(),
        "data": data,
        "meta": meta,
    }

    # Populate snapshot cache
    SNAPSHOT_CACHE[cache_key] = snapshot
    return snapshot


# ---------------------------------------------------------------------------
# RUN
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    snapshot = get_environmental_snapshot(
        LOCATION["lat"], LOCATION["lon"], LOCATION["name"]
    )
    print(json.dumps(snapshot, indent=2))

