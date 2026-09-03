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
from typing import Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Query, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from env_intelligence_test import get_environmental_snapshot, validate_coordinates

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
    # 1. Startup: Pre-warm station metadata and snapshot cache for Chennai Coast (13.08, 80.27)
    logger.info("Initializing API: Pre-warming caches for Chennai Coast (13.08, 80.27)...")
    try:
        def _prewarm():
            try:
                get_environmental_snapshot(lat=13.08, lon=80.27, name="Chennai Coast", bypass_cache=True)
                logger.info("Startup pre-warming successful: STATION_CACHE and SNAPSHOT_CACHE populated.")
            except Exception as e:
                logger.warning(f"Startup pre-warming encountered issue: {e}")

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
        "A single normalized API endpoint that pulls live data from 4 independent environmental sources "
        "(weather, ocean/marine, air quality, climate baseline) concurrently, normalizes the units and schema, "
        "and serves it as a single JSON response for frontier AI models and coastal risk applications."
    ),
    version="1.0.0",
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


# Enable CORS for frontend integrations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["Info"])
def root():
    return {
        "service": "Unified Environmental Intelligence API",
        "version": "1.0.0",
        "documentation": "/docs",
        "openapi": "/openapi.json",
        "sample_query": "/environment?lat=13.08&lon=80.27&name=Chennai%20Coast",
        "features": [
            "Concurrent multi-source fetching (ThreadPoolExecutor)",
            "Multi-tier caching (24h station metadata, 5m snapshot cache)",
            "Rate limiting (30 requests/minute)",
            "Canonical ISO 8601 UTC timestamp normalization",
            "Automated physical boundary sanity checks",
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
    }


@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "service": "environmental-intelligence-api",
        "concurrency": "enabled (ThreadPoolExecutor)",
        "rate_limiting": "enabled (slowapi 30/min)",
        "caching": "enabled (TTLCache 5m)",
        "phase": 1,
    }


@app.get(
    "/environment",
    tags=["Environmental Intelligence"],
    summary="Get unified environmental snapshot",
    description="Fetches live multi-domain environmental context for any lat/lon coordinates with concurrency, caching, and validation.",
)
@limiter.limit("30/minute")
def get_environment(
    request: Request,
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
    return JSONResponse(content=snapshot, status_code=status.HTTP_200_OK)


if __name__ == "__main__":
    import uvicorn

    print("Starting Unified Environmental Intelligence API on http://127.0.0.1:8000 ...")
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=False)
