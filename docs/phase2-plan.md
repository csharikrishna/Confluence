# Confluence — Phase 2 Documentation
### History & Trends → Multi-Location → Alerting/Reasoning Layer

---

## 1. What Phase 2 Is

Phase 1 proved the core thesis: a single unified endpoint, grounded in 7 real data sources, meaningfully improves how frontier models reason about coastal conditions — for **one location, one moment in time**.

Phase 2 removes both of those limits:

1. **Time** — instead of only ever answering "what's happening right now," the system starts remembering what happened before, so it can answer "what's changing."
2. **Space** — instead of only Chennai, the system generalizes to any number of coastal points using the exact same pipeline.
3. **Judgment** — instead of only reporting data, the system starts *noticing* when something crosses a threshold worth flagging, and says so without being asked.

**In one sentence:** Phase 1 built a sensor. Phase 2 turns it into a memory + a network + a watchdog.

---

## 2. Why This Order (Dependency Logic)

Even though all three sub-phases are being built together, they are not independent — there's a real dependency chain:

```
2A: History & Trends  (foundation — nothing else works well without this)
        ↓
2B: Multi-Location     (can happen in parallel with 2A — same schema, more points)
        ↓
2C: Alerting Layer      (depends on 2A — you can't detect "change" without stored history)
```

**Why 2A comes first, conceptually:** an alert like *"wind speed jumped 15 km/h in the last hour"* is impossible without a stored previous reading. Building 2C before 2A would force it to fall back to dumb static thresholds only (e.g. "PM2.5 > 150") instead of the more interesting trend-based logic (e.g. "PM2.5 doubled in 3 hours"). So even though you're doing all three, **2A should be functionally complete before 2C is tested**, even if the code is scaffolded in parallel.

2B (multi-location) is architecturally independent of both — it's really just "stop hardcoding Chennai," so it can be built any time without blocking or being blocked by the others.

---

## 3. Sub-Phase 2A: History & Trends

### What it does
Instead of fetching-and-discarding data on every request, the system now **persists every snapshot** it generates, so past conditions can be queried and compared against current ones.

### New components
- **A time-series store.** Start simple — SQLite is enough for Phase 2 (no need for TimescaleDB/InfluxDB yet, that's a later-scale problem). One table: `snapshots(id, lat, lon, timestamp, raw_json)`.
- **A scheduled ingestion job.** Reuse the existing GitHub Actions keep-alive cron pattern — instead of (or in addition to) just pinging `/health`, have it call `/environment` for each tracked location every N minutes (start with hourly) and persist the result.
- **A new endpoint: `GET /environment/history`** — accepts `lat`, `lon`, `start`, `end`, and optionally `field` (e.g. `weather.temperature_c`), returns the stored time series for that range.
- **A trend summary field** on the existing `/environment` response — e.g. `meta.trend_24h: { "temperature_c": "+2.1", "pm25": "-8.4" }` — a lightweight diff against the same location's reading from ~24h ago, computed on read.

### Schema addition (draft)
```json
"meta": {
  "confidence": "...",
  "trend_24h": {
    "temperature_c": { "current": 31.9, "previous": 29.8, "change": "+2.1" },
    "pm25": { "current": 23.8, "previous": 32.2, "change": "-8.4" }
  }
}
```

### What "done" looks like
- [ ] Snapshots are being persisted on a schedule, not just fetched live
- [ ] `/environment/history` returns real stored data for a time range
- [ ] `/environment`'s live response includes a trend field computed from stored history
- [ ] Old/stale data doesn't grow unbounded — decide a retention policy (e.g. keep 90 days, or keep hourly for 7 days + daily rollups beyond that) even if you don't fully implement rollups yet

---

## 4. Sub-Phase 2B: Multi-Location

### What it does
Generalizes the pipeline from "hardcoded for Chennai" to "works for any registered coastal point," without changing the core fetch/normalize logic at all — the 4-source-turned-7-source pipeline already takes `lat`/`lon` as parameters, so this is mostly about **removing assumptions**, not adding new code paths.

### New components
- **A locations registry.** A simple static list to start (JSON file or a `locations` table) — e.g. Chennai, Visakhapatnam, Kochi, Mumbai, Kolkata. Each entry: `name`, `lat`, `lon`, `region`.
- **A new endpoint: `GET /locations`** — lists all registered points, so a consumer (or an LLM) can discover what's available without guessing coordinates.
- **Update the pre-warm/cache-warming logic** (currently Chennai-only in `app.py`'s startup lifespan) to loop over all registered locations instead of one hardcoded point.
- **Update the scheduled ingestion job from 2A** to loop over all registered locations too — history should be collected for every tracked point, not just one.

### What "done" looks like
- [ ] `/locations` returns a real list, not just Chennai
- [ ] `/environment?lat=X&lon=Y` works correctly for at least 3 more real coastal points, sanity-checked manually
- [ ] Startup pre-warming and the history-collection cron both loop over the full registry, not a hardcoded point
- [ ] Confirm OpenAQ gracefully returns "no station" for locations without nearby ground sensors (some of your new points might not have one) — this should already work from Phase 1's error handling, just needs re-verifying against real new coordinates

---

## 5. Sub-Phase 2C: Alerting / Reasoning Layer

### What it does
This is the "brain" from the very first architecture document — the system stops being purely reactive (only responding when asked) and starts proactively flagging conditions worth attention.

### New components
- **A rules engine** — start simple, not ML-based. A config-driven set of thresholds and trend conditions per domain, e.g.:
  - `pm25 > 150` → "Unhealthy air quality"
  - `wave_height_m > 2.0` → "Unsafe for small craft"
  - `temperature_c change > +5 in 3h` → "Rapid heat spike" (this one needs 2A's history to work)
  - `wind_speed_kmh > 40` → "Storm-level wind"
- **A new endpoint: `GET /alerts`** — returns any currently active alerts across all registered locations (from 2B), each with the triggering condition, severity, and the raw data that caused it.
- **A delivery mechanism** — simplest version: alerts are just visible via the `/alerts` endpoint. Optional stretch: push to a Slack/Discord webhook or email when a new alert fires, using the same GitHub Actions cron that's already checking on a schedule.
- **Alert history/logging** — store triggered alerts (reuse the same DB from 2A) so you can later show "this alert fired 3 times this month," which is useful proof for any future NGO/decision-maker pitch.

### What "done" looks like
- [ ] Rules engine correctly evaluates the 7-source snapshot and flags real conditions (test with the Day 2 monsoon-squall data from Phase 1 — it should clearly trigger a "do not fish" style alert)
- [ ] `/alerts` returns structured, real alerts — test against at least one location with an actual current alert-worthy condition (may require waiting for real weather, or briefly lowering a threshold to force one during testing)
- [ ] False positives are checked — run the rules against a full week of calm, unremarkable data (once 2A has been running a few days) and confirm nothing fires when nothing should
- [ ] Thresholds are stored in a config file, not hardcoded inline, so they can be tuned without a code change

---

## 6. Updated Unified Schema (Phase 2 target state)

```json
{
  "location": { "name": "Chennai Coast", "lat": 13.08, "lon": 80.27 },
  "generated_at": "2026-09-10T10:00:00Z",
  "data": { "...same 7 domains as Phase 1..." },
  "meta": {
    "confidence": "high",
    "failed_sources": [],
    "trend_24h": {
      "temperature_c": { "current": 31.9, "previous": 29.8, "change": "+2.1" }
    },
    "active_alerts": [
      {
        "rule": "pm25_unhealthy",
        "severity": "high",
        "message": "PM2.5 at 168 µg/m³ — Very Unhealthy",
        "triggered_at": "2026-09-10T09:15:00Z"
      }
    ]
  }
}
```

---

## 7. Explicitly Out of Scope (Still, Even Now)

To avoid the same drift that happened with the 4→7 source expansion in Phase 1, Phase 2 explicitly does **not** include:

- No ML/predictive modeling — alerting is rule-based threshold/trend logic only, not forecasting
- No new external data sources beyond the existing 7 — this phase is about doing more with what you have, not adding more inputs
- No user accounts, auth, or personalized alert subscriptions — `/alerts` is a public read endpoint, not a notification system with per-user preferences
- No mobile app / dashboard UI — still API-only; a UI is a Phase 3 problem if it happens at all
- No real message-queue/event infra (Kafka, etc.) — a simple scheduled cron + database is enough at this scale

If any of these feel necessary mid-build, that's a signal to stop and write a Phase 3 doc — not to quietly fold it into Phase 2.

---

## 8. Suggested Build Order for Your Agent

1. Set up the SQLite store + snapshot persistence (2A foundation)
2. Build the scheduled ingestion cron for Chennai only (prove it works end-to-end before scaling out)
3. Add `/environment/history` and the `trend_24h` field
4. Add the locations registry + `/locations` endpoint (2B)
5. Extend the cron and pre-warming to loop over all registered locations
6. Build the rules engine + `/alerts` endpoint (2C), using the Phase 1 Day 1/2/3 test data as known-good test cases
7. Re-run the full Phase 1 stress-test suite (kill-each-source, timeouts, invalid coords) against the new endpoints to confirm nothing regressed
8. Update `README.md` to reflect the new endpoints, exactly like the Phase 1 → deployment cleanup did

---

## 9. What "Phase 2 Done" Looks Like, Overall

- [ ] History is being collected automatically, not just live-fetched
- [ ] At least 4-5 locations are fully supported end-to-end
- [ ] Alerts fire correctly on real or simulated threshold-crossing conditions, with zero false positives on calm data
- [ ] All new endpoints are documented in README with live examples, same standard as Phase 1
- [ ] Old Phase 1 tests still pass — Phase 2 shouldn't break Phase 1
