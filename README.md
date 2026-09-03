# 🌊 Confluence — Unified Environmental Intelligence API

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB.svg?logo=python&logoColor=white)](https://python.org)
[![Tests](https://img.shields.io/badge/Tests-32%20Total%20(28%20Offline%20%2B%204%20Remote)-brightgreen.svg)](tests/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Render](https://img.shields.io/badge/Deploy-Render-46E3B7.svg?logo=render&logoColor=white)](https://confluence-si41.onrender.com)

A high-performance, normalized API that concurrently aggregates **50+ physical, marine, and atmospheric hyperparameters** across **7 free public APIs** into a single validated JSON snapshot.

Engineered specifically to **ground frontier AI models** (Nemotron, Llama 3.2, GPT-4o, Claude) and maritime decision systems in empirical, real-time physical truth—eliminating weather hallucinations and enabling high-stakes operational safety advisories.

---

## 🌐 Live Production Service

The API is deployed on Render and serving live data:

- **Live Service Base URL**: [`https://confluence-si41.onrender.com`](https://confluence-si41.onrender.com)
- **Interactive OpenAPI / Swagger Docs**: [`https://confluence-si41.onrender.com/docs`](https://confluence-si41.onrender.com/docs)
- **Health Probe**: [`https://confluence-si41.onrender.com/health`](https://confluence-si41.onrender.com/health)
- **Sample Production Query**: [`/environment?lat=13.08&lon=80.27&name=Chennai%20Coast`](https://confluence-si41.onrender.com/environment?lat=13.08&lon=80.27&name=Chennai%20Coast)

---

## 🚀 Key Highlights

- **50+ Hyperparameters Across 7 Free APIs**: Ingests atmospheric weather, sea state hydrodynamics, dual-tier air quality, solar/nautical twilight ephemeris, topography/elevation, climate baselines, and recent seismic events.
- **Concurrent Execution Pipeline**: Dispatches all upstream requests simultaneously via `concurrent.futures.ThreadPoolExecutor(max_workers=7)`. Total latency is governed by the single slowest source (~2.6s) rather than sequential accumulation (~10s)—a **73% speedup**.
- **Two-Tier Smart Caching**:
  - **Station Metadata Cache (24h TTL)**: Eliminates spatial discovery round-trips for ground stations.
  - **Response Snapshot Cache (5m TTL)**: Returns warm repeated queries in **0.5 ms** with `bypass_cache=true` override.
- **Render Keep-Alive & Pre-Warming**:
  - Automatically pre-warms cache on startup.
  - Includes a GitHub Actions cron ping (`.github/workflows/keep_alive.yml`) to prevent free-tier 15-minute idle spin-down.
- **Data Quality Sentinel**: Automated boundary validator that flags non-physical values (e.g. negative wave heights, humidity >100%, out-of-bound pressure) before returning data.
- **Production Hardened**: SlowAPI rate limiting (30 req/min per IP), global exception interceptor (no stack trace leaks), request latency logging, and 100% clean secrets hygiene.

---

## 📊 The 7 Integrated Free APIs & 50+ Parameters

| Domain | Integrated Service | Key / Tier | Hyperparameters Ingested |
| :--- | :--- | :--- | :--- |
| **1. Weather & Atmosphere** | **Open-Meteo Forecast** | 100% Free, **No Key** | `temperature_c`, `apparent_temperature_c` (feels-like), `wind_speed_kmh`, `wind_gusts_kmh` (squall gusts), `wind_direction_deg`, `humidity_pct`, `pressure_hpa`, `surface_pressure_hpa`, `precipitation_mm`, `cloud_cover_pct`, `uv_index`, `visibility_m`, `weather_code` (WMO), `weather_description`, `is_day` |
| **2. Ocean Hydrodynamics** | **Open-Meteo Marine** | 100% Free, **No Key** | `sea_surface_temp_c`, `wave_height_m`, `wave_period_s`, `wave_direction_deg`, `wind_wave_height_m`, `wind_wave_period_s`, `wind_wave_direction_deg`, `swell_wave_height_m`, `swell_wave_period_s`, `swell_wave_direction_deg`, `ocean_current_velocity_kmh`, `ocean_current_direction_deg`, `note` (landlocked detection) |
| **3. Air Quality & Chemistry** | **OpenAQ** + **Open-Meteo Fallback** | Free Tier (`OpenAQ`) / Free, **No Key** (`Open-Meteo`) | `pm25`, `pm10`, `o3`, `no2`, `so2`, `co`, `aqi_category` (EPA standard), `us_aqi`, `european_aqi`, `dust_ug_m3`, `aerosol_optical_depth`, `tier` (`ground_sensor` or `atmospheric_model`) |
| **4. Astronomical & Marine Lighting** | **Sunrise-Sunset.org** | 100% Free, **No Key** | `sunrise`, `sunset`, `solar_noon`, `day_length_hours`, `civil_twilight_begin`, `civil_twilight_end`, `nautical_twilight_begin` (mariner departure threshold), `nautical_twilight_end`, `astronomical_twilight_begin`, `astronomical_twilight_end` |
| **5. Topography & Elevation** | **Open-Meteo Elevation** | 100% Free, **No Key** | `elevation_m` (meters above sea level), `coastal_risk_category` (`low-lying (<5m)` storm surge vulnerability vs `elevated`) |
| **6. Climate Baseline** | **NASA POWER** | 100% Free, **No Key** | `solar_radiation_kwh_m2`, `avg_temperature_c`, `avg_wind_speed_ms`, `observed_at` |
| **7. Seismic & Tsunami Risk** | **USGS Earthquakes** | 100% Free, **No Key** | `recent_events_7d_count` (past 7d within 500km), `max_magnitude`, `hazard_level` (`nominal` or `elevated`), `search_radius_km` |

---

## 🔬 Scientific Grounding Proof: Why This Matters

When frontier LLMs are asked operational coastal questions without this endpoint, they either hallucinate seasonal stereotypes or admit total blindness. Grounding them in this unified snapshot transforms their capability:

| Environmental Scenario | Raw Observations | Ungrounded Frontier LLM Response | Grounded Model with Confluence Endpoint |
| :--- | :--- | :--- | :--- |
| **Scenario 1: Dry Heat Spike** | 35.4°C, 47% RH, 0.0mm rain, 0.76m swell | *Guesses heavy monsoon downpours and high waves based on static regional priors.* | **Accurate Operational Advice**: Safe for 2–3 hr artisanal fishing; mandates hourly hydration breaks for outdoor workers due to heat index. |
| **Scenario 2: Monsoon Squall** | 26.2°C, 94% RH, **54mm rain**, **42.5 km/h winds**, **2.85m waves**, 998 hPa | *Gives generic advice without knowing current wave height or squall status.* | **Hard Stand-Down**: *"Wind (23 kt) and wave height (2.85m) exceed safe limits for artisanal boats. Stay in port. Secure moorings. Prepare low-lying areas for flooding."* |
| **Scenario 3: Winter Stagnation & Pollution Surge** | 31.0°C, calm sea (0.42m wave), **PM2.5 = 168.4 µg/m³ (Very Unhealthy)** | *Fails to detect air stagnation; advises general beach strolls.* | **Targeted Hazard Advisory**: Sea is safe to launch, but mandates N95 masks on deck; reschedules heavy outdoor labor to dawn/dusk to avoid peak pollution. |

---

## ⚡ Quickstart

### 1. Clone & Install
```bash
git clone https://github.com/csharikrishna/Confluence.git
cd Confluence
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure Environment
Copy the example environment file:
```bash
cp .env.example .env
```
Edit `.env` to configure your keys:
```env
# OpenAQ API Key (Free tier key from https://openaq.org/)
OPENAQ_API_KEY=your_openaq_api_key_here

# NVIDIA NIM API Key (Optional, for frontier model grounding tests)
NVIDIA_API_KEY=your_nvidia_api_key_here

# Server Port
PORT=8000
```

### 3. Run the Development Server
```bash
uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```
Open **[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)** for the interactive OpenAPI / Swagger UI documentation.

---

## 📡 API Reference

### `GET /environment`
Fetches the normalized, multi-domain environmental intelligence snapshot.

#### Query Parameters:
| Parameter | Type | Required | Description | Example |
| :--- | :--- | :--- | :--- | :--- |
| `lat` | `float` | **Yes** | Latitude between `-90.0` and `90.0` | `13.08` |
| `lon` | `float` | **Yes** | Longitude between `-180.0` and `180.0` | `80.27` |
| `name` | `string` | No | Optional human-readable location label | `Chennai Coast` |
| `timeout` | `float` | No | Per-source request timeout in seconds (default: `10.0`) | `10.0` |
| `bypass_cache` | `bool` | No | Force fresh upstream fetch bypassing the 5m cache | `false` |

#### Sample Response:
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
      "humidity_pct": 64,
      "pressure_hpa": 1005.7,
      "precipitation_mm": 0.1,
      "uv_index": 0.25,
      "visibility_m": 6620.0,
      "weather_code": 51,
      "weather_description": "Light drizzle",
      "is_day": true,
      "source": "open-meteo",
      "observed_at": "2026-09-03T11:30:00Z",
      "status": "ok"
    },
    "marine": {
      "sea_surface_temp_c": 30.6,
      "wave_height_m": 0.78,
      "wave_period_s": 8.75,
      "wind_wave_height_m": 0.24,
      "swell_wave_height_m": 0.60,
      "ocean_current_velocity_kmh": 1.1,
      "ocean_current_direction_deg": 18,
      "note": null,
      "source": "open-meteo-marine",
      "observed_at": "2026-09-03T11:30:00Z",
      "status": "ok"
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
      "status": "ok"
    },
    "sun_and_lighting": {
      "sunrise": "2026-09-03T00:26:46+00:00",
      "sunset": "2026-09-03T12:49:55+00:00",
      "solar_noon": "2026-09-03T06:38:21+00:00",
      "day_length_hours": 12.39,
      "nautical_twilight_begin": "2026-09-02T23:41:23+00:00",
      "nautical_twilight_end": "2026-09-03T13:35:18+00:00",
      "source": "sunrise-sunset.org",
      "status": "ok"
    },
    "terrain": {
      "elevation_m": 10.0,
      "coastal_risk_category": "elevated",
      "source": "open-meteo-elevation",
      "status": "ok"
    },
    "climate_baseline": {
      "solar_radiation_kwh_m2": 6.01,
      "avg_temperature_c": 30.82,
      "avg_wind_speed_ms": 3.74,
      "source": "nasa-power",
      "observed_at": "2026-08-28T00:00:00Z",
      "status": "ok"
    },
    "seismic_risk": {
      "recent_events_7d_count": 0,
      "max_magnitude": null,
      "hazard_level": "nominal",
      "search_radius_km": 500,
      "source": "usgs-earthquake",
      "status": "ok"
    }
  },
  "meta": {
    "confidence": "high — all sources responded successfully",
    "failed_sources": [],
    "total_latency_ms": 2652.44,
    "cache_hit": false
  }
}
```

---

## 🧪 Automated Testing

Confluence includes three dedicated test suites covering offline mock unit tests, live remote verification, and failure isolation:

### 1. Offline Unit & Mocked Integration Suite (28 Tests)
Validates boundary sanity checks, canonical ISO UTC normalization, coordinate validation, and isolated failure degradation without external network calls:
```bash
pytest tests/test_api.py tests/test_caching_and_ratelimit.py tests/test_endpoint_mocked.py -v
```
```text
======================== 28 passed in 3.56s ========================
```

### 2. Live Remote Deployment Suite (4 Tests)
Targets the live deployed service to verify real-world connectivity, CORS headers, cache hits, and 400 bad-request handling *(automatically skipped when running offline)*:
```bash
# On Windows (PowerShell):
$env:API_BASE_URL="https://confluence-si41.onrender.com"; pytest tests/test_live_remote.py -v

# On Linux / macOS:
API_BASE_URL="https://confluence-si41.onrender.com" pytest tests/test_live_remote.py -v
```
```text
============================== 4 passed in 3.92s ==============================
```

### 3. 7-Way Failure-Isolation Stress Suite
Executes 7 independent failure-isolation runs, killing each upstream source individually to verify graceful degradation:
```bash
python test_stress_and_edge_cases.py
```
```text
OVERALL STRESS-TEST RESULT: ALL PASS [100%]
```

---

## ☁️ 1-Click Deployment (Render / Railway)

This repository includes a pre-configured [render.yaml](render.yaml) and [Procfile](Procfile):

1. Fork or push this repository to GitHub.
2. In **[Render](https://dashboard.render.com/)**, click **New +** $\rightarrow$ **Blueprint** and select this repo.
3. Set `OPENAQ_API_KEY` (and optional `NVIDIA_API_KEY`) in Render's environment settings.
4. Add your deployed URL to GitHub Secrets as `RENDER_APP_URL` to enable the keep-alive cron workflow.

---

## 📚 Documentation & Project History

- **Historical Phase 1 Pilot Specification**: [docs/phase1-planning-archive.md](docs/phase1-planning-archive.md)
- **Frontier LLM Grounding PoC**: [test_multi_model_and_conditions.py](test_multi_model_and_conditions.py)

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.
