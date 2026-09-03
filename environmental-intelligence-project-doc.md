# Project: Unified Environmental Intelligence Endpoint
### Phase 1 Documentation — Single Location Pilot

---

## 1. What We're Building

A single API endpoint that:

1. Pulls live data from 3–4 free environmental sources for **one target location**
2. Normalizes it into one consistent schema (units, timestamps, coordinates)
3. Serves it back as **one clean JSON response** — instead of an LLM (or any app) having to call 4 different APIs, learn 4 different formats, and handle 4 different failure modes

**In one sentence:** we are building the data layer that any AI model — ChatGPT, Claude, Gemini, or a custom agent — can call once to get trustworthy, structured, real-time environmental context for a place, instead of hallucinating it or juggling raw APIs itself.

This is *not* a chatbot. It's infrastructure a chatbot (or anything else) sits on top of.

---

## 2. Why This Matters (The Actual Value)

Right now, if you ask any frontier model "what's the ocean and air condition near Chennai right now," it either:
- Makes something up (no live data access), or
- Needs to be wired to 4+ separate tools/APIs itself, each with different auth, formats, and rate limits

**Our endpoint removes that burden.** One call → one normalized answer, with source and freshness attached. This is the same problem OceanAI (a recent research project) solved for ocean-only NOAA data — we're doing it across ocean + weather + air quality + solar/climate, for a region that's currently underserved (Indian coastline vs. the mostly US-NOAA-focused tools that exist today).

**Who this helps, concretely:**
- AI apps/agents that need grounded environmental facts instead of hallucinated ones
- Coastal risk tools (fisheries, small NGOs, local governments) that can't afford to build this themselves
- Us — as a portfolio-proving foundation before we build the reasoning/alerting layer on top

---

## 3. Target Location (Pilot)

**Default: Chennai coastline, Tamil Nadu (13.08°N, 80.27°E)**

Chosen because:
- Coastal — relevant to ocean + weather + air quality all at once
- Well-covered by all four candidate data sources
- Near enough to home region to sanity-check results manually
- Large enough population/fishing/port activity to matter later

*(Easy to swap — the whole system should be built parameterized by lat/lon from day one, not hardcoded to Chennai.)*

---

## 4. The 4 Endpoints (Phase 1 Sources)

All chosen because they are **free, require no paid tier, and are stable enough to build on.**

| # | Source | What it gives us | Auth | Notes |
|---|--------|-------------------|------|-------|
| 1 | **Open-Meteo — Weather API** | Temperature, wind speed/direction, humidity, pressure, precipitation (current + forecast) | None | No key, no rate limit for our scale |
| 2 | **Open-Meteo — Marine API** | Wave height, wave period, sea surface temperature, swell direction | None | Same provider, same simplicity |
| 3 | **OpenAQ API** | Air quality — PM2.5, PM10, O3, NO2, SO2, CO | Free API key | Ground-station based, global coverage, well documented |
| 4 | **NASA POWER API** | Solar radiation, longer-term meteorological/climate context at any lat/lon | None | Good for baseline/historical comparison, not just live snapshot |

**Why these four:** together they cover ocean state, atmosphere state, pollution state, and a climate baseline — the minimum set needed to start noticing *interconnection* (e.g., wind shift + SST drop + pressure change happening together), which was the original motivating idea.

---

## 5. Unified Response Schema (Draft v0)

Every source gets mapped into this shape before it leaves our endpoint:

```json
{
  "location": {
    "name": "Chennai Coast",
    "lat": 13.08,
    "lon": 80.27
  },
  "generated_at": "2026-09-03T10:00:00Z",
  "data": {
    "weather": {
      "temperature_c": 31.2,
      "wind_speed_kmh": 18.4,
      "wind_direction_deg": 210,
      "humidity_pct": 74,
      "pressure_hpa": 1008,
      "source": "open-meteo",
      "observed_at": "2026-09-03T09:45:00Z"
    },
    "marine": {
      "sea_surface_temp_c": 29.8,
      "wave_height_m": 1.1,
      "wave_period_s": 6.2,
      "source": "open-meteo-marine",
      "observed_at": "2026-09-03T09:00:00Z"
    },
    "air_quality": {
      "pm25": 42,
      "pm10": 68,
      "o3": 21,
      "no2": 14,
      "aqi_category": "moderate",
      "source": "openaq",
      "observed_at": "2026-09-03T08:00:00Z"
    },
    "climate_baseline": {
      "solar_radiation_kwh_m2": 5.4,
      "source": "nasa-power",
      "observed_at": "2026-09-02T00:00:00Z"
    }
  },
  "meta": {
    "freshness_warning": "climate_baseline data is >24h old",
    "confidence": "high — all sources responded successfully"
  }
}
```

**Key design decisions:**
- Every field carries its own `source` and `observed_at` — no silent mixing of stale and live data
- A top-level `meta.freshness_warning` flags anything that isn't truly real-time (this was the "scientifically honest" principle from earlier — we don't pretend near-real-time is real-time)
- This is the *only* shape an LLM or app ever needs to understand, regardless of how many sources we add later

---

## 6. Architecture (Phase 1 Scope Only)

```
[ 4 External APIs ]
        ↓
[ Fetch Layer ]  (one small function per API, handles retries/failures)
        ↓
[ Normalization Layer ]  (maps each source into the unified schema above)
        ↓
[ Single Unified Endpoint ]  →  GET /environment?lat=13.08&lon=80.27
        ↓
[ Consumer ]  (a frontier model, our own chatbot later, or anyone else)
```

No database yet. No RAG yet. No LLM reasoning yet.
**Phase 1 is: can we reliably produce one trustworthy JSON blob for one location, from 4 live sources, on demand?**

Everything from the original full architecture (storage layers, vector DB, alerting, multi-region) comes *after* this works.

---

## 7. What "Done" Looks Like for Phase 1

- [x] One working script/endpoint that takes `lat, lon` and returns the unified JSON
- [x] All 4 sources successfully fetched and mapped to the schema
- [x] Graceful handling when one source fails (return partial data + note the gap, don't crash)
- [x] Manually verified against real-world values for Chennai (sanity check: does the SST/wind/AQI look plausible right now?)
- [x] Endpoint tested by literally pasting its output into a frontier model prompt and asking an environmental question about Chennai — does it answer better/more accurately than without it?

That last test is the actual proof of concept for the whole "single endpoint for frontier models" idea.
- **Validation Run**: Conducted on 2026-09-03 using `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` (documented in `model_grounding_comparison.json`). Results confirmed that without the endpoint, the model hallucinated heavy monsoon rain (30-70mm) and high humidity (75-85%), whereas with the endpoint data it grounded on true conditions (35.4°C, 47% humidity, 0.0mm rain, 0.76m wave, moderate AQI) providing accurate operational advisories for fishermen and outdoor workers.

---

## 8. Explicitly Out of Scope (For Now)

To avoid scope creep back into the "everything" trap:

- No storage/database (fetch live every time for now)
- No additional regions (Chennai only)
- No additional data sources beyond the 4 listed
- No chatbot UI
- No alerting/push notifications
- No RAG or vector search

These all come in Phase 2+, only after Phase 1 is proven to work and actually useful.

---

## 9. Status & Delivery: Phase 1 Fully Closed

- [x] **Core Concurrency Fix**: Re-architected fetch execution using `concurrent.futures.ThreadPoolExecutor(max_workers=4)`. Wall-clock latency dropped from sequential sum (~6.0s) to **2.6s** (matching the single slowest upstream source, OpenAQ).
- [x] **Production Callable Endpoint ([app.py](file:///c:/Users/cshar/Desktop/Confluence/app.py))**: Production-ready FastAPI application exposing:
  - `GET /environment?lat=13.08&lon=80.27&name=Chennai%20Coast`
  - `GET /health`
  - `GET /docs` (Interactive OpenAPI Swagger UI)
- [x] **Full Pytest Suite**: 18 automated unit and integration tests in `tests/` covering input validation, canonical UTC timestamps, boundary sanity checks, landlocked points, and mocked partial failure handling with 100% pass rate.
- [x] **Multi-Condition & Multi-Model Frontier Grounding**: Demonstrated across 3 environmental regimes (heat spike, active monsoon squall, winter pollution surge) and 2 model families (`nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` and `meta/llama-3.2-11b-vision-instruct`).

### Ready for Phase 2:
With Phase 1 proven and wrapped as a high-performance callable API, the foundation is set for Phase 2 (historical caching, multi-region coordinates, and reasoning/alerting agents).
