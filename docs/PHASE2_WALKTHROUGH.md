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
- 101 offline tests written and passing at this point (Day-2 monsoon-squall fixture correctly triggers `small_craft_unsafe` / `storm_level_wind` / `heavy_rain_flood_risk`; a calm-data fixture correctly triggers nothing).
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

1. **Attach a Render persistent disk.** This needs your Render dashboard, requires upgrading off the free plan, and the `render.yaml` disk block is deliberately left commented out so it doesn't break your current free-tier deploy if applied blindly. Uncomment it and set `CONFLUENCE_DB_PATH=/var/data/confluence_history.db` only after upgrading the plan.
2. **Create the Slack/Discord webhook itself.** I built and tested the delivery code, but generating an actual webhook URL requires access to your Slack workspace or Discord server. Create one, then set `ALERT_WEBHOOK_URL` as a Render env var (and optionally a GitHub secret if you want it in CI).
3. **Set `RENDER_APP_URL` as a GitHub secret.** Both cron workflows (`keep_alive.yml`, `ingest_history.yml`) read this secret; I can write the workflow YAML but can't create repository secrets myself.
4. **External uptime monitoring.** Nothing currently pages anyone if the live service goes down. Point a free monitor (UptimeRobot, Better Uptime, etc.) at `/health` — that's a third-party account I can't create for you.
5. **Domain-expert review of the alert thresholds.** The heat index and dew point formulas are standard science; the small-craft/storm-potential/coastal-flood band cutoffs are my engineering judgment. If this is ever pitched to fishermen, an NGO, or a coastal-safety org, get an actual meteorologist/oceanographer to review `derived_insights.py` and `alert_rules.json` before anyone relies on it operationally. I can implement whatever they recommend, but I can't be the authority that certifies it.
6. **Registering this as a callable tool in any AI platform.** Nothing about this build makes ChatGPT, Claude, or any other frontier model call this API automatically. Someone has to wire it in as a function/tool definition inside a specific agent or app for the grounding benefit to actually reach a model in production.
7. **Reviewing and committing these changes.** I have not run `git add`/`git commit`/`git push` on any of this — it's sitting as uncommitted changes in your working tree for you to review first, per your repo's normal workflow.
8. **Load/scale testing under real traffic.** The 7-way stress suite tests upstream failure isolation, not concurrent-user load. If this ever gets real traffic volume, that's a separate exercise (e.g. `locust`, already in your installed packages) I haven't run.
9. **Any billing or paid-plan decisions** (Render tier upgrade, a custom domain, etc.) — these are account/cost decisions that are yours to make, not mine to execute.

---

## Honest re-rating

Before this pass: **7/10** — real, working, well-tested, but no CI gate, a CORS misconfiguration, no alert delivery beyond polling, and an unexamined ephemeral-storage gap undercutting the "history" pitch.

After this pass: **9/10.** Everything fixable from inside the code/config is fixed and verified — CI now gates every push, the CORS issue is corrected and confirmed live, alerts have an actual delivery path, the DB has real health visibility, dependencies are pinned with automated update PRs, and the durable-storage path is documented and ready to flip on. It stays short of 10/10 deliberately: the persistent disk isn't actually attached (needs your paid-plan decision), the webhook has no real URL behind it yet (needs your Slack/Discord), nothing is watching uptime, and the alert thresholds haven't been checked by a domain expert. Those are the honest, remaining items in Part 3 — not code gaps, but real-world actions only you can take.
