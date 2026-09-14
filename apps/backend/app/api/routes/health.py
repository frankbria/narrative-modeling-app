import asyncio
import logging
import os
import time
from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.auth.nextauth_auth import get_current_user_id
from app.models.user_data import UserData  # To access beanie database
from app.services.s3_service import s3_service
from app.utils.s3 import configured_bucket

router = APIRouter()
# Router mounted under /api/v1 (#479): the admin health widget reaches the backend
# through nginx's /api/ proxy. It carries the cheap liveness alias and the
# authenticated upstream diagnostic — but NOT /health/ready, which stays root-only
# for the LB. Being under /api/v1 also puts the diagnostic under the global
# RateLimitMiddleware, so an authenticated caller can't loop its outbound calls
# unthrottled (#503).
liveness_router = APIRouter()
logger = logging.getLogger(__name__)

async def check_mongodb_connection() -> dict[str, Any]:
    """
    Check MongoDB connectivity and response time
    Returns health status, latency, and error details if unhealthy
    """
    start_time = time.time()
    try:
        # Access the MongoDB database through Beanie
        # UserData is a Beanie document model, so it has access to the database
        db = UserData.get_motor_collection().database
        # Ping the MongoDB server
        await db.client.admin.command('ping')
        latency_ms = (time.time() - start_time) * 1000

        return {
            "status": "healthy",
            "latency_ms": round(latency_ms, 2),
            "database": db.name
        }
    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        logger.error(f"MongoDB health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "latency_ms": round(latency_ms, 2),
            "error": "unavailable"  # detail logged server-side (issue #269)
        }

async def check_s3_access() -> dict[str, Any]:
    """
    Check S3 bucket accessibility and response time
    Returns health status, latency, and bucket access details
    """
    start_time = time.time()

    # Check if S3 is in mock mode (test credentials or not configured)
    if s3_service.is_mock_mode or s3_service.s3_client is None:
        latency_ms = (time.time() - start_time) * 1000
        return {
            "status": "not_configured",
            "latency_ms": round(latency_ms, 2),
            "message": "S3 running in mock mode (test credentials or not configured)"
        }

    try:
        # Test bucket access by checking if our specific bucket exists. boto3 is
        # synchronous, so run it off the event loop — a slow/hung head_bucket must
        # not stall the worker (#503 AC2).
        bucket_name = configured_bucket() or "unknown"  # the one shared resolver (#507)
        await asyncio.to_thread(s3_service.s3_client.head_bucket, Bucket=bucket_name)
        latency_ms = (time.time() - start_time) * 1000

        return {
            "status": "healthy",
            "latency_ms": round(latency_ms, 2),
            "bucket": bucket_name,
            "accessible": True
        }
    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        logger.error(f"S3 health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "latency_ms": round(latency_ms, 2),
            "error": "unavailable"  # detail logged server-side (issue #269)
        }

async def check_openai_api() -> dict[str, Any]:
    """
    Check OpenAI API accessibility and response time
    Returns health status, latency, and API availability
    """
    start_time = time.time()
    openai_api_key = os.getenv("OPENAI_API_KEY")

    if not openai_api_key or openai_api_key == "your-openai-api-key":
        return {
            "status": "not_configured",
            "latency_ms": 0,
            "message": "OpenAI API key not configured"
        }

    try:
        # Lightweight API check - list models endpoint
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {openai_api_key}"}
            )
            latency_ms = (time.time() - start_time) * 1000

            if response.status_code == 200:
                return {
                    "status": "healthy",
                    "latency_ms": round(latency_ms, 2),
                    "api_version": "v1"
                }
            else:
                return {
                    "status": "unhealthy",
                    "latency_ms": round(latency_ms, 2),
                    "error": f"API returned status {response.status_code}"
                }
    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        logger.error(f"OpenAI health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "latency_ms": round(latency_ms, 2),
            "error": "unavailable"  # detail logged server-side (issue #269)
        }

@router.get("/health")
async def health_check():
    """
    Basic liveness check - returns 200 if the application is running
    Use this for load balancer health checks
    """
    return {
        "status": "alive",
        "timestamp": datetime.now(UTC).isoformat(),
        "environment": os.getenv("ENVIRONMENT", "development"),
        "version": os.getenv("APP_VERSION", "1.0.0")
    }

@liveness_router.get("/health", name="liveness_v1")
async def liveness_v1() -> dict[str, str]:
    """Liveness under /api/v1 for the browser-facing admin widget (#479)."""
    return await health_check()


@router.get("/health/live")
async def liveness_check():
    """Liveness alias — trivial, dependency-free (#503 AC4). Same as /health."""
    return await health_check()


def _check_or_generic(name: str, result: Any) -> dict[str, Any]:
    """A gathered check may be an Exception; log its text server-side but never
    serialize it into a response body (issue #269)."""
    if not isinstance(result, Exception):
        return result
    logger.error(f"{name} health check raised: {str(result)}")
    return {"status": "unhealthy", "latency_ms": None, "error": "unavailable"}


@router.get("/health/ready")
async def readiness_check():
    """Readiness — "can THIS instance serve traffic", nothing more (#503).

    Only MongoDB is checked: it is the one dependency without which the app cannot
    serve any request, and its ping is async (non-blocking). Deliberately makes
    **no** outbound third-party call — this endpoint is unauthenticated and polled
    constantly by load balancers and uptime monitors, so a per-request OpenAI call
    or blocking S3 ``head_bucket`` here was a cost-amplification DoS and an
    event-loop stall (#503). Whole-system upstream health lives behind auth at
    ``GET /health/dependencies``. 200 if ready, 503 otherwise — the contract the
    Docker/compose healthchecks depend on.
    """
    # return_exceptions so a raising check is sanitized by _check_or_generic
    # rather than 500ing and leaking its text into this unauthenticated body (#269).
    results: list[Any] = await asyncio.gather(
        check_mongodb_connection(), return_exceptions=True
    )
    checks = {"mongodb": _check_or_generic("MongoDB", results[0])}
    ready = checks["mongodb"]["status"] == "healthy"

    return JSONResponse(
        status_code=200 if ready else 503,
        content={
            "status": "ready" if ready else "not_ready",
            "timestamp": datetime.now(UTC).isoformat(),
            "checks": checks,
        },
    )


@liveness_router.get("/health/dependencies")
async def dependencies_check(_user_id: str = Depends(get_current_user_id)):
    """Full upstream diagnostic — MongoDB + S3 + OpenAI (#503 AC3).

    Mounted under /api/v1 (via ``liveness_router``): it makes outbound calls
    (OpenAI, S3), so it must sit off the anonymous readiness path AND under the
    global rate limiter. It is **authenticated** (any signed-in user) and
    **throttled** (RateLimitMiddleware covers /api/v1) so no caller can loop its
    outbound calls unthrottled — the cost-amplification vector #503 closes.
    Intended for the admin HealthMonitor (P1.3); #479's admin ``/health/status``
    can later wrap this with the admin allowlist. Checks run in parallel and all
    I/O is non-blocking (S3's boto3 probe is offloaded via ``asyncio.to_thread``).
    """
    results: list[Any] = await asyncio.gather(
        check_mongodb_connection(),
        check_s3_access(),
        check_openai_api(),
        return_exceptions=True,
    )
    mongo_result, s3_result, openai_result = results
    checks = {
        "mongodb": _check_or_generic("MongoDB", mongo_result),
        "s3": _check_or_generic("S3", s3_result),
        "openai": _check_or_generic("OpenAI", openai_result),
    }
    # MongoDB is the only serve-blocking dependency; S3/OpenAI are informational.
    critical_healthy = checks["mongodb"]["status"] == "healthy"

    return JSONResponse(
        status_code=200 if critical_healthy else 503,
        content={
            "status": "healthy" if critical_healthy else "unhealthy",
            "timestamp": datetime.now(UTC).isoformat(),
            "checks": checks,
        },
    )

# NOTE (issue #273): the old JSON `/metrics` and `/security` endpoints were
# removed. They served a never-fed in-memory ApplicationMonitor and, being
# registered before main.py's Prometheus `/metrics`, shadowed it so scrapers got
# unparseable JSON. Real metrics are Prometheus at GET /metrics (app.main).
