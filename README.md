# Confluence — Unified Environmental Intelligence API

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB.svg?logo=python&logoColor=white)](https://python.org)
[![Tests](https://img.shields.io/badge/Tests-171%20Total%20(167%20Offline%20%2B%204%20Remote)-brightgreen.svg)](tests/)
[![CI](https://github.com/csharikrishna/Confluence/actions/workflows/tests.yml/badge.svg)](.github/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Render](https://img.shields.io/badge/Deploy-Render-46E3B7.svg?logo=render&logoColor=white)](https://confluence-si41.onrender.com)

A normalized API that concurrently aggregates **50+ physical, marine, and atmospheric hyperparameters** across **7 free public data sources** into a single validated JSON snapshot — then connects those raw numbers into **physics-informed composite signals** (heat index, sea state, storm potential, coastal flood risk) and a **config-driven alerting layer**, backed by persisted history across a **multi-location registry**.

Built to **ground frontier AI models** and maritime decision systems in empirical, real-time physical truth — reducing weather hallucinations and enabling operational safety advisories that cite verified observations instead of training-data priors.

**Current status: Phase 2.** History and trends, multi-location support, and a rule-based reasoning layer are live — see [Phase 2: History, Trends & Alerting](#phase-2--history-trends--alerting) below, and [`docs/phase2-plan.md`](docs/phase2-plan.md) for the design doc it was built from.

---

## Contents

- [Live service](#live-service)
- [Highlights](#highlights)
- [Data sources](#data-sources)
- [Why this matters](#why-this-matters)
- [Quickstart](#quickstart)
- [Project structure](#project-structure)
- [API reference](#api-reference)
- [Phase 2: history, trends & alerting](#phase-2--history-trends--alerting)
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

---

## Highlights

- **50+ hyperparameters across 7 free APIs** — atmospheric weather, sea-state hydrodynamics, dual-tier air quality, solar/nautical twilight ephemeris, topography/elevation, climate baselines, and recent seismic events.
- **Concurrent fan-out** — all 7 upstream sources are dispatched simultaneously via `ThreadPoolExecutor`, so total latency is bounded by the single slowest source (~2.6s) rather than the sum of all seven (~10s).
- **Two-tier caching** — a 24h station-metadata cache eliminates redundant spatial discovery, and a 5-minute response cache serves repeated queries in well under a millisecond (`bypass_cache=true` to force a fresh fetch).
- **Data-quality sentinel** — every response is checked against physical boundaries (no negative wave heights, no >100% humidity, no out-of-range pressure) before it's returned.
- **Production-hardened** — rate limiting, a global exception handler that never leaks stack traces, structured request logging, and a CI gate that runs the full test suite on every push.
- **Physics-informed reasoning layer** — composite signals (heat index, sea state, storm potential, coastal flood risk, tsunami advisory) computed from cited meteorological/oceanographic standards, plus a config-driven alerting engine — see [Phase 2](#phase-2--history-trends--alerting).
- **Pluggable, verified storage** — SQLite by default, with MongoDB Atlas as a drop-in durable backend, verified against a real running instance, not just mocks.

---

## Data sources

| Domain | Service | Access | Hyperparameters |
| :--- | :--- | :--- | :--- |
| Weather & atmosphere | Open-Meteo Forecast | Free, no key | `temperature_c`, `apparent_temperature_c`, `wind_speed_kmh`, `wind_gusts_kmh`, `wind_direction_deg`, `humidity_pct`, `pressure_hpa`, `surface_pressure_hpa`, `precipitation_mm`, `cloud_cover_pct`, `uv_index`, `visibility_m`, `weather_code` (WMO), `weather_description`, `is_day` |
| Ocean hydrodynamics | Open-Meteo Marine | Free, no key | `sea_surface_temp_c`, `wave_height_m`, `wave_period_s`, `wave_direction_deg`, `wind_wave_height_m`, `wind_wave_period_s`, `wind_wave_direction_deg`, `swell_wave_height_m`, `swell_wave_period_s`, `swell_wave_direction_deg`, `ocean_current_velocity_kmh`, `ocean_current_direction_deg` |
| Air quality & chemistry | OpenAQ + Open-Meteo fallback | Free tier / free, no key | `pm25`, `pm10`, `o3`, `no2`, `so2`, `co`, `aqi_category` (EPA), `us_aqi`, `european_aqi`, `dust_ug_m3`, `aerosol_optical_depth`, `tier` (`ground_sensor` or `atmospheric_model`) |
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

At minimum, set `OPENAQ_API_KEY` (free from [openaq.org](https://openaq.org)). Everything else in `.env.example` is optional — durable storage, alert webhooks, and Google Drive backup all stay inert until explicitly configured.

### 3. Run the dev server

```bash
uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) for interactive Swagger docs.

---

## Project structure

```
Confluence/
├── app.py                    # FastAPI app: routes, lifespan, middleware
├── environmental_data.py     # Core data pipeline — fetches & normalizes all 7 sources
├── derived_insights.py       # Physics-informed composite signals (heat index, sea state, ...)
├── rules_engine.py           # Config-driven alert evaluation
├── alert_rules.json          # Alert thresholds — tunable without a code change
├── locations.py / .json      # Registered multi-location coastal registry
├── notifications.py          # Optional Slack/Discord alert webhook
├── gdrive_backup.py          # Optional daily Google Drive history backup
├── utils.py                  # Shared helpers (dotted-path field resolution)
│
├── db_backend.py             # Storage backend selector (STORAGE_BACKEND env var)
├── storage.py                # SQLite backend (default)
├── mongo_storage.py          # MongoDB Atlas backend (recommended for durable history)
│
├── tests/                    # pytest suite — offline (mocked) + live-remote
├── scripts/                  # Standalone demo/PoC tools, not part of the app or test suite
│   ├── grounding_test.py             # Single-model grounded vs. ungrounded comparison
│   ├── multi_model_grounding_demo.py # Multi-model, multi-condition grounding demo
│   ├── stress_test.py                # 7-way failure-isolation + edge-case suite
│   └── nvidia_grounding_client.py    # Minimal NVIDIA NIM API usage example
│
├── docs/                     # Design docs and phase write-ups
├── render.yaml, Procfile     # Render deployment config
├── docker-compose.mongo.yml  # Local MongoDB for backend development
└── requirements*.txt         # Base + optional (mongo, gdrive) dependencies
```

---

## API reference

### `GET /environment`

Fetches the normalized, multi-domain environmental snapshot for any coordinates.

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `lat` | `float` | Yes | Latitude, `-90.0` to `90.0` |
| `lon` | `float` | Yes | Longitude, `-180.0` to `180.0` |
| `name` | `string` | No | Optional human-readable label |
| `timeout` | `float` | No | Per-source timeout in seconds (default `10.0`) |
| `bypass_cache` | `bool` | No | Force a fresh fetch, skipping the 5-minute cache |

<details>
<summary>Sample response</summary>

```json
{
  "location": { "name": "Chennai Coast", "lat": 13.08, "lon": 80.27 },
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
      "swell_wave_height_m": 0.60,
      "ocean_current_velocity_kmh": 1.1,
      "source": "open-meteo-marine",
      "status": "ok"
    },
    "air_quality": {
      "station_name": "Royapuram, Chennai - TNPCB",
      "pm25": 23.83,
      "pm10": 51.8,
      "aqi_category": "moderate",
      "source": "openaq",
      "status": "ok"
    },
    "sun_and_lighting": { "sunrise": "2026-09-03T00:26:46+00:00", "sunset": "2026-09-03T12:49:55+00:00", "status": "ok" },
    "terrain": { "elevation_m": 10.0, "coastal_risk_category": "elevated", "status": "ok" },
    "climate_baseline": { "solar_radiation_kwh_m2": 6.01, "avg_temperature_c": 30.82, "status": "ok" },
    "seismic_risk": { "recent_events_7d_count": 0, "hazard_level": "nominal", "status": "ok" }
  },
  "meta": {
    "confidence": "high — all sources responded successfully",
    "failed_sources": [],
    "total_latency_ms": 2652.44,
    "cache_hit": false,
    "derived_insights": { "heat_index_c": 34.9, "small_craft_risk_level": "none", "...": "..." },
    "trend_24h": null,
    "active_alerts": []
  }
}
```

*(`meta.derived_insights`, `meta.trend_24h`, and `meta.active_alerts` are Phase 2 additions — see below.)*
</details>

### `GET /environment/history`

Query persisted snapshot history for a location:

```
GET /environment/history?lat=13.08&lon=80.27&start=2026-09-01T00:00:00Z&end=2026-09-03T00:00:00Z&field=weather.temperature_c
```

### `GET /locations`

Lists every coastal point the service tracks for pre-warming, history ingestion, and `/alerts`. `/environment` still accepts any `lat`/`lon` — this registry is only what the scheduled jobs iterate over.

### `GET /alerts`

Evaluates the rules engine against every registered location (or a single `lat`/`lon`) and returns currently active alerts — see [Phase 2](#phase-2--history-trends--alerting) below for details.

### `GET /health`

Service health, active storage backend, and connectivity status.

---

## Phase 2 — History, Trends & Alerting

Phase 1 answers "what's happening right now, at one point." Phase 2 adds memory (what's changing), a network (more than one point), and judgment (proactively flagging what's worth attention) — without ML, new external data sources, or infrastructure beyond a database and a cron job.

### Physics-informed derived insights

Every `/environment` response includes `meta.derived_insights` — composite signals computed from the raw hyperparameters using cited, published physical standards, not a learned model:

| Field | Combines | Standard |
| :--- | :--- | :--- |
| `heat_index_c` / `heat_index_category` | Temperature + humidity | NOAA/Rothfusz heat index regression, with published low/high-humidity corrections |
| `dew_point_c` / `fog_risk` | Temperature + humidity + wind | Magnus-Tetens approximation |
| `beaufort_scale` | Wind speed | WMO-adopted Beaufort scale (force 0–12) |
| `imd_cyclone_category` | Sustained wind speed | India Meteorological Department official classification |
| `small_craft_risk_level` | Wave height + wind + gusts | NWS coastal marine warning tiers (Small Craft Advisory → Hurricane Force) |
| `storm_potential_score` / `_level` | Pressure + gusts + cloud cover + 3h pressure trend | Engineering heuristic (no single published index exists) |
| `rapid_pressure_fall` | 24h pressure change, latitude-normalized | Bergeron / Sanders-Gyakum (1980) rapid-cyclogenesis criterion |
| `air_stagnation_index` | Wind + precipitation + PM2.5 | Engineering heuristic |
| `coastal_flood_risk` | Elevation + wave height + wind + inverse-barometer surge | Inverse barometer effect (~1cm sea-level rise per 1hPa deficit) |
| `tsunami_advisory` | Seismic magnitude + depth + elevation | USGS shallow-focus (<70km) criterion |

Everything above is a real, cited, published standard except `storm_potential_score` and `air_stagnation_index`, which are documented engineering heuristics — no single standardized index exists for either. The rapid-pressure-fall criterion is borrowed from *extratropical* cyclogenesis and applied here only as a generic "pressure is falling unusually fast" signal at these tropical/subtropical latitudes, not a literal bombogenesis claim. Full citations and scope notes: [`derived_insights.py`](derived_insights.py).

### History, trends, and locations

- **`GET /environment/history`** — persisted snapshot history for a location, optionally narrowed to one dotted field.
- **`meta.trend_24h`** — a lightweight diff against the closest stored reading ~24h ago (`null` until enough history exists).
- **`GET /locations`** — the multi-location registry (Chennai, Visakhapatnam, Kochi, Mumbai, Kolkata/Sundarbans by default).
- Every fresh (non-cache-hit) `/environment` fetch is persisted in the background, and [`.github/workflows/ingest_history.yml`](.github/workflows/ingest_history.yml) hits every registered location hourly so history accumulates independent of organic traffic. Records older than 90 days are pruned automatically.

### `GET /alerts`

A config-driven rules engine ([`alert_rules.json`](alert_rules.json)) evaluates threshold and trend conditions over both raw and derived fields, against every registered location or a single `lat`/`lon`:

```json
{
  "generated_at": "2026-09-03T12:00:05Z",
  "locations_checked": 5,
  "active_alert_count": 1,
  "active_alerts": [
    {
      "id": "small_craft_unsafe",
      "severity": "high",
      "message": "Marine warning 'small_craft_advisory' in effect (wave 1.38m, wind 17.1km/h). Do not launch small or artisanal vessels.",
      "location": { "name": "Mumbai Coast", "lat": 18.94, "lon": 72.84 }
    }
  ]
}
```

Rules cover unhealthy PM2.5, unsafe sea state, strong sustained wind (Beaufort 6+) and gale-force gusts, heavy-rain flood risk, dangerous heat index, composite coastal-flood/storm-potential scores, IMD cyclonic-storm classification, seismic tsunami caution, air stagnation, and trend-based rules (rapid temperature spike, PM2.5 doubling, rapid pressure fall). Thresholds live entirely in `alert_rules.json` — tunable without a code change. Triggered alerts are deduped per rule/location on a 60-minute cooldown and logged for future reporting.

**Optional alert delivery**: set `ALERT_WEBHOOK_URL` to a Slack or Discord incoming-webhook URL and every newly-triggered alert is also pushed there. Fully inert if left unset.

### Storage backends

The history store is backend-agnostic — `storage.py` (SQLite, default) and `mongo_storage.py` (**recommended** for durable history: MongoDB Atlas's free tier, fully managed, no credit card) expose identical function signatures, selected via `STORAGE_BACKEND=sqlite|mongo` in `db_backend.py`. Both are verified against real running instances, not just mocks. Full setup and the reasoning behind the Mongo recommendation: [`docs/PHASE2_WALKTHROUGH.md`](docs/PHASE2_WALKTHROUGH.md).

Separately, `gdrive_backup.py` can push a daily JSON export of recent history to Google Drive as a disaster-recovery copy — a backup, not a live queryable store. It's inert unless `GDRIVE_ENABLED=true` is explicitly set.

**What's actually running where:** locally and by default, that's SQLite with Drive backup off. This project's own Render deployment has `STORAGE_BACKEND=mongo` set, so production runs on MongoDB Atlas — check your own `render.yaml` env vars if you're unsure which is live for your deployment.

A CouchDB backend (`couchdb_storage.py`) was also built and verified against a real instance, then archived — see [Archived backends](#archived-backends) below.

### Archived backends

A CouchDB REST-client backend was built alongside Mongo, run against a real local CouchDB 3.5 (via `docker-compose.couchdb.yml`), and verified end to end through `/environment`, `/environment/history`, and `/alerts` — including catching a real Mango query-sort bug mocks alone wouldn't have. It was then removed from `main` rather than left dormant: Mongo already covers everything it would (managed, free, no self-hosted server to run), so keeping two dormant durable backends around was clutter, not future-proofing.

Nothing was deleted — the full implementation, its tests, and the compose file live on the `archive/couchdb-backend` branch, and the reasoning/verification notes are still in [`docs/PHASE2_WALKTHROUGH.md`](docs/PHASE2_WALKTHROUGH.md) Part 4. `git checkout archive/couchdb-backend` to bring it back if CouchDB's offline-sync/multi-writer model ever becomes genuinely relevant (e.g. physical sensors syncing intermittently from boats) — until then, `db_backend.py` treats `STORAGE_BACKEND=couchdb` as an unrecognized value and safely falls back to SQLite instead of erroring.

### Explicitly out of scope (Phase 2)

No ML/forecasting, no new data sources beyond the existing 7, no user accounts or per-user subscriptions, no UI, no message-queue infrastructure. See [`docs/phase2-plan.md`](docs/phase2-plan.md) §7 for the rationale.

---

## Testing

### Offline unit & mocked integration suite (167 tests)

Boundary sanity checks, ISO-UTC normalization, coordinate validation, isolated failure degradation, the physics-informed derived insights, the rules engine (including a real monsoon-squall scenario and an explicit false-positive check on calm data), both storage backends, the locations registry, and every endpoint — no network calls. Runs automatically on every push via [`.github/workflows/tests.yml`](.github/workflows/tests.yml).

```bash
pytest tests/ --ignore=tests/test_live_remote.py -v
```

### Live remote deployment suite (4 tests)

Verifies the deployed service directly — connectivity, CORS, cache hits, 400 handling. Automatically skipped when the target is unreachable.

```bash
API_BASE_URL="https://confluence-si41.onrender.com" pytest tests/test_live_remote.py -v
```

### 7-way failure-isolation stress suite

Kills each upstream source independently to verify the other six still return cleanly.

```bash
python scripts/stress_test.py
```

---

## Deployment

This repository includes a pre-configured [`render.yaml`](render.yaml) and [`Procfile`](Procfile).

1. Fork or push this repository to GitHub.
2. In [Render](https://dashboard.render.com/), click **New** → **Blueprint** and select this repo.
3. Set `OPENAQ_API_KEY` (and optionally `NVIDIA_API_KEY`) in Render's environment settings.
4. Add your deployed URL to GitHub Secrets as `RENDER_APP_URL` to enable the keep-alive and hourly ingestion cron workflows.
5. Optional: set `ALERT_WEBHOOK_URL` for pushed alerts, or `STORAGE_BACKEND=mongo` + `MONGODB_URI` for durable history (see `render.yaml` comments).

---

## Limitations & production readiness

Documented honestly rather than oversold:

- **No authentication.** `/environment`, `/alerts`, and `/environment/history` are public and rate-limited but unauthenticated — a deliberate Phase 2 design choice (see [`docs/phase2-plan.md`](docs/phase2-plan.md) §7), fine for a public grounding API, not a fit if per-consumer quotas ever enter scope.
- **Single instance, no SLA.** A CI test gate runs on every push, but nothing pages anyone if the live deployment goes down beyond the existing keep-alive cron's own pass/fail signal — a dedicated monitor (UptimeRobot, Better Uptime) would need to be added separately.
- **Derived signals are correctly cited, not independently certified.** Most formulas are real published standards (see the table above), but nobody with domain authority (a meteorologist or oceanographer) has reviewed how they're combined here. Treat outputs as a strong, sourced first pass — not a certified safety authority — until reviewed by one.
- **Not wired into any AI platform.** Nothing here makes a frontier model call this API automatically; it has to be registered as a tool/function by whoever builds the agent that uses it. This is grounding infrastructure a developer plugs in, not a live integration today.
- **History durability depends on the storage backend.** SQLite on Render's free tier is wiped on redeploy (durable *between* restarts, not *across* deploys); MongoDB Atlas or an attached persistent disk fix this — see [`docs/PHASE2_WALKTHROUGH.md`](docs/PHASE2_WALKTHROUGH.md).

---

## Documentation

- [`docs/PHASE2_WALKTHROUGH.md`](docs/PHASE2_WALKTHROUGH.md) — history, trends, alerting, storage backends, and the hardening pass
- [`docs/phase2-plan.md`](docs/phase2-plan.md) — the Phase 2 design doc this was built from
- [`docs/phase1-planning-archive.md`](docs/phase1-planning-archive.md) — historical Phase 1 pilot specification
- [`scripts/multi_model_grounding_demo.py`](scripts/multi_model_grounding_demo.py) — frontier LLM grounding demonstration

---

## License

MIT License — see [`LICENSE`](LICENSE).
