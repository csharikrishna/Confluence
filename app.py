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

import sys
import time
import logging
from typing import Optional
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

app = FastAPI(
    title="Unified Environmental Intelligence API",
    description=(
        "A single normalized API endpoint that pulls live data from 4 independent environmental sources "
        "(weather, ocean/marine, air quality, climate baseline) concurrently, normalizes the units and schema, "
        "and serves it as a single JSON response for frontier AI models and coastal risk applications."
    ),
    version="1.0.0",
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
        "sources": [
            "Open-Meteo Weather",
            "Open-Meteo Marine",
            "OpenAQ Air Quality",
            "NASA POWER Climate Baseline",
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
