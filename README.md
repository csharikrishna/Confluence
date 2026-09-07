# Confluence — Unified Environmental Intelligence API

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB.svg?logo=python&logoColor=white)](https://python.org)
[![Tests](https://img.shields.io/badge/Tests-212%20Total%20(203%20Offline%20%2B%209%20Remote)-brightgreen.svg)](tests/)
[![CI](https://github.com/csharikrishna/Confluence/actions/workflows/tests.yml/badge.svg)](.github/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Render](https://img.shields.io/badge/Deploy-Render-46E3B7.svg?logo=render&logoColor=white)](https://confluence-si41.onrender.com)

A normalized API and platform that concurrently aggregates **50+ physical, marine, and atmospheric hyperparameters** across **10 free public data sources** into a single validated JSON snapshot — then connects those raw numbers into **physics-informed composite signals** (heat index, sea state, storm potential, coastal flood risk, compound estuarine discharge, tropical cyclone proximity, and active fire/smoke causality) and a **config-driven alerting layer**, backed by persisted history across a **multi-location registry** covering 5 coastal locations across India's South, West, and East coasts (Chennai, Kochi, Visakhapatnam, Mumbai, Kolkata/Sundarbans).

Built to **ground frontier AI models** and maritime decision systems in empirical, real-time physical truth — reducing weather hallucinations and enabling operational safety advisories that cite verified observations instead of training-data priors.

**Current status: Full Stack Intelligence Platform.** Real-time telemetry, 24h trends, multi-location registry, rules engine, Argon2id developer authentication, Model Context Protocol (MCP) server, and grounded LLM chatbot are live.

---

## Contents

- [Live service](#live-service)
- [Highlights](#highlights)
- [AI Agent & MCP Integration (Claude & Cursor)](#ai-agent--mcp-integration-claude-desktop--cursor)
- [Data sources](#data-sources)
- [Why this matters](#why-this-matters)
- [Quickstart](#quickstart)
- [Project structure](#project-structure)
- [API reference](#api-reference)
- [Phase 2: history, trends & alerting](#phase-2--history-trends--alerting)
- [Phase 3: grounded coastal AI chatbot](#phase-3--grounded-coastal-ai-chatbot)
- [Authentication & developer API keys](#authentication--developer-api-keys)
- [Testing](#testing)
- [Deployment](#deployment)
- [Limitations & production readiness](#limitations--production-readiness)
- [Documentation](#documentation)
- [License](#license)

---

## Live service

- **Base URL**: [`https://confluence-si41.onrender.com`](https://confluence-si41.onrender.com)
- **Interactive docs (Swagger)**: [`/docs`](https://confluence-si41.onrender.com/docs)
- **Health probe**: [`/health`](https://confluence-si41.onrender.com/health)
- **Sample query**: [`/environment?lat=13.08&lon=80.27&name=Chennai%20Coast`](https://confluence-si41.onrender.com/environment?lat=13.08&lon=80.27&name=Chennai%20Coast)
- **Interactive Chat**: [`/chat`](https://confluence-si41.onrender.com/chat)

---

## Highlights

- **50+ hyperparameters across 10 free APIs** — atmospheric weather, sea-state hydrodynamics, dual-tier air quality (OpenAQ sensor array + Open-Meteo CAMS atmospheric model fallback), river discharge & estuarine flood forecasting, GDACS global tropical cyclone tracking, NASA FIRMS satellite fire/hotspot causality, solar/nautical twilight ephemeris, topography/elevation, climate baselines, and recent seismic events.
- **Concurrent fan-out** — all 10 upstream sources are dispatched simultaneously via `ThreadPoolExecutor`, bounding total latency to the single slowest source (~2.4s) rather than sequential execution (~14s).
- **Two-tier caching** — a 24h station-metadata cache eliminates redundant spatial discovery, and a 5-minute response cache serves repeated queries in well under a millisecond (`bypass_cache=true` to force a fresh fetch).
- **Data-quality sentinel** — every response is checked against physical boundaries (no negative wave heights, no >100% humidity, no out-of-range pressure) before it's returned.
- **Production-hardened** — tiered rate limiting (slowapi), global exception handlers preventing stack trace leakage, structured request logging, and CI gates on every push.
- **Physics-informed reasoning layer** — composite signals (heat index, sea state, storm potential, coastal flood risk, tsunami advisory) computed from cited meteorological/oceanographic standards, plus a config-driven alerting engine.
- **Pluggable, verified storage** — SQLite by default, with MongoDB Atlas as the production durable backend, verified against real running clusters.
- **Native Model Context Protocol (MCP)** — official `confluence-mcp` package for Claude Desktop and Cursor agent tool-use.
- **Developer API Key & Auth Lifecycle** — Argon2id password hashing, session tokens, and developer API key lifecycle (`conf_live_...`) with tiered quotas.

---

## AI Agent & MCP Integration (Claude Desktop, Cursor & MCP Clients)

Confluence provides an official **Model Context Protocol (MCP)** server ([`packages/confluence-mcp`](packages/confluence-mcp)) enabling Anthropic Claude Desktop, Claude Code, Cursor, Zed, Cline, and standard MCP clients to query live coastal sensor telemetry and physics derivations directly. *(Note: MCP is an open standard originated by Anthropic; distinct from OpenAI's proprietary Custom GPTs API).*

### Claude Desktop Configuration
Add to `claude_desktop_config.json` (`%APPDATA%\Claude\claude_desktop_config.json` on Windows or `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "confluence": {
      "command": "npx",
      "args": ["-y", "confluence-mcp"],
      "env": {
        "CONFLUENCE_API_KEY": "conf_live_YOUR_API_KEY",
        "CONFLUENCE_API_URL": "https://confluence-si41.onrender.com"
      }
    }
  }
}
```

### Cursor Configuration
Add to `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "confluence": {
      "command": "npx",
      "args": ["-y", "confluence-mcp"],
      "env": {
        "CONFLUENCE_API_KEY": "conf_live_YOUR_API_KEY"
      }
    }
  }
}
```

### Exposed MCP Capabilities
- **Tools**:
  - `get_coastal_snapshot`: 10-in-1 real-time telemetry + NOAA Heat Index, WMO Beaufort force, small craft advisories, GDACS cyclone advisories, NASA FIRMS fire attribution, storm surge, and compound river flood risk.
  - `get_preset_locations`: Validated coastal observatories across India's South, West, and East coasts (Chennai, Mumbai, Kochi, Visakhapatnam, Kolkata/Sundarbans).
  - `check_coastal_alerts`: Threshold breaches, cyclone depressions, and hazard advisories.
  - `get_historical_trends`: 24-hour physical deltas (temperature, pressure fall, wave height, wind).
  - `ask_coastal_assistant`: Sensor-grounded natural language maritime guidance.
- **Resources**: `confluence://locations` and `confluence://methodology`.
- **Prompts**: `coastal-safety-audit` and `cyclone-readiness-check`.

---

## Data sources

| Domain | Service | Access | Hyperparameters |
| :--- | :--- | :--- | :--- |
| Weather & atmosphere | Open-Meteo Forecast | Free, no key | `temperature_c`, `apparent_temperature_c`, `wind_speed_kmh`, `wind_gusts_kmh`, `wind_direction_deg`, `humidity_pct`, `pressure_hpa`, `surface_pressure_hpa`, `precipitation_mm`, `cloud_cover_pct`, `uv_index`, `visibility_m`, `weather_code` (WMO), `weather_description`, `is_day` |
| Ocean hydrodynamics | Open-Meteo Marine | Free, no key | `sea_surface_temp_c`, `wave_height_m`, `wave_period_s`, `wave_direction_deg`, `wind_wave_height_m`, `wind_wave_period_s`, `wind_wave_direction_deg`, `swell_wave_height_m`, `swell_wave_period_s`, `swell_wave_direction_deg`, `ocean_current_velocity_kmh`, `ocean_current_direction_deg` |
| Air quality & chemistry | OpenAQ + Open-Meteo fallback | Free tier / free, no key | `pm25`, `pm10`, `o3`, `no2`, `so2`, `co`, `aqi_category` (EPA), `us_aqi`, `european_aqi`, `dust_ug_m3`, `aerosol_optical_depth`, `data_type` (`measured` ground sensors or `modeled` CAMS atmospheric estimates) |
| River hydrology & flood risk | Open-Meteo Flood | Free, no key | `river_discharge_m3s`, `discharge_max_7d_m3s`, `applicable` (Copernicus GloFAS river basin model) |
| Tropical cyclone tracking | GDACS (UN / EC JRC) | Free, no key | `active_cyclone_nearby`, `nearest_cyclone_name`, `nearest_cyclone_distance_km`, `cyclone_alert_level`, `max_wind_speed_kmh`, `active_cyclones_count` |
| Active fire & smoke causality | NASA FIRMS (VIIRS/MODIS) | Free (NRT open feed / key) | `hotspot_count`, `nearest_hotspot_distance_km`, `max_frp_mw`, `high_confidence_count`, `fire_detected`, `search_radius_km` |
| Astronomical & marine lighting | Sunrise-Sunset.org | Free, no key | `sunrise`, `sunset`, `solar_noon`, `day_length_hours`, civil/nautical/astronomical twilight begin/end |
| Topography & elevation | Open-Meteo Elevation | Free, no key | `elevation_m`, `coastal_risk_category` (`low-lying (<5m)` vs `elevated`) |
| Climate baseline | NASA POWER | Free, no key | `solar_radiation_kwh_m2`, `avg_temperature_c`, `avg_wind_speed_ms`, `observed_at` |
| Seismic & tsunami risk | USGS Earthquakes | Free, no key | `recent_events_7d_count`, `max_magnitude`, `max_magnitude_depth_km`, `hazard_level`, `search_radius_km` |

---

## Why this matters

Frontier LLMs asked operational coastal questions without grounding either hallucinate seasonal stereotypes or admit total blindness. A unified, verified snapshot changes that:

| Scenario | Raw observations | Ungrounded response | Grounded response |
| :--- | :--- | :--- | :--- |
| Dry heat spike | 35.4°C, 47% RH, 0.0mm rain, 0.76m swell | Guesses monsoon downpours and high waves from static regional priors | Safe for 2–3hr artisanal fishing; mandates hourly hydration breaks given heat index |
| Monsoon squall | 26.2°C, 94% RH, 54mm rain, 42.5 km/h wind, 2.85m waves, 998 hPa | Gives generic advice, unaware of current wave height or squall status | "Wind (23kt) and wave height (2.85m) exceed safe limits for artisanal boats. Stay in port. Secure moorings." |
| Winter stagnation + pollution surge | 31.0°C, calm sea (0.42m wave), PM2.5 = 168.4 µg/m³ (very unhealthy) | Fails to detect air stagnation; advises a beach stroll | Sea is safe to launch, but mandates N95 masks on deck; reschedules outdoor labor to dawn/dusk |

---

## Quickstart

### 1. Clone and install

```bash
git clone https://github.com/csharikrishna/Confluence.git
cd Confluence
python -m venv venv

# Windows
.\venv\Scripts\activate
# Linux / macOS
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

At minimum, set `OPENAQ_API_KEY` (free from [openaq.org](https://openaq.org)). Optional keys include `NVIDIA_API_KEY` (for the grounded chatbot), `MONGODB_URI` (for durable Atlas storage), and `ALERT_WEBHOOK_URL` (for Discord/Slack alerts).

### 3. Run the dev server

```bash
uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

- **Interactive API Docs (Swagger)**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Web Interface**: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)

---

## Project structure

```text
Confluence/
├── app.py                    # Root gateway & backward-compatible uvicorn proxy
├── backend/                  # Clean backend service package
│   ├── __init__.py           # Package initialization & path resolution
│   ├── app.py                # FastAPI routes, lifespan, middleware & static mounts
│   ├── auth.py               # Argon2id password hashing, sessions & API key auth
│   ├── chat.py / chatbot.py  # Grounded LLM reasoning & safety audit prompt builder
│   ├── environmental_data.py # 8-source concurrent ingestion pipeline & normalizers
│   ├── derived_insights.py   # Physics signals (Heat Index, Beaufort, small craft, estuarine flood)
│   ├── rules_engine.py       # Config-driven hazard evaluation engine
│   ├── alert_rules.json      # Threshold and trend condition definitions
│   ├── locations.py / .json  # 5 registered coastal stations across South, West, and East coasts
│   ├── notifications.py      # Slack/Discord webhook dispatcher
│   ├── gdrive_backup.py      # Daily disaster-recovery snapshot exporter
│   ├── db_backend.py         # Storage router (SQLite / MongoDB Atlas)
│   ├── storage.py            # SQLite local persistence & trend diffs
│   ├── mongo_storage.py      # MongoDB Atlas durable production backend
│   ├── upstream_health.py    # Upstream API latency & SLA monitor
│   └── utils.py              # Dotted-path dictionary traversal helper
├── frontend/                 # React + Vite interactive coastal UI
├── packages/
│   └── confluence-mcp/       # Official Model Context Protocol (MCP) server
├── tests/                    # Complete pytest suite (194 tests)
├── scripts/                  # Empirical RAG benchmarks, stress testing, PoCs
├── docs/                     # Design specs, walkthroughs, benchmark rubrics
├── static/                   # Benchmark results and media assets
├── render.yaml & Procfile    # Render blueprint deployment configs
└── requirements*.txt         # Base, mongo, gdrive, and benchmark dependencies
```

---

## API reference

### Core Environmental Telemetry

#### `GET /environment`
Fetches the normalized, multi-domain environmental snapshot for any coordinates.

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `lat` | `float` | Yes | Latitude, `-90.0` to `90.0` |
| `lon` | `float` | Yes | Longitude, `-180.0` to `180.0` |
| `name` | `string` | No | Optional human-readable label |
| `timeout` | `float` | No | Per-source timeout in seconds (default `10.0`) |
| `bypass_cache` | `bool` | No | Force fresh fetch, skipping the 5-minute cache |

#### `GET /environment/history`
Query persisted snapshot history for a location:
```
GET /environment/history?lat=13.08&lon=80.27&start=2026-09-01T00:00:00Z&end=2026-09-03T00:00:00Z&field=weather.temperature_c
```

#### `GET /locations`
Lists every coastal point tracked by the platform for pre-warming and alerting.

#### `GET /alerts`
Evaluates the rules engine against all registered locations or a specific `lat`/`lon`.

#### `GET /health`
Returns service status, rate limiting, caching state, and storage backend connectivity.

#### `GET /api/health/upstream`
Pings all 10 upstream sources concurrently and returns live status, HTTP code, and latency in milliseconds.

---

### Authentication & Developer Keys

| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/auth/register` | Register new user account (Argon2id) | No |
| `POST` | `/api/auth/login` | Login and receive bearer token | No |
| `GET` | `/api/auth/me` | Fetch active user profile | Yes (Bearer) |
| `POST` | `/api/auth/keys` | Generate new developer API key (`conf_live_...`) | Yes (Bearer) |
| `GET` | `/api/auth/keys` | List active developer API keys | Yes (Bearer) |
| `DELETE` | `/api/auth/keys/{prefix}` | Revoke an API key | Yes (Bearer) |
| `POST` | `/api/auth/keys/rotate` | Zero-downtime key rotation | Yes (Bearer) |

---

### Grounded Coastal AI Chatbot

#### `POST /ask`
Natural language coastal intelligence query. Grounded directly in live telemetry:
```json
{
  "question": "Can artisanal fishermen launch near Chennai right now?",
  "location": "Chennai Coast"
}
```

#### `GET /chat`
Renders the dedicated coastal chatbot interface.

---

## Phase 2 — History, Trends & Alerting

### Physics-informed derived insights
Every `/environment` response includes `meta.derived_insights` — composite signals computed from the raw hyperparameters using cited, published physical standards, not a learned model:

| Field | Combines | Standard |
| :--- | :--- | :--- |
| `heat_index_c` / `heat_index_category` | Temperature + humidity | NOAA/Rothfusz heat index regression, with published low/high-humidity corrections |
| `dew_point_c` / `fog_risk` | Temperature + humidity + wind | Magnus-Tetens approximation |
| `beaufort_scale` | Wind speed | WMO-adopted Beaufort scale (force 0–12) |
| `imd_cyclone_category` | Sustained wind speed | India Meteorological Department official classification |
| `small_craft_risk_level` | Wave height + wind + gusts | NWS coastal marine warning tiers (Small Craft Advisory → Hurricane Force) |
| `storm_potential_score` / `_level` | Pressure + gusts + cloud cover + 3h pressure trend | Engineering heuristic |
| `rapid_pressure_fall` | 24h pressure change, latitude-normalized | Bergeron / Sanders-Gyakum rapid-cyclogenesis criterion |
| `air_stagnation_index` | Wind + precipitation + PM2.5 | Engineering heuristic |
| `coastal_flood_risk` | Elevation + wave height + wind + inverse-barometer surge + river discharge | Inverse barometer effect (~1cm sea-level rise per 1hPa deficit) + Copernicus GloFAS compound estuarine discharge |
| `tsunami_advisory` | Seismic magnitude + depth + elevation | USGS shallow-focus (<70km) criterion |
| `cyclone_advisory` | Proximity + intensity + alert level | GDACS global multi-hazard tropical cyclone tracking (distance and maritime warning) |
| `air_quality_causality` | PM2.5 + satellite thermal hotspots | NASA FIRMS VIIRS/MODIS active fire anomaly spatial attribution (<300 km) |

Full citations and scope notes: [`backend/derived_insights.py`](backend/derived_insights.py).

### Config-driven alerting
A config-driven rules engine ([`backend/alert_rules.json`](backend/alert_rules.json)) evaluates threshold and trend conditions over both raw and derived fields, against every registered location or a single `lat`/`lon`.

Triggered alerts are deduped per rule/location on a 60-minute cooldown and optionally dispatched to Slack/Discord via `ALERT_WEBHOOK_URL`.

---

## Phase 3 — Grounded Coastal AI Chatbot

Confluence incorporates a strict grounding prompt architecture that forces frontier LLMs (such as NVIDIA Nemotron or Llama 3) to base all claims exclusively on verified observational JSON data:
1. Rejects hallucinated regional priors if live data is unavailable.
2. Injects exact sensor values (e.g. wave height, PM2.5, heat index, wind velocity).
3. Produces concrete, actionable safety advisories for fishermen, coastal residents, and harbor masters.

---

## Authentication & Developer API Keys

Confluence features a dual-tier consumption model:
- **Anonymous Tier**: Public access to `/environment` and `/alerts`, rate-limited to 30 requests/minute per IP.
- **Authenticated Tier**: Passing an `X-API-Key: conf_live_...` header unlocks higher capacity (100 requests/minute per key), dedicated quotas, and access to developer endpoints.

Passwords are cryptographically secured using **Argon2id**, and API keys use high-entropy secrets with SHA-256 hash storage.

---

## Testing

The project maintains a rigorous **212-test automated test suite**:

### Offline unit & mocked integration suite (203 tests)
Covers boundary sanity checks, ISO-UTC normalization, coordinate validation, failure degradation, physics calculations, rules engine scenarios, dual storage backends, Argon2id auth, and grounded prompt schemas.

```bash
pytest tests/ --ignore=tests/test_live_remote.py -v
```

### Live remote deployment suite (9 tests)
Verifies the deployed service directly — connectivity, CORS, cache hits, 400 handling.

```bash
API_BASE_URL="https://confluence-si41.onrender.com" pytest tests/test_live_remote.py -v
```

### Run All Tests
```bash
pytest tests/ -v
```

---

## Deployment

This repository includes a pre-configured [`render.yaml`](render.yaml) and [`Procfile`](Procfile).

1. Fork or push this repository to GitHub.
2. In [Render](https://dashboard.render.com/), click **New** → **Blueprint** and select this repo.
3. Set `OPENAQ_API_KEY` (and optionally `NVIDIA_API_KEY`, `MONGODB_URI`) in Render's environment settings.
4. Add your deployed URL to GitHub Secrets as `RENDER_APP_URL` to enable keep-alive and hourly ingestion cron workflows.

---

## Limitations & production readiness

Documented honestly rather than oversold:

- **Tiered Quotas vs Public Access**: Anonymous access is open and rate-limited to 30 req/min. Authenticated API key quotas require user registration.
- **Single instance, no SLA**: A CI test gate runs on every push, but a dedicated monitor (UptimeRobot, Better Uptime) should be added for production alerting.
- **Derived signals are correctly cited, not independently certified**: Most formulas are real published standards (see table above), but outputs should be treated as strong physical guidance rather than certified regulatory safety authority.
- **Storage Durability**: SQLite on Render's free tier is ephemeral across redeploys; production uses MongoDB Atlas to ensure persistent 24h history and alert records.

---

## Documentation

- [`docs/PHASE2_WALKTHROUGH.md`](docs/PHASE2_WALKTHROUGH.md) — history, trends, alerting, storage backends, and hardening
- [`docs/phase2-plan.md`](docs/phase2-plan.md) — Phase 2 design specifications
- [`docs/PHASE3.md`](docs/PHASE3.md) — Phase 3 grounded LLM chatbot specifications
- [`docs/phase1-planning-archive.md`](docs/phase1-planning-archive.md) — historical Phase 1 pilot specification
- [`scripts/run_rag_benchmark.py`](scripts/run_rag_benchmark.py) — empirical scientific RAG benchmark suite

---

## License

MIT License — see [`LICENSE`](LICENSE).
