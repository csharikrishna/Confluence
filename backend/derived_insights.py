"""
Physics-informed composite signals.

Phase 1's 50+ hyperparameters are individually correct but not connected — an LLM
reading raw temperature_c=35.4 and humidity_pct=94 has to do the physiological-heat-
stress arithmetic itself, which is exactly where hallucination creeps in. This module
does that arithmetic once, server-side, using established physical/meteorological
formulas (NOAA's heat index regression, the Magnus-Tetens dew point approximation,
Beaufort-scale-informed sea-state thresholds) rather than any learned/ML model —
composite, deterministic, and auditable, in keeping with Phase 2's "no ML" scope.

Every function tolerates missing inputs (returns None / "unknown") since upstream
sources fail independently and any domain here may be absent.
"""

import math

# Beaufort wind force scale (WMO-adopted, standard km/h upper bounds per force).
_BEAUFORT_BANDS = [
    (1, "calm"), (5, "light air"), (11, "light breeze"), (19, "gentle breeze"),
    (28, "moderate breeze"), (38, "fresh breeze"), (49, "strong breeze"),
    (61, "near gale"), (74, "gale"), (88, "strong gale"), (102, "storm"),
    (117, "violent storm"),
]

# NWS coastal marine warning wind criteria, knots converted to km/h (1kt = 1.852km/h):
#   Small Craft Advisory: 18-33kt (33.3-61.1 km/h)
#   Gale Warning:         34-47kt (63.0-87.0 km/h)
#   Storm Warning:        48-63kt (88.9-116.7 km/h)
#   Hurricane Force Wind Warning: >=64kt (>=118.5 km/h)
_SCA_WIND_KMH = 18 * 1.852
_GALE_WIND_KMH = 34 * 1.852
_STORM_WIND_KMH = 48 * 1.852
_HURRICANE_WIND_KMH = 64 * 1.852

# Small Craft Advisory sea-height criterion commonly published by NWS coastal/offshore
# marine zones (~7ft). Gale/storm sea-state bands scaled up from there.
_SCA_WAVE_M = 2.1
_GALE_WAVE_M = 3.5
_STORM_WAVE_M = 5.5

# IMD (India Meteorological Department) official classification of low-pressure
# systems by maximum sustained surface wind speed (km/h) — the relevant authority
# for the Indian coastal locations this service targets.
_IMD_BANDS = [
    (31, "low_pressure_area"), (49, "depression"), (61, "deep_depression"),
    (88, "cyclonic_storm"), (117, "severe_cyclonic_storm"),
    (165, "very_severe_cyclonic_storm"), (220, "extremely_severe_cyclonic_storm"),
]


def heat_index_c(temp_c, humidity_pct):
    """NOAA/Rothfusz regression heat index (apparent temperature from heat + humidity),
    including NOAA's two published edge-case corrections (low-humidity subtraction,
    high-humidity addition) that the base regression alone under/overstates.

    Only meaningful once it's already hot — below 26.7C (80F) the regression is
    inaccurate and heat stress isn't the binding constraint, so we just return the
    ambient temperature unchanged.
    """
    if temp_c is None or humidity_pct is None:
        return None
    if temp_c < 26.7:
        return round(temp_c, 1)

    t = temp_c * 9.0 / 5.0 + 32.0
    r = humidity_pct
    hi_f = (
        -42.379
        + 2.04901523 * t
        + 10.14333127 * r
        - 0.22475541 * t * r
        - 0.00683783 * t * t
        - 0.05481717 * r * r
        + 0.00122874 * t * t * r
        + 0.00085282 * t * r * r
        - 0.00000199 * t * t * r * r
    )
    # NOAA's published adjustments for the regression's known weak spots.
    if r < 13 and 80 <= t <= 112:
        hi_f -= ((13 - r) / 4.0) * math.sqrt((17 - abs(t - 95.0)) / 17.0)
    elif r > 85 and 80 <= t <= 87:
        hi_f += ((r - 85) / 10.0) * ((87 - t) / 5.0)

    return round((hi_f - 32.0) * 5.0 / 9.0, 1)


def heat_index_category(hi_c):
    """NOAA heat index risk bands (thresholds are the standard 80/90/103/125F marks in C)."""
    if hi_c is None:
        return None
    if hi_c < 27.0:
        return "normal"
    if hi_c < 32.2:
        return "caution"
    if hi_c < 39.4:
        return "extreme_caution"
    if hi_c < 51.7:
        return "danger"
    return "extreme_danger"


def dew_point_c(temp_c, humidity_pct):
    """Magnus-Tetens approximation of dew point."""
    if temp_c is None or humidity_pct is None or humidity_pct <= 0:
        return None
    a, b = 17.625, 243.04
    gamma = math.log(humidity_pct / 100.0) + (a * temp_c) / (b + temp_c)
    return round((b * gamma) / (a - gamma), 1)


def fog_risk(temp_c, humidity_pct, wind_speed_kmh):
    """Fog/mist likelihood from dew-point spread + wind (fog needs still, saturated air)."""
    dp = dew_point_c(temp_c, humidity_pct)
    if dp is None or temp_c is None:
        return {"risk": "unknown", "dew_point_c": None, "dew_point_spread_c": None}

    spread = round(temp_c - dp, 1)
    wind = wind_speed_kmh if wind_speed_kmh is not None else 0.0
    if spread <= 2.5 and wind < 8:
        risk = "high"
    elif spread <= 4.0 and wind < 15:
        risk = "moderate"
    else:
        risk = "low"
    return {"risk": risk, "dew_point_c": dp, "dew_point_spread_c": spread}


def beaufort_scale(wind_speed_kmh):
    """WMO-adopted Beaufort wind force (0-12) from sustained wind speed."""
    if wind_speed_kmh is None:
        return None
    for force, (upper_bound, name) in enumerate(_BEAUFORT_BANDS):
        if wind_speed_kmh < upper_bound:
            return {"force": force, "name": name}
    return {"force": 12, "name": "hurricane"}


def imd_cyclone_category(wind_speed_kmh):
    """IMD's official low-pressure-system classification by sustained wind speed.

    Only meaningful once winds reach depression strength (per IMD's own scale
    floor, ~31 km/h) — below that it isn't a synoptic system, so this returns
    None rather than mislabeling ordinary breezy weather as a "low pressure area."
    """
    if wind_speed_kmh is None or wind_speed_kmh < _IMD_BANDS[0][0]:
        return None
    for upper_bound, name in _IMD_BANDS:
        if wind_speed_kmh < upper_bound:
            return name
    return "super_cyclonic_storm"


def small_craft_risk(wave_height_m, wind_speed_kmh, wind_gusts_kmh=None):
    """Sea-state category aligned to official NWS coastal marine warning tiers
    (Small Craft Advisory / Gale Warning / Storm Warning / Hurricane Force Wind
    Warning), combining wind and wave height — the worse of the two wins.
    """
    if wave_height_m is None and wind_speed_kmh is None:
        return {"level": "unknown", "wind_kmh_used": None, "wave_height_m_used": None}

    wind = max(wind_speed_kmh or 0.0, wind_gusts_kmh or 0.0)
    wave = wave_height_m or 0.0

    def _wind_level(w):
        if w < _SCA_WIND_KMH:
            return 0
        if w < _GALE_WIND_KMH:
            return 1
        if w < _STORM_WIND_KMH:
            return 2
        if w < _HURRICANE_WIND_KMH:
            return 3
        return 4

    def _wave_level(h):
        if h < _SCA_WAVE_M:
            return 0
        if h < _GALE_WAVE_M:
            return 1
        if h < _STORM_WAVE_M:
            return 2
        return 3

    level = max(_wind_level(wind), _wave_level(wave))
    labels = ["none", "small_craft_advisory", "gale_warning", "storm_warning", "hurricane_force_warning"]
    return {"level": labels[level], "wind_kmh_used": round(wind, 1), "wave_height_m_used": round(wave, 2)}


def rapid_pressure_fall(pressure_change_24h_hpa, lat):
    """Latitude-normalized rapid-pressure-fall signal, using the Bergeron/
    Sanders-Gyakum (1980) explosive-cyclogenesis criterion: a 24hPa/24h fall at
    60N, scaled by sin(lat)/sin(60) to the storm's actual latitude.

    Honest scope note: that criterion describes baroclinic (extratropical)
    cyclogenesis. At these tropical/subtropical coastal latitudes the dynamics
    are different (warm-core, not baroclinic), so this is surfaced as a generic
    "rapid pressure fall" signal worth attention — not a claim that formal
    bombogenesis is occurring.
    """
    if pressure_change_24h_hpa is None or lat is None:
        return None
    lat_rad = math.radians(min(abs(lat), 89.9))
    sin_60 = math.sin(math.radians(60))
    threshold = max(24.0 * (math.sin(lat_rad) / sin_60), 3.0)  # floor so equatorial locations aren't flagged on noise
    is_rapid = pressure_change_24h_hpa <= -threshold
    return {
        "change_24h_hpa": round(pressure_change_24h_hpa, 2),
        "latitude_normalized_threshold_hpa": round(threshold, 2),
        "rapid_fall": is_rapid,
    }


def storm_potential_score(pressure_hpa, wind_gusts_kmh, cloud_cover_pct, pressure_change_3h_hpa=None):
    """0-1 composite storm-potential score from low pressure + gusts + cloud cover
    (+ a falling-pressure trend when available, the single strongest storm precursor).
    """
    if pressure_hpa is None:
        return None

    score = 0.0
    if pressure_hpa < 1005:
        score += 0.3
    if pressure_hpa < 995:
        score += 0.3
    if wind_gusts_kmh is not None and wind_gusts_kmh > 40:
        score += 0.2
    if wind_gusts_kmh is not None and wind_gusts_kmh > 60:
        score += 0.2
    if cloud_cover_pct is not None and cloud_cover_pct > 80:
        score += 0.1
    if pressure_change_3h_hpa is not None and pressure_change_3h_hpa <= -3:
        score += 0.3

    return round(min(score, 1.0), 2)


def storm_potential_level(score):
    if score is None:
        return None
    if score < 0.3:
        return "low"
    if score < 0.6:
        return "moderate"
    if score < 0.85:
        return "high"
    return "severe"


def air_stagnation_index(wind_speed_kmh, pm25, precipitation_mm=None):
    """Flags conditions where pollutants accumulate rather than disperse: still air,
    no washout rain, and an already-elevated PM2.5 reading.
    """
    if wind_speed_kmh is None:
        return None

    stagnant_wind = wind_speed_kmh < 10
    no_rain = (precipitation_mm or 0) < 0.5
    pollutant_high = (pm25 or 0) > 35.4

    if stagnant_wind and no_rain and pollutant_high:
        return "high"
    if stagnant_wind and no_rain:
        return "moderate"
    return "low"


def coastal_flood_risk(elevation_m, wave_height_m, wind_speed_kmh, pressure_hpa):
    """Composite storm-surge/coastal-flood exposure: low elevation is the dominant
    term (it determines whether any surge reaches habitation), scaled up by sea
    state and by the inverse barometer effect — the well-established oceanographic
    relationship where sea level rises ~1cm for every 1hPa the local air pressure
    drops below the standard 1013.25hPa reference.
    """
    if elevation_m is None:
        return None

    score = 0.0
    if elevation_m < 5:
        score += 0.4
    elif elevation_m < 10:
        score += 0.15

    if wave_height_m is not None and wave_height_m > 2.0:
        score += 0.3
    if wind_speed_kmh is not None and wind_speed_kmh > 40:
        score += 0.2

    ib_surge_cm = None
    if pressure_hpa is not None:
        ib_surge_cm = round(max(0.0, 1013.25 - pressure_hpa), 1)
        if ib_surge_cm >= 10:
            score += 0.2
        elif ib_surge_cm >= 5:
            score += 0.1

    score = round(min(score, 1.0), 2)
    if score < 0.3:
        level = "low"
    elif score < 0.6:
        level = "moderate"
    elif score < 0.85:
        level = "high"
    else:
        level = "severe"
    return {"score": score, "level": level, "inverse_barometer_surge_cm": ib_surge_cm}


def tsunami_caution(max_magnitude, elevation_m, depth_km=None):
    """Advisory flag when a significant nearby quake (M>=6.5 within 500km, from the
    seismic_risk domain) coincides with a low-lying coastline.

    When depth data is available, requires a shallow-focus event (USGS-defined
    shallow: <70km) — deep-focus quakes rarely generate significant surface
    tsunamis at the same magnitude. Falls back to magnitude+elevation only when
    depth is unknown, so missing data doesn't silently lose the original signal.
    """
    if max_magnitude is None or elevation_m is None:
        return {"advisory": False, "reason": None}
    if depth_km is not None and depth_km >= 70:
        return {"advisory": False, "reason": None}
    if max_magnitude >= 6.5 and elevation_m < 10:
        depth_note = f", shallow focus at {depth_km}km depth" if depth_km is not None else ""
        return {
            "advisory": True,
            "reason": f"M{max_magnitude} seismic event within 500km{depth_note} and low-lying coast ({elevation_m}m elevation)",
        }
    return {"advisory": False, "reason": None}


def compute_derived_insights(data, lat=None, pressure_change_24h_hpa=None, pressure_change_3h_hpa=None):
    """Assemble every composite signal from one snapshot's `data` dict.

    Each upstream domain may be missing or in an "error" status — every lookup below
    uses .get() with an empty-dict default so a partial snapshot never raises here.

    `lat` and `pressure_change_24h_hpa` are optional — when given (app.py supplies
    them once Phase 2A history exists for the location), they enable the
    latitude-normalized rapid-pressure-fall signal. `pressure_change_3h_hpa` feeds
    storm_potential_score's short-term trend term the same way. All optional;
    omitted, everything else still computes normally.
    """
    data = data or {}
    weather = data.get("weather") or {}
    marine = data.get("marine") or {}
    aq = data.get("air_quality") or {}
    terrain = data.get("terrain") or {}
    seismic = data.get("seismic_risk") or {}

    temp = weather.get("temperature_c")
    humidity = weather.get("humidity_pct")
    wind = weather.get("wind_speed_kmh")
    gusts = weather.get("wind_gusts_kmh")
    pressure = weather.get("pressure_hpa")
    cloud = weather.get("cloud_cover_pct")
    precip = weather.get("precipitation_mm")

    hi = heat_index_c(temp, humidity)
    fog = fog_risk(temp, humidity, wind)
    craft = small_craft_risk(marine.get("wave_height_m"), wind, gusts)
    storm_score = storm_potential_score(pressure, gusts, cloud, pressure_change_3h_hpa)
    stagnation = air_stagnation_index(wind, aq.get("pm25"), precip)
    flood = coastal_flood_risk(terrain.get("elevation_m"), marine.get("wave_height_m"), wind, pressure)
    tsunami = tsunami_caution(seismic.get("max_magnitude"), terrain.get("elevation_m"), seismic.get("max_magnitude_depth_km"))

    return {
        "heat_index_c": hi,
        "heat_index_category": heat_index_category(hi),
        "dew_point_c": fog.get("dew_point_c"),
        "fog_risk": fog.get("risk"),
        "beaufort_scale": beaufort_scale(wind),
        "imd_cyclone_category": imd_cyclone_category(wind),
        "small_craft_risk_level": craft.get("level"),
        "small_craft_risk_detail": craft,
        "storm_potential_score": storm_score,
        "storm_potential_level": storm_potential_level(storm_score),
        "rapid_pressure_fall": rapid_pressure_fall(pressure_change_24h_hpa, lat),
        "air_stagnation_index": stagnation,
        "coastal_flood_risk": flood,
        "tsunami_advisory": tsunami,
        "methodology_note": (
            "Composite physical signals from published, cited sources: NOAA heat index regression, "
            "Magnus-Tetens dew point, WMO Beaufort scale, IMD cyclone classification, NWS coastal "
            "marine warning wind/sea criteria, the inverse barometer effect, and the Bergeron/"
            "Sanders-Gyakum latitude-normalized rapid-pressure-fall criterion — no machine learning "
            "or forecasting is involved. See docs/PHASE2_WALKTHROUGH.md for citations and honest "
            "scope notes on where these standards do and don't strictly apply."
        ),
    }
