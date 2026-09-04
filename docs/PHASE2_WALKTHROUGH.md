# Phase 2 Walkthrough

This documents two passes of work: building Phase 2 (history, trends, multi-location, alerting) per [docs/phase2-plan.md](phase2-plan.md), then a hardening pass aimed at closing the gaps between "solid portfolio project" and "production-credible service." It also lists, explicitly, what could not be done from inside this environment — things that need your action outside the code.

---

## Part 1 — Phase 2 build (2A / 2B / 2C)

### 2A: History & Trends
- **`storage.py`** — SQLite store. Two tables: `snapshots` (every fresh fetch, persisted in the background) and `alerts_log` (triggered alerts, deduped per rule/location on a 60-minute cooldown). 90-day retention pruning runs at startup.
- **`GET /environment/history`** — query stored readings for a location by time range, optionally narrowed to one dotted field (`weather.temperature_c`).
- **`meta.trend_24h`** on `/environment` — diffs the current reading against the closest stored snapshot ~24h ago. Returns `null` until enough history has accumulated for that location.

### 2B: Multi-Location
- **`locations.py` / `locations.json`** — a 5-point registry (Chennai, Visakhapatnam, Kochi, Mumbai, Kolkata/Sundarbans). `GET /locations` exposes it.
- Startup pre-warming and the hourly ingestion cron both loop over the full registry now, not a hardcoded Chennai.
- `/environment` still accepts any `lat`/`lon` — the registry is only what the scheduled jobs iterate over.

### 2C: Alerting / Reasoning Layer
- **`derived_insights.py`** — the physics layer: raw hyperparameters combined via established formulas (NOAA heat index regression, Magnus-Tetens dew point) and documented threshold logic (sea-state risk, storm potential, air stagnation, coastal flood risk, tsunami advisory). No ML, per the plan's explicit scope.
- **`rules_engine.py` + `alert_rules.json`** — config-driven threshold and trend rules. Thresholds are data, not code — tunable by editing the JSON file.
- **`GET /alerts`** — evaluates every registered location (or a single `lat`/`lon`) concurrently and returns active alerts.
- **`.github/workflows/ingest_history.yml`** — hourly cron that reads the live `/locations` registry and calls `/environment?bypass_cache=true` for each point, so history accumulates independent of organic traffic.

### Verification
- 101 offline tests written and passing at this point (Day-2 monsoon-squall fixture correctly triggers `small_craft_unsafe` / `strong_sustained_wind` (renamed from `storm_level_wind` in a later audit pass — 40km/h is Beaufort force 6, not storm-force) / `heavy_rain_flood_risk`; a calm-data fixture correctly triggers nothing).
- Re-ran the original Phase 1 7-way stress suite — still 100% pass, confirming no regression.
- Started the actual dev server and hit every endpoint against **live** upstream data (not mocks). `/alerts` caught genuinely current conditions during testing — Mumbai's real PM2.5 (78 µg/m³) and real sea state (1.38m) both correctly flagged.

---

## Part 2 — Hardening pass ("closing the gap toward 10/10")

You asked directly whether this felt production-credible. The honest gaps were: no CI gate, a CORS misconfiguration, no persistent-history story, no delivery mechanism for alerts beyond polling, no DB health visibility, and floating dependency versions. Here's what changed:

| Gap | Fix | File(s) |
| :--- | :--- | :--- |
| No CI enforcing tests | Added a GitHub Actions workflow that runs the full offline suite on every push/PR to `main` | `.github/workflows/tests.yml` |
| CORS misconfiguration | `allow_credentials` was `True` alongside `allow_origins=["*"]` — Starlette's CORSMiddleware reflects the caller's Origin instead of literally sending `*` when credentials are on. This API has no cookies/sessions, so credentials should never have been `True`. Fixed to `False`; verified via a live preflight request that `Access-Control-Allow-Origin: *` is now sent literally with no credentials header. | `app.py` |
| Alerts only visible by polling `/alerts` | Added an **optional** Slack/Discord webhook (`ALERT_WEBHOOK_URL`) — the Phase 2C "stretch goal" from the plan doc. Payload includes both `text` and `content` keys so one URL works for either service. Fully inert if unset; delivery failures are logged and swallowed, never raised. Only fires on newly-logged (non-duplicate) alerts. | `notifications.py` |
| No DB observability | `/health` now runs a real `SELECT 1` against the SQLite store and reports `history_store_status: connected/unreachable`, plus whether the alert webhook is configured. `status` degrades to `"degraded"` if the DB is unreachable. | `storage.py`, `app.py` |
| No path to durable history | `render.yaml` documents (commented out, not active) how to attach a Render persistent disk and point `CONFLUENCE_DB_PATH` at it. Left inactive deliberately — see "what I could not do" below. | `render.yaml`, `.env.example` |
| Floating dependency versions | Pinned every dependency to the exact version actually tested (`~=` compatible-release pins), added Dependabot config so updates arrive as reviewable PRs gated by the new CI workflow instead of drifting silently. | `requirements.txt`, `.github/dependabot.yml` |
| Threshold/formula credibility | Documented explicitly in the README which formulas are standard published science (heat index, dew point) vs. engineering judgment calls (small-craft/storm-potential/flood band cutoffs) — see the new "Limitations & Production Readiness" section. | `README.md` |

### New tests added in this pass
- `tests/test_notifications.py` — webhook no-ops when unconfigured, posts the combined payload when configured, swallows delivery failures, and only fires on newly-logged (not deduped) alerts.
- `tests/test_storage.py` gained `is_healthy()` coverage (valid DB → `True`, unwritable path → `False`).
- `tests/test_api.py`'s health check test now asserts the new `history_store_status`, `alert_webhook`, and `phase` fields.
- **Result: 108/108 offline tests pass.** Re-verified live against the running dev server (health check, CORS preflight) after every change.

---

## Part 3 — What I could not do (needs your action)

Everything above is code/config I could write, test, and verify myself. These require credentials, billing, external accounts, or judgment calls I don't have access to or standing to make:

1. **Durable storage still needs a real server behind it.** Two free-of-charge paths exist and both are code-ready: attach a Render persistent disk (needs a paid Render plan — deliberately commented out in `render.yaml`), or run CouchDB yourself (needs an actual CouchDB server reachable from the app — see Part 4). Either way, something outside this codebase has to actually run.
2. **Create the Slack/Discord webhook itself.** I built and tested the delivery code, but generating an actual webhook URL requires access to your Slack workspace or Discord server. Create one, then set `ALERT_WEBHOOK_URL`.
3. **Set `RENDER_APP_URL` as a GitHub secret.** Both cron workflows (`keep_alive.yml`, `ingest_history.yml`) read this secret; I can write the workflow YAML but can't create repository secrets myself.
4. **External uptime monitoring.** Nothing currently pages anyone if the live service goes down beyond the existing `keep_alive.yml` cron's own pass/fail status (see Part 4's analysis of this). A dedicated monitor is still a third-party account I can't create for you.
5. **Domain-expert sign-off, even after the science upgrade in Part 4.** The formulas are now correctly cited to real published standards (NOAA, WMO, IMD, NWS, USGS) rather than invented — but nobody with actual meteorological/oceanographic authority has reviewed how they're combined here. If this is ever pitched to fishermen, an NGO, or a coastal-safety org, get a real domain expert to review `derived_insights.py` and `alert_rules.json` before anyone relies on it operationally.
6. **Registering this as a callable tool in any AI platform.** You mentioned you already have an NVIDIA 30B model API key for this testing phase (matching the existing `scripts/nvidia_grounding_client.py` / `scripts/grounding_test.py` PoC scripts in the repo) with Gemini or another provider planned once that's validated — that's a reasonable path and entirely yours to drive. Nothing about this build makes any frontier model call the API automatically on its own; whichever provider you wire in has to be given this API as a registered tool/function.
7. **Running CouchDB in production, and creating Google Cloud credentials.** Update: once Docker was available, I did run CouchDB locally (via `docker-compose.couchdb.yml`) and verified the client against it for real — see Part 4. What's still on you: hosting it somewhere reachable in production (an Oracle Cloud VM or similar), using a real (non-placeholder) password, and creating the Google Cloud service account for Drive backup — I have no cloud accounts of my own to provision either of those.
8. **Load/scale testing under real traffic.** The 7-way stress suite tests upstream failure isolation, not concurrent-user load. If this ever gets real traffic volume, that's a separate exercise (e.g. `locust`, already in your installed packages) I haven't run.
9. **Any billing or paid-plan decisions** (Render tier upgrade, a custom domain, etc.) — these are account/cost decisions that are yours to make, not mine to execute.

---

## Part 4 — Science upgrade, pluggable storage, and CouchDB/Drive wiring

A follow-up pass, in response to three asks: push the alert science as far as published standards actually go, stop assuming a third-party uptime monitor is the only option, and prepare (without running) a CouchDB + Google Drive storage path.

### Alert science upgrade
Previously several `derived_insights.py` bands (small-craft risk, storm potential) were reasonable but self-invented threshold cutoffs. Rewritten to cite real, checkable standards wherever one exists:

- **`beaufort_scale`** — the WMO-adopted Beaufort wind force scale (0-12), universal reference.
- **`imd_cyclone_category`** — India Meteorological Department's official low-pressure-system classification (Depression → Super Cyclonic Storm), the actual authority for these coastal locations.
- **`small_craft_risk_level`** — rewritten from ad-hoc bands to the real NWS coastal marine warning tiers (Small Craft Advisory / Gale Warning / Storm Warning / Hurricane Force Wind Warning), with the wind-speed cutoffs converted directly from NWS's published knot ranges.
- **`rapid_pressure_fall`** — a new signal using the Bergeron/Sanders-Gyakum (1980) latitude-normalized rapid-cyclogenesis formula, powered by the 24h pressure history already being collected. Honestly scoped in the docstring: that formula describes *extratropical* cyclogenesis, so at these tropical/subtropical latitudes it's surfaced as a generic "pressure is falling unusually fast" signal, not a literal bombogenesis claim.
- **`coastal_flood_risk`** — now computes an explicit inverse-barometer sea-level contribution (~1cm per 1hPa pressure deficit, a real oceanographic relationship) instead of a flat threshold bump.
- **`tsunami_advisory`** — now also checks earthquake depth (USGS already returns this; `fetch_seismic_risk` was extended to capture it) and requires a shallow-focus event (<70km, USGS's own definition) — deep-focus quakes rarely produce significant surface tsunamis at the same magnitude, so a same-magnitude deep event no longer triggers the advisory.

`storm_potential_score` and `air_stagnation_index` remain engineering heuristics — I'm not aware of a single standardized published index for either, so pretending otherwise would be dishonest rather than rigorous. The README's derived-insights table now marks exactly which fields are cited standards vs. judgment calls.

### Uptime monitoring, reconsidered
Rather than assuming a paid/third-party monitor is required: `.github/workflows/keep_alive.yml` already pings `/health` every 12 minutes and `exit 1`s on a non-200 response. A failing scheduled GitHub Action already triggers GitHub's own default email notification to the repo's watchers — this is a real, zero-setup uptime signal that was already running and just wasn't being framed as one. A dedicated third-party monitor (UptimeRobot etc.) still gives better guarantees (independent of GitHub Actions' own uptime, configurable paging channels), so it's still worth adding if you want that — but it's not the only free option, and the cheapest one requires nothing new from you.

### Pluggable storage backend (CouchDB-ready, not CouchDB-running)
Built a backend-selector so `storage.py` (SQLite, still the default) and a new `couchdb_storage.py` (CouchDB REST client) expose the *identical* function signatures, and `db_backend.py` picks between them via `STORAGE_BACKEND=sqlite|couchdb`. `app.py` and `notifications.py` both import through `db_backend`, so there's one single place deciding which backend is live — no risk of one module writing to SQLite while another reads from CouchDB.

**Important correction on the original ask:** the downloaded `apache-couchdb-3.5.2.tar.gz` is CouchDB's *source release* (an Erlang/OTP build tree — `Makefile`, `rel/reltool.config`, native `.cmd`/`.in` templates), not a runnable binary, and there's no meaningful sense in which its "main components" can be pulled into this Python repo — CouchDB is a separate compiled server process, not a library. The correct pattern (and the only one that works) is what got built: this app talks to a running CouchDB server over HTTP, exactly like any other database client.

**What you need to actually do to flip this on:**
1. Run CouchDB somewhere reachable — the official `couchdb` Docker image is the realistic path (the source tarball needs Erlang/OTP, a C compiler, ICU, and a JS engine to build; Docker sidesteps all of that). An Oracle Cloud Always Free VM (genuinely free forever) is a reasonable place to run that container long-term.
2. Set `STORAGE_BACKEND=couchdb`, `COUCHDB_URL`, `COUCHDB_USER`, `COUCHDB_PASSWORD` as env vars.
3. That's it — `couchdb_storage.py` creates its own databases and Mango indexes on startup (`init_db()`), mirroring exactly what `storage.py` does for SQLite.

**Update — this is now verified against a real running instance, not just mocks.** Once Docker was available, `docker-compose.couchdb.yml` (committed) was used to run actual CouchDB 3.5 locally, and every function in `couchdb_storage.py` was exercised against it for real, then the full FastAPI app was run with `STORAGE_BACKEND=couchdb` and driven through `/environment`, `/environment/history`, and `/alerts` end to end — confirmed snapshots and alerts land as real documents in CouchDB (checked via raw `_all_docs`/db-info calls), not just that the code doesn't crash.

This caught one real bug the mocked tests couldn't: `get_alert_history` passed `sort=[{"triggered_at": "desc"}]` to Mango's `_find`, which CouchDB rejects with `no_usable_index` unless an index exists matching that exact selector+sort shape — the existing `(lat, lon, rule_id, triggered_at)` index doesn't satisfy a sort on `triggered_at` alone. Fixed by dropping the Mango-level sort and sorting the (small) result set in Python instead, matching the pattern already used in `get_reading_hours_ago`. Regression tests were added (`tests/test_couchdb_storage.py::TestGetAlertHistory`) asserting `sort` is never passed to `_find` for this query, so this can't silently regress.

Reproduce this yourself: `docker compose -f docker-compose.couchdb.yml up -d`, then set `STORAGE_BACKEND=couchdb` and the `COUCHDB_*` env vars from `.env.example` before running the app.

**Status: kept dormant, not the recommended path.** After building this, Oracle Cloud's Always Free tier turned out to require a billing account (a credit card on file) before it would even provision the free VM — real friction for a project whose entire premise is staying free, and a legitimate reason to not use it. This code stays in the repo (fully tested, verified against a real instance) in case that changes or it's useful for something else later, but MongoDB Atlas (below) is the actual recommended durable-storage path now.

### MongoDB Atlas (recommended durable storage — replaces the CouchDB plan)

Reconsidered from scratch once the CouchDB-on-Oracle plan hit the billing-account wall: the actual requirement was never "run a CouchDB server," it was "durable history across Render redeploys, and it must stay free." A *managed* database satisfies that without needing you to run, patch, or host anything at all.

**Why MongoDB Atlas over Firebase Firestore (the other option considered):** both have genuinely free tiers with no credit card required (verified via live search before recommending either, given "must be free" is the whole point) — but Firestore has the same rigid "query must match an existing composite index or it's rejected" behavior that just caused the real CouchDB bug above, while MongoDB's queries degrade to a slower collection scan instead of failing outright. Firestore's one edge — reusing the same Google Cloud credential already being set up for Drive backup — wasn't enough to outweigh repeating a bug class we'd just fixed.

**Architecture:** `mongo_storage.py` is a third backend alongside `storage.py` (SQLite) and `couchdb_storage.py`, added to `db_backend.py`'s selector (`STORAGE_BACKEND=mongo`). Same function-signature-parity approach as CouchDB. One real difference: MongoDB Atlas retired its plain-HTTPS Data API in September 2025 (confirmed via search — it's fully shut down), so unlike the CouchDB client, this can't be a dependency-free `requests`-based REST client. It uses the official `pymongo` driver instead, added as an *optional* extra (`requirements-mongo.txt`), imported lazily so the base app still runs without it unless `STORAGE_BACKEND=mongo` is actually selected.

**Verified against a real server, same rigor as CouchDB.** A local MongoDB was needed to test against — Docker Desktop was already asked to pull `mongo:7` (`docker-compose.mongo.yml`, committed), but it turned out a native `mongod` was already running locally on port 27017 from an unrelated project. Used that directly instead (isolated to its own `confluence_verify_test` database — the pre-existing databases were never touched, confirmed by listing them before and after). Every function in `mongo_storage.py` was exercised for real, then the full FastAPI app was run with `STORAGE_BACKEND=mongo` and driven through `/environment`, `/environment/history`, and `/alerts` end to end.

This did catch one real bug, smaller than the CouchDB one but still something mocks wouldn't have shown: `/health`'s `history_store` field displayed `"mongodb@mongodb:"` instead of `"mongodb@localhost:27017"`. The credential-masking parser did naive string-splitting on `@` and `/` assuming a `user:pass@host` shape; against a URI with no embedded credentials (`mongodb://localhost:27017`), it mistook the `mongodb://` scheme prefix itself for the host. Fixed by switching to `urllib.parse.urlparse` (handles both `mongodb://` and `mongodb+srv://` correctly, and `.hostname` already excludes credentials) — verified live afterward that it now shows the real host. A regression test covers this exact no-credentials case.

No CRUD/query bugs were found — MongoDB's forgiving query behavior meant every function worked on the first real attempt, unlike CouchDB's Mango sort restriction.

**What you need to do:** create a free MongoDB Atlas account (cloud.mongodb.com — no card needed) and an M0 cluster, get its connection string (Database → Connect → Drivers), set `MONGODB_URI` (and `STORAGE_BACKEND=mongo`), and on Render change the build command to `pip install -r requirements.txt -r requirements-mongo.txt` (see the comment in `render.yaml`). That's it — `init_db()` creates its own indexes on first run.

### Google Drive backup (disaster recovery, not a live database)
`gdrive_backup.py` uploads a periodic JSON export of recent history to a Drive folder — a point-in-time backup copy, not a queryable live store (Drive isn't designed for that; CouchDB/SQLite remain what the app actually reads and writes). Wired into `app.py`'s lifespan as a daily background task, fully inert unless `GDRIVE_ENABLED=true` and credentials are set. The `google-api-python-client`/`google-auth` libraries are optional (`requirements-gdrive.txt`) and imported lazily, so the base app runs fine without them.

**What you need to do:** create a Google Cloud service account, share a Drive folder with its email address, then set `GDRIVE_ENABLED=true` plus either `GDRIVE_SERVICE_ACCOUNT_JSON` (the key file's contents as one env var — works on Render, which has nowhere persistent to upload a file) or `GDRIVE_SERVICE_ACCOUNT_FILE` (a path). I cannot create a Google Cloud project, service account, or credentials myself.

**181 offline tests passing** (1 skipped — an upload-path test that only runs if `google-api-python-client` happens to be installed locally). All new modules verified live: server starts cleanly, `/health` correctly reports `sqlite` as the active backend and both new integrations as "not configured" until you add credentials, `/environment` still works end-to-end against real upstream data — and both the CouchDB and MongoDB backends are now verified against real running instances, not just mocks.

---

## Honest re-rating

Before the hardening pass: **7/10** — real, working, well-tested, but no CI gate, a CORS misconfiguration, no alert delivery beyond polling, and an unexamined ephemeral-storage gap undercutting the "history" pitch.

After hardening: **9/10** — CI gates every push, CORS is fixed and verified live, alerts have a delivery path, the DB has real health visibility, dependencies are pinned with automated updates.

After the Part 4 science/storage pass: **still 9/10, but a more defensible 9.** The alert science now cites real published standards instead of invented bands, the storage architecture is genuinely pluggable and ready for CouchDB the moment you have one running, and Google Drive backup is real, tested (against mocks), optional code — not a promise. It stays short of 10 for exactly the reasons in Part 3: nothing here can install/run CouchDB, create Google credentials, attach a paid disk, get a domain expert's sign-off, or watch uptime with a dedicated third-party service. Those remain real-world actions, not code gaps.
