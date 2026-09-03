# Project: Unified Environmental Intelligence Endpoint
### Architecture & Engineering Specification — Multi-Domain Pilot

---

## 1. What We're Building

A single, high-performance API endpoint that:

1. Concurrently pulls live data from **7 free public environmental sources** for **any target coordinate**.
2. Normalizes over 50 physical, atmospheric, and hydrodynamic variables into one consistent schema (canonical SI units, ISO 8601 UTC timestamps, coordinate validation).
3. Serves it back as **one clean, validated JSON snapshot** with sub-millisecond warm cache reads—eliminating the need for frontier AI models or maritime applications to juggle multiple disparate APIs, authentications, rate limits, and failure modes.

**In one sentence:** We are building the real-time physical data layer that any AI model (Nemotron, Llama 3.2, GPT-4o, Claude) or coastal application can call once to get trustworthy, structured, multi-domain environmental context, eliminating environmental hallucinations.

This is *not* a chatbot. It is production infrastructure that agents, maritime operations, and coastal decision tools sit on top of.

---

## 2. Why This Matters (The Value Proposition)

Right now, if you ask any frontier model *"What are the ocean and weather conditions along the Chennai coast right now and is it safe to launch small artisanal boats?"*, it either:
- **Hallucinates**: Guesses seasonal stereotypes (e.g. predicting heavy monsoon rain in dry September), or
- **Requires complex multi-tool orchestration**: Must be wired to 7+ separate APIs, each with different schemas, missing coordinate mappings, and unpredictable latency.

**Our endpoint removes that burden.** One call $\rightarrow$ one normalized answer, with source provenance, freshness indicators, and physical boundary checks attached. 

### Operational Use Cases:
- **Artisanal Fisheries & Mariner Safety**: Correlates wind gusts, local wind chop, ocean swell period, and nautical twilight schedules to calculate safe departure and return windows.
- **Heat Stress & Worker Safety**: Correlates dry bulb temperature with apparent heat index, relative humidity, and UV index.
- **Coastal Surge & Flood Risk**: Evaluates ground elevation above sea level ($<5\text{m}$ low-lying thresholds) alongside precipitation and recent offshore seismic events.

---

## 3. Target Pilot Location

**Default: Chennai Coastline, Tamil Nadu (13.08°N, 80.27°E)**

Chosen because:
- **Coastal Interface**: Direct interplay of marine hydrodynamics, atmospheric weather, and coastal air chemistry.
- **High Sensor Density**: Strong coverage across ground-level air quality stations and regional maritime models.
- **Economic & Operational Significance**: Major commercial port, extensive artisanal fishing communities, and seasonal monsoonal vulnerability.

*(Fully parameterized by `lat` and `lon`—functions globally across all marine and terrestrial coordinates).*

---

## 4. The 7 Integrated Free APIs

All sources are **100% free**, require no credit card or paid tier, and provide stable public endpoints:

| # | Domain | Source | What It Ingests | Key / Tier |
|---|:---|:---|:---|:---|
| 1 | **Weather & Atmosphere** | **Open-Meteo Forecast** | `temperature_c`, `apparent_temperature_c`, `wind_speed_kmh`, `wind_gusts_kmh`, `wind_direction_deg`, `humidity_pct`, `pressure_hpa`, `surface_pressure_hpa`, `precipitation_mm`, `cloud_cover_pct`, `uv_index`, `visibility_m`, `weather_code` (WMO), `weather_description`, `is_day` | 100% Free, **No Key** |
| 2 | **Ocean Hydrodynamics** | **Open-Meteo Marine** | `sea_surface_temp_c`, `wave_height_m`, `wave_period_s`, `wave_direction_deg`, `wind_wave_height_m`, `wind_wave_period_s`, `wind_wave_direction_deg`, `swell_wave_height_m`, `swell_wave_period_s`, `swell_wave_direction_deg`, `ocean_current_velocity_kmh`, `ocean_current_direction_deg` | 100% Free, **No Key** |
| 3 | **Air Quality & Chemistry** | **OpenAQ** + **Open-Meteo Fallback** | `pm25`, `pm10`, `o3`, `no2`, `so2`, `co`, `aqi_category` (EPA), `us_aqi`, `european_aqi`, `dust_ug_m3`, `aerosol_optical_depth`, `tier` (`ground_sensor` or `atmospheric_model`) | Free Tier (`OpenAQ`) / Free, **No Key** (`Open-Meteo`) |
| 4 | **Solar & Marine Lighting** | **Sunrise-Sunset.org** | `sunrise`, `sunset`, `solar_noon`, `day_length_hours`, `civil_twilight_begin`, `civil_twilight_end`, `nautical_twilight_begin` (mariner navigation visibility), `nautical_twilight_end`, `astronomical_twilight_begin`, `astronomical_twilight_end` | 100% Free, **No Key** |
| 5 | **Terrain & Elevation** | **Open-Meteo Elevation** | `elevation_m` (meters above sea level), `coastal_risk_category` (`low-lying (<5m)` storm surge vulnerability vs `elevated`) | 100% Free, **No Key** |
| 6 | **Climate Baseline** | **NASA POWER** | `solar_radiation_kwh_m2`, `avg_temperature_c`, `avg_wind_speed_ms`, `observed_at` | 100% Free, **No Key** |
| 7 | **Seismic & Tsunami Risk** | **USGS Earthquakes** | `recent_events_7d_count` (past 7 days within 500km), `max_magnitude`, `hazard_level` (`nominal` or `elevated`), `search_radius_km` | 100% Free, **No Key** |

---

## 5. Unified Response Schema

Every upstream source is normalized into this consistent schema:

```json
{
  "location": {
    "name": "Chennai Coast",
    "lat": 13.08,
    "lon": 80.27
  },
  "generated_at": "2026-09-03T11:30:29Z",
  "data": {
    "weather": {
      "temperature_c": 31.5,
      "apparent_temperature_c": 36.0,
      "wind_speed_kmh": 10.4,
      "wind_gusts_kmh": 32.8,
      "wind_direction_deg": 172,
      "humidity_pct": 64,
      "pressure_hpa": 1005.7,
      "surface_pressure_hpa": 1004.6,
      "precipitation_mm": 0.1,
      "cloud_cover_pct": 98,
      "uv_index": 0.25,
      "visibility_m": 6620.0,
      "weather_code": 51,
      "weather_description": "Light drizzle",
      "is_day": true,
      "source": "open-meteo",
      "observed_at": "2026-09-03T11:30:00Z",
      "status": "ok",
      "latency_ms": 1111.63
    },
    "marine": {
      "sea_surface_temp_c": 30.6,
      "wave_height_m": 0.78,
      "wave_period_s": 8.75,
      "wave_direction_deg": 145,
      "wind_wave_height_m": 0.24,
      "wind_wave_period_s": 1.95,
      "wind_wave_direction_deg": 159,
      "swell_wave_height_m": 0.60,
      "swell_wave_period_s": 6.55,
      "swell_wave_direction_deg": 145,
      "ocean_current_velocity_kmh": 1.1,
      "ocean_current_direction_deg": 18,
      "note": null,
      "source": "open-meteo-marine",
      "observed_at": "2026-09-03T11:30:00Z",
      "status": "ok",
      "latency_ms": 1389.96
    },
    "air_quality": {
      "station_name": "Royapuram, Chennai - TNPCB",
      "pm25": 23.83,
      "pm10": 51.8,
      "o3": 28.06,
      "no2": 11.4,
      "so2": 4.56,
      "co": 1.26,
      "aqi_category": "moderate",
      "source": "openaq",
      "observed_at": "2026-09-02T10:30:00Z",
      "status": "ok",
      "latency_ms": 2642.33
    },
    "sun_and_lighting": {
      "sunrise": "2026-09-03T00:26:46+00:00",
      "sunset": "2026-09-03T12:49:55+00:00",
      "solar_noon": "2026-09-03T06:38:21+00:00",
      "day_length_hours": 12.39,
      "civil_twilight_begin": "2026-09-03T00:06:24+00:00",
      "civil_twilight_end": "2026-09-03T13:10:17+00:00",
      "nautical_twilight_begin": "2026-09-02T23:41:23+00:00",
      "nautical_twilight_end": "2026-09-03T13:35:18+00:00",
      "source": "sunrise-sunset.org",
      "observed_at": "2026-09-03T06:38:21+00:00",
      "status": "ok",
      "latency_ms": 950.37
    },
    "terrain": {
      "elevation_m": 10.0,
      "coastal_risk_category": "elevated",
      "source": "open-meteo-elevation",
      "status": "ok",
      "latency_ms": 1076.67
    },
    "climate_baseline": {
      "solar_radiation_kwh_m2": 6.01,
      "avg_temperature_c": 30.82,
      "avg_wind_speed_ms": 3.74,
      "source": "nasa-power",
      "observed_at": "2026-08-28T00:00:00Z",
      "status": "ok",
      "latency_ms": 1489.21
    },
    "seismic_risk": {
      "recent_events_7d_count": 0,
      "max_magnitude": null,
      "hazard_level": "nominal",
      "search_radius_km": 500,
      "source": "usgs-earthquake",
      "status": "ok",
      "latency_ms": 1254.90
    }
  },
  "meta": {
    "confidence": "high — all sources responded successfully",
    "failed_sources": [],
    "total_latency_ms": 2652.44,
    "source_latencies_ms": {
      "open-meteo": 1111.63,
      "open-meteo-marine": 1389.96,
      "openaq": 2642.33,
      "sunrise-sunset.org": 950.37,
      "open-meteo-elevation": 1076.67,
      "nasa-power": 1489.21,
      "usgs-earthquake": 1254.90
    },
    "cache_hit": false,
    "freshness_warning": "climate_baseline data is >24h old"
  }
}
```

---

## 6. Architecture & Execution Engine

```
[ 7 Upstream Free APIs ]
  ├── Open-Meteo Weather
  ├── Open-Meteo Marine
  ├── OpenAQ (with Open-Meteo AQ CAMS fallback)
  ├── Sunrise-Sunset.org
  ├── Open-Meteo Elevation
  ├── NASA POWER
  └── USGS Earthquake Hazards
         ↓
[ Concurrency Engine ]  ThreadPoolExecutor(max_workers=7)
         ↓
[ Quality & Sanity Sentinel ]  Physical boundary validation (temperature, humidity, waves, AQI)
         ↓
[ Multi-Tier Cache Layer ]
  ├── Station Metadata Cache (24h TTL)
  └── Response Snapshot Cache (5m TTL → 0.5ms response)
         ↓
[ FastAPI Production Service ]  GET /environment, GET /health, GET /docs
         ↓
[ Consumers ]  Frontier LLMs (Nemotron, Llama 3.2), Maritime Operators, Coastal Risk Systems
```

---

## 7. Quality Sentinel & Physical Boundary Verification

To prevent upstream corruptions or unphysical anomalies from contaminating model prompts, the built-in `validate_environmental_data()` sentinel verifies:
1. `temperature_c`: Validated between $-50.0^\circ\text{C}$ and $60.0^\circ\text{C}$.
2. `apparent_temperature_c`: Validated between $-60.0^\circ\text{C}$ and $75.0^\circ\text{C}$.
3. `humidity_pct`: Physical bounds between $0\%$ and $100\%$.
4. `pressure_hpa`: Standard barometric bounds between $850\text{ hPa}$ and $1090\text{ hPa}$.
5. `wind_speed_kmh` & `wind_gusts_kmh`: Non-negative constraint ($w \ge 0$).
6. `precipitation_mm`: Non-negative constraint ($pr \ge 0$).
7. `wave_height_m`, `wind_wave_height_m`, `swell_wave_height_m`: Non-negative ($wh \ge 0$).
8. `sea_surface_temp_c`: Oceanic bounds between $-2.5^\circ\text{C}$ and $45.0^\circ\text{C}$.
9. `air_quality` pollutants: Non-negative ($pm2.5, pm10, o3, no2, so2, co \ge 0$).
10. `uv_index`: Validated between $0.0$ and $25.0$.

---

## 8. Robustness & Failure Isolation (100% Pass)

The service enforces strict **isolated failure degradation**. If one or more upstream APIs fail, the remaining sources continue uninterrupted and the response status degrades gracefully to `partial`:

- [x] **Kill 'weather'**: Returns partial snapshot, `failed_sources: ["open-meteo"]`, remaining 6 sources OK.
- [x] **Kill 'marine'**: Returns partial snapshot, `failed_sources: ["open-meteo-marine"]`, remaining 6 sources OK.
- [x] **Kill 'air_quality'**: Returns partial snapshot, `failed_sources: ["openaq"]`, remaining 6 sources OK.
- [x] **Kill 'sun_and_lighting'**: Returns partial snapshot, `failed_sources: ["sunrise-sunset.org"]`, remaining 6 sources OK.
- [x] **Kill 'terrain'**: Returns partial snapshot, `failed_sources: ["open-meteo-elevation"]`, remaining 6 sources OK.
- [x] **Kill 'climate_baseline'**: Returns partial snapshot, `failed_sources: ["nasa-power"]`, remaining 6 sources OK.
- [x] **Kill 'seismic_risk'**: Returns partial snapshot, `failed_sources: ["usgs-earthquake"]`, remaining 6 sources OK.
- [x] **Aggressive Timeout (0.001s)**: Gracefully flags all failed sources with `confidence: low — all sources failed` without crashing.

---

## 9. Explicitly Out of Scope (For Now)

To prevent unconstrained architectural sprawl:
- No persistent vector store / RAG layers (stateless live/cached ingestion).
- No frontend conversational chatbot UI.
- No push alerting / SMS webhooks.
- No additional data sources beyond the 7 ratified multi-domain providers.

---

## 10. Delivery Status & Verification

- [x] **Production Live URL**: Deployed on Render at `https://confluence-si41.onrender.com`.
- [x] **Remote Test Suite**: 4/4 passing against production URL (`tests/test_live_remote.py`).
- [x] **Automated Pytest Suite**: 28/28 unit and mocked integration tests passing (`tests/`).
- [x] **Empirical LLM Grounding Proof**: Demonstrated across 3 weather regimes (Heat Spike, Monsoon Squall, Winter Stagnation) and 2 model families (`nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` and `meta/llama-3.2-11b-vision-instruct`).
- [x] **Free-Tier Keep-Alive**: GitHub Actions cron workflow (`.github/workflows/keep_alive.yml`) configured to ping `/health` every 12 minutes.
