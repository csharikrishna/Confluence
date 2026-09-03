"""
Unified Environmental Intelligence Endpoint — Production-Hardened FastAPI Service
Includes:
- Concurrency via ThreadPoolExecutor
- Multi-tier in-memory caching (Station cache 24h, Snapshot cache 5m)
- Rate limiting via slowapi (30 req/min per IP)
- Global exception handling & request logging
- Secure environment configuration

Exposes:
  GET /environment?lat=13.08&lon=80.27&name=Chennai%20Coast
  GET /health
  GET /docs
  GET /
"""

import os
import sys
import time
import asyncio
import logging
import requests
import concurrent.futures
from typing import Optional
from datetime import datetime, timezone, timedelta
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Query, HTTPException, status, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from env_intelligence_test import get_environmental_snapshot, validate_coordinates
import storage
import notifications
from locations import get_all_locations
from derived_insights import compute_derived_insights
from rules_engine import evaluate_alerts

# Reconfigure console encoding for Windows UTF-8 support
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("environmental_api")

# Rate Limiter: 30 requests/minute per client IP
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 0. Phase 2A: initialize the SQLite history store (creates tables + prunes stale rows)
    try:
        storage.init_db()
        logger.info(f"History store initialized at {storage.DB_PATH}")
    except Exception as e:
        logger.warning(f"History store initialization failed: {e}")

    # 1. Startup: Pre-warm station metadata and snapshot cache for every registered
    #    location (Phase 2B — no longer hardcoded to Chennai alone).
    all_locations = get_all_locations()
    logger.info(f"Initializing API: Pre-warming caches for {len(all_locations)} registered location(s)...")
    try:
        def _prewarm():
            for loc in all_locations:
                try:
                    get_environmental_snapshot(lat=loc["lat"], lon=loc["lon"], name=loc["name"], bypass_cache=True)
                    logger.info(f"Pre-warmed: {loc['name']} ({loc['lat']}, {loc['lon']})")
                except Exception as e:
                    logger.warning(f"Pre-warm failed for {loc['name']}: {e}")

        loop = asyncio.get_running_loop()
        loop.run_in_executor(None, _prewarm)
    except Exception as e:
        logger.warning(f"Startup pre-warming deferred: {e}")

    # 2. Keep-alive task to prevent free-tier hosts (e.g. Render 15-min idle spin-down)
    render_url = os.getenv("RENDER_EXTERNAL_URL") or os.getenv("APP_URL")
    keep_alive_task = None
    if render_url:
        logger.info(f"Keep-alive enabled for public host: {render_url}")

        async def _keep_alive():
            while True:
                await asyncio.sleep(720)  # Ping every 12 minutes
                try:
                    r = requests.get(f"{render_url.rstrip('/')}/health", timeout=10)
                    logger.info(f"Self-ping keep-alive sent to {render_url}/health — status: {r.status_code}")
                except Exception as ex:
                    logger.warning(f"Keep-alive ping failed: {ex}")

        keep_alive_task = asyncio.create_task(_keep_alive())

    yield

    if keep_alive_task:
        keep_alive_task.cancel()
    logger.info("API shutdown complete.")


app = FastAPI(
    title="Unified Environmental Intelligence API",
    description=(
        "A single normalized API endpoint that pulls live data from 7 independent environmental sources "
        "(weather, ocean/marine, air quality, astronomical, terrain, climate baseline, seismic) concurrently, "
        "normalizes the units and schema, and serves it as a single JSON response for frontier AI models and "
        "coastal risk applications. Phase 2 adds persisted history/trends, a multi-location registry, and a "
        "physics-informed alerting layer on top of the raw Phase 1 hyperparameters."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter


# Custom Rate Limit Exceeded Handler
def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "error": "TooManyRequests",
            "message": "Rate limit exceeded (30 requests/minute). Please slow down.",
            "detail": str(exc.detail),
        },
    )


app.add_exception_handler(RateLimitExceeded, rate_limit_handler)


# Global Exception Handler: prevents stack trace leakage
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception during {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "InternalServerError",
            "message": "An unexpected error occurred while processing the environmental snapshot.",
            "detail": str(exc),
        },
    )


# Request Logging Middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    client_ip = request.client.host if request.client else "unknown"
    logger.info(f"{request.method} {request.url.path} - {response.status_code} ({duration_ms}ms) [client: {client_ip}]")
    return response


# Enable CORS for frontend integrations. This is a public, stateless, read-only API
# with no cookies/sessions — allow_credentials stays False so allow_origins="*" means
# what it says, rather than Starlette silently reflecting the caller's Origin header
# (which is what happens when credentials=True is combined with a wildcard origin).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["Info"])
def root():
    return {
        "service": "Unified Environmental Intelligence API",
        "version": "2.0.0",
        "documentation": "/docs",
        "openapi": "/openapi.json",
        "sample_query": "/environment?lat=13.08&lon=80.27&name=Chennai%20Coast",
        "features": [
            "Concurrent multi-source fetching (ThreadPoolExecutor)",
            "Multi-tier caching (24h station metadata, 5m snapshot cache)",
            "Rate limiting (30 requests/minute)",
            "Canonical ISO 8601 UTC timestamp normalization",
            "Automated physical boundary sanity checks",
            "Persisted history + 24h trend diffs (SQLite)",
            "Multi-location registry (GET /locations)",
            "Physics-informed derived insights (heat index, sea state, storm potential, ...)",
            "Config-driven rule-based alerting (GET /alerts)",
            "Optional Slack/Discord alert webhook (ALERT_WEBHOOK_URL)",
        ],
        "hyperparameters_count": "50+ physical variables",
        "sources": [
            "Open-Meteo Weather (14 hyperparameters)",
            "Open-Meteo Marine (12 hydrodynamic hyperparameters)",
            "OpenAQ Ground Stations (physical sensor array)",
            "Open-Meteo Air Quality (atmospheric model fallback)",
            "Sunrise-Sunset.org (solar & marine nautical ephemeris)",
            "Open-Meteo Elevation (topography & coastal flood vulnerability)",
            "NASA POWER (climatological solar & weather baseline)",
            "USGS Earthquake Hazards (7-day seismic & tsunami alert)",
        ],
        "endpoints": ["/environment", "/environment/history", "/locations", "/alerts", "/health", "/docs"],
    }


@app.get("/health", tags=["Health"])
def health_check():
    db_ok = storage.is_healthy()
    return {
        "status": "healthy" if db_ok else "degraded",
        "service": "environmental-intelligence-api",
        "concurrency": "enabled (ThreadPoolExecutor)",
        "rate_limiting": "enabled (slowapi 30/min)",
        "caching": "enabled (TTLCache 5m)",
        "history_store": f"sqlite ({os.path.basename(storage.DB_PATH)})",
        "history_store_status": "connected" if db_ok else "unreachable",
        "registered_locations": len(get_all_locations()),
        "alerting": "rule-based (config-driven, no ML)",
        "alert_webhook": "configured" if notifications.WEBHOOK_URL else "not configured",
        "phase": 2,
    }


def _persist_and_log(lat, lon, name, snapshot, alerts):
    """Background task: persist the fresh snapshot and log/notify any newly firing
    alerts. Best-effort — a storage or webhook failure must never affect the
    response already sent.
    """
    try:
        storage.save_snapshot(lat, lon, name, snapshot)
    except Exception as e:
        logger.warning(f"Failed to persist snapshot for ({lat}, {lon}): {e}")

    location = {"name": name, "lat": lat, "lon": lon}
    for alert in alerts:
        try:
            notifications.log_and_notify(lat, lon, alert, location)
        except Exception as e:
            logger.warning(f"Failed to log/notify alert '{alert.get('id')}' for ({lat}, {lon}): {e}")


@app.get(
    "/environment",
    tags=["Environmental Intelligence"],
    summary="Get unified environmental snapshot",
    description="Fetches live multi-domain environmental context for any lat/lon coordinates with concurrency, caching, and validation.",
)
@limiter.limit("30/minute")
def get_environment(
    request: Request,
    background_tasks: BackgroundTasks,
    lat: float = Query(..., description="Latitude (-90.0 to 90.0)"),
    lon: float = Query(..., description="Longitude (-180.0 to 180.0)"),
    name: Optional[str] = Query("Unnamed Location", description="Optional label for location"),
    timeout: Optional[float] = Query(10.0, ge=0.5, le=30.0, description="Per-source request timeout in seconds"),
    bypass_cache: Optional[bool] = Query(False, description="Bypass the 5-minute snapshot cache to force a fresh fetch"),
):
    # Upfront coordinate validation
    valid, err = validate_coordinates(lat, lon)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Invalid coordinates", "message": err},
        )

    snapshot = get_environmental_snapshot(
        lat=lat,
        lon=lon,
        name=name,
        timeout=timeout,
        bypass_cache=bypass_cache,
    )

    data = snapshot.get("data", {}) or {}
    meta = snapshot.setdefault("meta", {})

    # Phase 2: physics-informed composite signals, computed fresh on every read.
    # The rapid-pressure-fall signal needs a 24h-ago reading — best-effort, None
    # until history exists for this location.
    current_pressure = (data.get("weather") or {}).get("pressure_hpa")
    try:
        pressure_change_24h = storage.get_pressure_change_24h(lat, lon, current_pressure)
    except Exception as e:
        logger.warning(f"Pressure trend lookup failed for ({lat}, {lon}): {e}")
        pressure_change_24h = None

    derived = compute_derived_insights(data, lat=lat, pressure_change_24h_hpa=pressure_change_24h)
    meta["derived_insights"] = derived

    # Phase 2A: 24h trend diff against stored history (None until history exists).
    try:
        trend = storage.compute_trend_24h(lat, lon, data)
    except Exception as e:
        logger.warning(f"Trend computation failed for ({lat}, {lon}): {e}")
        trend = None
    if trend:
        meta["trend_24h"] = trend

    # Phase 2C: evaluate the rules engine (threshold + trend-based rules).
    try:
        alerts = evaluate_alerts(data, derived, lat=lat, lon=lon, history_lookup=storage.get_reading_hours_ago)
    except Exception as e:
        logger.warning(f"Alert evaluation failed for ({lat}, {lon}): {e}")
        alerts = []
    meta["active_alerts"] = alerts

    # Persist every freshly-fetched (non-cache-hit) snapshot for future history/trends.
    if data and not meta.get("cache_hit"):
        background_tasks.add_task(_persist_and_log, lat, lon, name, snapshot, alerts)

    return JSONResponse(content=snapshot, status_code=status.HTTP_200_OK)


def _parse_iso(ts):
    ts = ts.strip()
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(ts)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Invalid timestamp", "message": f"Could not parse '{ts}' as ISO 8601"},
        )
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@app.get(
    "/environment/history",
    tags=["History & Trends"],
    summary="Query stored environmental history for a location",
    description="Returns persisted snapshot data for a lat/lon over a time range, optionally narrowed to one dotted field.",
)
@limiter.limit("30/minute")
def get_environment_history(
    request: Request,
    lat: float = Query(..., description="Latitude (-90.0 to 90.0)"),
    lon: float = Query(..., description="Longitude (-180.0 to 180.0)"),
    start: Optional[str] = Query(None, description="ISO 8601 start timestamp (default: 7 days ago)"),
    end: Optional[str] = Query(None, description="ISO 8601 end timestamp (default: now)"),
    field: Optional[str] = Query(None, description="Dotted field path, e.g. 'weather.temperature_c'"),
    limit: int = Query(500, ge=1, le=5000, description="Maximum rows to return"),
):
    valid, err = validate_coordinates(lat, lon)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Invalid coordinates", "message": err},
        )

    now = datetime.now(timezone.utc)
    end_dt = _parse_iso(end) if end else now
    start_dt = _parse_iso(start) if start else end_dt - timedelta(days=7)
    if start_dt > end_dt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Invalid range", "message": "start must be before end"},
        )

    rows = storage.get_history(
        lat,
        lon,
        start_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        end_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        field=field,
        limit=limit,
    )

    return {
        "location": {"lat": lat, "lon": lon},
        "start": start_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "end": end_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "field": field,
        "count": len(rows),
        "history": rows,
    }


@app.get(
    "/locations",
    tags=["Locations"],
    summary="List registered coastal locations",
    description="Returns every location the service tracks for pre-warming, scheduled history ingestion, and /alerts.",
)
def get_locations():
    locs = get_all_locations()
    return {"count": len(locs), "locations": locs}


@app.get(
    "/alerts",
    tags=["Alerting"],
    summary="Get active alerts across registered locations",
    description=(
        "Evaluates the rule-based alerting engine for every registered location (or a single lat/lon if given) "
        "and returns any currently active alerts, each with its triggering condition, severity, and value."
    ),
)
@limiter.limit("20/minute")
def get_alerts(
    request: Request,
    background_tasks: BackgroundTasks,
    lat: Optional[float] = Query(None, description="Optional: check a single location instead of the full registry"),
    lon: Optional[float] = Query(None, description="Required if lat is given"),
    bypass_cache: Optional[bool] = Query(False, description="Bypass the 5-minute snapshot cache to force a fresh fetch"),
):
    if lat is not None or lon is not None:
        if lat is None or lon is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "Invalid query", "message": "lat and lon must both be provided together"},
            )
        valid, err = validate_coordinates(lat, lon)
        if not valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "Invalid coordinates", "message": err},
            )
        targets = [{"name": "Custom Location", "lat": lat, "lon": lon}]
    else:
        targets = get_all_locations()

    def _check(loc):
        try:
            snap = get_environmental_snapshot(lat=loc["lat"], lon=loc["lon"], name=loc["name"], bypass_cache=bypass_cache)
            data = snap.get("data", {}) or {}
            current_pressure = (data.get("weather") or {}).get("pressure_hpa")
            try:
                pressure_change_24h = storage.get_pressure_change_24h(loc["lat"], loc["lon"], current_pressure)
            except Exception:
                pressure_change_24h = None
            derived = compute_derived_insights(data, lat=loc["lat"], pressure_change_24h_hpa=pressure_change_24h)
            alerts = evaluate_alerts(
                data, derived, lat=loc["lat"], lon=loc["lon"], history_lookup=storage.get_reading_hours_ago
            )
            return loc, alerts
        except Exception as e:
            logger.warning(f"Alert check failed for {loc.get('name')}: {e}")
            return loc, []

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, min(7, len(targets)))) as executor:
        for loc, alerts in executor.map(_check, targets):
            for alert in alerts:
                alert_with_loc = dict(alert)
                alert_with_loc["location"] = {"name": loc["name"], "lat": loc["lat"], "lon": loc["lon"]}
                results.append(alert_with_loc)
                background_tasks.add_task(notifications.log_and_notify, loc["lat"], loc["lon"], alert, loc)

    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "locations_checked": len(targets),
        "active_alert_count": len(results),
        "active_alerts": results,
    }


if __name__ == "__main__":
    import uvicorn

    print("Starting Unified Environmental Intelligence API on http://127.0.0.1:8000 ...")
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=False)
