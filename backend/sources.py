"""
Confluence Upstream Data Sources Registry
Centralizes the configurations, base endpoints, documentation links, and
hyperparameter catalogs for all 10 independent scientific data providers.
"""

from typing import List, Dict, Any

# Canonical upstream API endpoints
OPEN_METEO_WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
OPENAQ_LOCATIONS_URL = "https://api.openaq.org/v3/locations"
OPEN_METEO_AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
SUNRISE_SUNSET_URL = "https://api.sunrise-sunset.org/json"
OPEN_METEO_ELEVATION_URL = "https://api.open-meteo.com/v1/elevation"
USGS_SEISMIC_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
NASA_POWER_CLIMATE_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
OPEN_METEO_FLOOD_URL = "https://flood-api.open-meteo.com/v1/flood"
GDACS_CYCLONE_URL = "https://www.gdacs.org/xml/rss.xml"
NASA_FIRMS_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"

# Comprehensive structured registry for all 10 upstream providers
DATA_SOURCES_REGISTRY: List[Dict[str, Any]] = [
    {
        "id": "weather",
        "name": "Open-Meteo Weather",
        "category": "Atmospheric & Meteorological",
        "base_url": OPEN_METEO_WEATHER_URL,
        "docs_url": "https://open-meteo.com/en/docs",
        "hyperparameters_count": 15,
        "description": "High-resolution atmospheric forecasting (temp, gusts, surface pressure, humidity, UV, cloud cover)",
    },
    {
        "id": "marine",
        "name": "Open-Meteo Marine",
        "category": "Ocean Hydrodynamics",
        "base_url": OPEN_METEO_MARINE_URL,
        "docs_url": "https://open-meteo.com/en/docs/marine-weather-api",
        "hyperparameters_count": 13,
        "description": "Global hydrodynamic wave models (significant wave height, swell direction/period, surface ocean currents)",
    },
    {
        "id": "air_quality",
        "name": "OpenAQ Ground Stations",
        "category": "Ground Air Quality & Emissions",
        "base_url": OPENAQ_LOCATIONS_URL,
        "fallback_url": OPEN_METEO_AIR_QUALITY_URL,
        "docs_url": "https://docs.openaq.org/",
        "hyperparameters_count": 9,
        "description": "Real-time physical ground sensor network (PM2.5, PM10, O3, NO2, SO2, CO) with CAMS model fallback",
    },
    {
        "id": "sun_and_lighting",
        "name": "Sunrise-Sunset.org",
        "category": "Marine Nautical Ephemeris",
        "base_url": SUNRISE_SUNSET_URL,
        "docs_url": "https://sunrise-sunset.org/api",
        "hyperparameters_count": 10,
        "description": "Astronomical and nautical twilight calculations, solar noon, daylight length",
    },
    {
        "id": "terrain",
        "name": "Open-Meteo Elevation",
        "category": "Coastal Topography & Inundation",
        "base_url": OPEN_METEO_ELEVATION_URL,
        "docs_url": "https://open-meteo.com/en/docs/elevation-api",
        "hyperparameters_count": 2,
        "description": "High-resolution digital elevation models for coastal surge vulnerability analysis",
    },
    {
        "id": "climate_baseline",
        "name": "NASA POWER",
        "category": "Solar Radiation & Climatology",
        "base_url": NASA_POWER_CLIMATE_URL,
        "docs_url": "https://power.larc.nasa.gov/docs/",
        "hyperparameters_count": 3,
        "description": "Long-term climatological normal baselines (solar insolation, mean temperature, wind)",
    },
    {
        "id": "seismic_risk",
        "name": "USGS Earthquake Hazards",
        "category": "Geophysics & Tsunami",
        "base_url": USGS_SEISMIC_URL,
        "docs_url": "https://earthquake.usgs.gov/fdsnws/event/1/",
        "hyperparameters_count": 5,
        "description": "Global seismic feeds tracking 7-day offshore earthquakes and shallow focal depth tsunami risks",
    },
    {
        "id": "river_flood",
        "name": "Copernicus GloFAS (Open-Meteo Flood)",
        "category": "Hydrology & River Basin Discharge",
        "base_url": OPEN_METEO_FLOOD_URL,
        "docs_url": "https://open-meteo.com/en/docs/flood-api",
        "hyperparameters_count": 4,
        "description": "Global Flood Awareness System river basin volumetric discharge (m3/s) for compound estuarine flooding",
    },
    {
        "id": "cyclone_tracking",
        "name": "GDACS Disaster Alerts",
        "category": "Tropical Cyclones & Disasters",
        "base_url": GDACS_CYCLONE_URL,
        "docs_url": "https://www.gdacs.org/",
        "hyperparameters_count": 7,
        "description": "UN / European Commission JRC real-time tropical cyclone tracking, storm tracks, and alert levels",
    },
    {
        "id": "thermal_hotspots",
        "name": "NASA FIRMS",
        "category": "Satellite Active Fire & Smoke Causality",
        "base_url": NASA_FIRMS_URL,
        "docs_url": "https://firms.modaps.eosdis.nasa.gov/",
        "hyperparameters_count": 7,
        "description": "VIIRS / MODIS satellite thermal anomaly detection within 300km for particulate causality attribution",
    },
]


def get_data_sources_registry() -> List[Dict[str, Any]]:
    """Return the structured configurations of all 10 upstream providers."""
    return DATA_SOURCES_REGISTRY


def get_source_summary_strings() -> List[str]:
    """Return formatted summary strings for root API endpoint metadata."""
    return [
        f"{src['name']} ({src['hyperparameters_count']} hyperparameters)"
        for src in DATA_SOURCES_REGISTRY
    ]


def get_source_urls() -> Dict[str, str]:
    """Return mapping of source identifiers to their canonical upstream URLs."""
    return {src["id"]: src["base_url"] for src in DATA_SOURCES_REGISTRY}
