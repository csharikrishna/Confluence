# 🌊 Confluence — Unified Environmental Intelligence API

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB.svg?logo=python&logoColor=white)](https://python.org)
[![Tests](https://img.shields.io/badge/Tests-112%20Total%20(108%20Offline%20%2B%204%20Remote)-brightgreen.svg)](tests/)
[![CI](https://github.com/csharikrishna/Confluence/actions/workflows/tests.yml/badge.svg)](.github/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Render](https://img.shields.io/badge/Deploy-Render-46E3B7.svg?logo=render&logoColor=white)](https://confluence-si41.onrender.com)

A high-performance, normalized API that concurrently aggregates **50+ physical, marine, and atmospheric hyperparameters** across **7 free public APIs** into a single validated JSON snapshot — then connects those raw numbers into **physics-informed composite signals** (heat index, sea state, storm potential, coastal flood risk) and a **config-driven alerting layer**, backed by persisted history across a **multi-location registry**.

Engineered specifically to **ground frontier AI models** (Nemotron, Llama 3.2, GPT-4o, Claude) and maritime decision systems in empirical, real-time physical truth—eliminating weather hallucinations and enabling high-stakes operational safety advisories.

**Phase 2 (current):** History & trends, multi-location support, and a rule-based reasoning layer are live — see [§ Phase 2](#-phase-2--history-trends--alerting) below. See [docs/phase2-plan.md](docs/phase2-plan.md) for the design doc this was built from.

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

## 🧠 Phase 2 — History, Trends & Alerting

Phase 1 answered "what's happening right now, at one point." Phase 2 adds memory (what's changing), a network (more than one point), and judgment (proactively flagging what's worth attention) — without adding ML, new external data sources, or infra beyond a SQLite file and the existing cron pattern.

### Physics-informed derived insights

Every `/environment` response now includes `meta.derived_insights` — composite signals computed from the raw hyperparameters using cited, published physical/meteorological standards, **not** a learned model. This does the "connect the hyperparameters" arithmetic once, server-side, instead of leaving an LLM to guess at it:

| Field | What it combines | Standard cited |
| :--- | :--- | :--- |
| `heat_index_c` / `heat_index_category` | Temperature + humidity → physiological heat stress | NOAA/Rothfusz heat index regression |
| `dew_point_c` / `fog_risk` | Temperature + humidity + wind → fog/mist likelihood | Magnus-Tetens approximation |
| `beaufort_scale` | Wind speed → force 0-12 | WMO-adopted Beaufort scale |
| `imd_cyclone_category` | Sustained wind speed → system classification | IMD (India Meteorological Department) official scale |
| `small_craft_risk_level` | Wave height + wind speed + gusts → marine warning tier | NWS coastal marine warning wind/sea criteria |
| `storm_potential_score` / `_level` | Pressure + gusts + cloud cover → composite storm precursor score | Engineering heuristic (see honest scope note below) |
| `rapid_pressure_fall` | 24h pressure change, normalized by latitude | Bergeron / Sanders-Gyakum (1980) rapid-cyclogenesis criterion |
| `air_stagnation_index` | Wind speed + precipitation + PM2.5 → pollutant-accumulation risk | Engineering heuristic |
| `coastal_flood_risk` | Elevation + wave height + wind + inverse-barometer surge | Inverse barometer effect (~1cm sea-level rise per 1hPa deficit) |
| `tsunami_advisory` | Seismic magnitude + depth + elevation → tsunami run-up caution | USGS shallow-focus (<70km) criterion |

**Honest scope note:** the heat index, dew point, Beaufort scale, IMD classification, NWS marine warning criteria, inverse barometer effect, and rapid-pressure-fall formula are all real, cited, published standards — not something I invented. The two exceptions are `storm_potential_score` and `air_stagnation_index`, which remain engineering heuristics (reasonable, documented threshold combinations) rather than a single official published index — no such standardized single-number index exists for either in the literature I'm aware of. The rapid-pressure-fall criterion is itself borrowed from *extratropical* cyclogenesis and applied here only as a generic "something's dropping fast" signal at these tropical/subtropical latitudes, not as a literal claim of bombogenesis — see the docstring in `derived_insights.py` for the full caveat.

### `GET /environment/history`
Query persisted snapshot history for a location:

```
GET /environment/history?lat=13.08&lon=80.27&start=2026-09-01T00:00:00Z&end=2026-09-03T00:00:00Z&field=weather.temperature_c
```

Every fresh (non-cache-hit) `/environment` fetch is persisted to a local SQLite store (`snapshots` table) in the background, so history accumulates from both organic traffic and the hourly ingestion cron below. `meta.trend_24h` on `/environment` is a lightweight diff against the closest stored reading ~24h ago (`null` until enough history exists). Snapshots older than 90 days are pruned automatically at startup.

### `GET /locations`
Lists every coastal point the service tracks for pre-warming, history ingestion, and `/alerts` — currently Chennai, Visakhapatnam, Kochi, Mumbai, and Kolkata/Sundarbans. `/environment` still accepts **any** `lat`/`lon`; this registry is what the scheduled jobs iterate over.

### `GET /alerts`
Evaluates a config-driven rules engine (`alert_rules.json`) — thresholds and trend conditions over both raw and derived fields — against every registered location (or a single `lat`/`lon`), and returns currently active alerts:

```json
{
  "generated_at": "2026-09-03T12:00:05Z",
  "locations_checked": 5,
  "active_alert_count": 2,
  "active_alerts": [
    {
      "id": "small_craft_unsafe",
      "severity": "high",
      "message": "Sea state 'unsafe' for small craft (wave 1.38m, wind 17.1km/h). Do not launch small or artisanal vessels.",
      "location": { "name": "Mumbai Coast", "lat": 18.94, "lon": 72.84 }
    }
  ]
}
```

Rules cover unhealthy PM2.5, unsafe sea state, storm-level wind/gusts, heavy-rain flood risk, dangerous heat index, composite coastal-flood/storm-potential scores, seismic tsunami caution, air stagnation, and two trend-based rules (rapid temperature spike, PM2.5 doubling over 3h) that need stored history to evaluate. Thresholds live entirely in `alert_rules.json` — tunable without a code change. Triggered alerts are logged to a `alerts_log` table (deduped per rule/location on a 60-minute cooldown) for future "this alert fired N times this month" reporting.

**Optional alert delivery:** set `ALERT_WEBHOOK_URL` to a Slack or Discord incoming-webhook URL and every newly-triggered (non-duplicate) alert is also pushed there — the Phase 2C "stretch goal" from the design doc. Fully inert if left unset.

### Scheduled ingestion
`.github/workflows/ingest_history.yml` runs hourly, reads the live `/locations` registry, and calls `/environment?bypass_cache=true` for each point — causing the deployed app to persist a fresh snapshot per location every hour, independent of organic traffic.

> **Note on Render's free tier:** its filesystem is ephemeral — a redeploy or restart wipes `confluence_history.db`. History still accumulates correctly between restarts (it's a real file, not in-memory), it just isn't durable across deploys until a persistent disk is attached. Set `CONFLUENCE_DB_PATH` to relocate the DB file if you do add one.

### Explicitly out of scope (Phase 2)
No ML/forecasting, no new data sources beyond the existing 7, no user accounts or per-user alert subscriptions, no UI, no message-queue infra — see [docs/phase2-plan.md](docs/phase2-plan.md) §7 for the full rationale.

---

## 🧪 Automated Testing

Confluence includes dedicated test suites covering offline mock unit tests, live remote verification, and failure isolation, across both Phase 1 and Phase 2:

### 1. Offline Unit & Mocked Integration Suite (108 Tests)
Validates boundary sanity checks, canonical ISO UTC normalization, coordinate validation, isolated failure degradation, the physics-informed derived insights, the rules engine (including the Phase 1 Day 2 monsoon-squall fixture and a false-positive check on calm data), the SQLite history store, the locations registry, the alert webhook, and every endpoint — all without external network calls. This suite runs automatically on every push/PR via [`.github/workflows/tests.yml`](.github/workflows/tests.yml):
```bash
pytest tests/ --ignore=tests/test_live_remote.py -v
```
```text
======================== 108 passed in ~5s ========================
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
4. Add your deployed URL to GitHub Secrets as `RENDER_APP_URL` to enable the keep-alive and hourly ingestion cron workflows.
5. Optional: set `ALERT_WEBHOOK_URL` (Slack/Discord) to receive pushed alerts. Optional: attach a Render persistent disk and set `CONFLUENCE_DB_PATH` to make history/trends survive redeploys (see `render.yaml` comments — requires a paid plan, so it's off by default).

---

## ⚠️ Limitations & Production Readiness

Documenting this honestly rather than overselling it:

- **History isn't durable on the free tier.** Render's free-tier filesystem is ephemeral — `confluence_history.db` is wiped on every redeploy. Trend/alert logic is correct and works between restarts, it just isn't durable across deploys until a persistent disk is attached (see `render.yaml`).
- **No authentication.** `/environment`, `/alerts`, and `/environment/history` are public, rate-limited (30-60/min) but unauthenticated, by explicit Phase 2 design (see [docs/phase2-plan.md](docs/phase2-plan.md) §7). Fine for a public grounding API; not a fit if per-consumer quotas or private data ever enter scope.
- **Single free-tier instance.** No load balancing, no uptime monitoring/paging, no SLA. A CI test gate now runs on every push ([`.github/workflows/tests.yml`](.github/workflows/tests.yml)), but nothing currently watches the live deployment's uptime — that needs an external monitor (e.g. UptimeRobot/Better Uptime) pointed at `/health`.
- **Most derived signals now cite official published standards** (NOAA heat index, Magnus-Tetens dew point, WMO Beaufort scale, IMD cyclone classification, NWS marine warning criteria, the inverse barometer effect, USGS shallow-focus tsunami criterion) rather than ad-hoc bands — see the table above. `storm_potential_score` and `air_stagnation_index` remain engineering heuristics since no single standardized published index exists for either. None of this has been reviewed by an actual meteorologist/oceanographer — the formulas are correctly cited, but nobody with domain authority has signed off on how they're combined or applied here. Treat outputs as a strong, sourced first pass, not a certified safety authority.
- **Not wired into any AI platform.** Nothing here makes a frontier model call this API automatically — it has to be registered as a tool/function by whoever builds the agent that uses it. This is grounding infrastructure a developer plugs in, not a live integration today.

---

## 📚 Documentation & Project History

- **Phase 2 Walkthrough (History, Trends, Alerting, Hardening)**: [docs/PHASE2_WALKTHROUGH.md](docs/PHASE2_WALKTHROUGH.md)
- **Phase 2 Design Doc**: [docs/phase2-plan.md](docs/phase2-plan.md)
- **Historical Phase 1 Pilot Specification**: [docs/phase1-planning-archive.md](docs/phase1-planning-archive.md)
- **Frontier LLM Grounding PoC**: [test_multi_model_and_conditions.py](test_multi_model_and_conditions.py)

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.
