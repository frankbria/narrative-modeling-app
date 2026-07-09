import asyncio
import logging
import os
import time
from datetime import datetime
from typing import Any

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.models.user_data import UserData  # To access beanie database
from app.services.monitoring import monitor
from app.services.s3_service import s3_service

router = APIRouter()
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
        # Test bucket access by checking if our specific bucket exists
        bucket_name = os.getenv("AWS_S3_BUCKET_NAME") or os.getenv("AWS_BUCKET_NAME", "unknown")
        s3_service.s3_client.head_bucket(Bucket=bucket_name)
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
        "timestamp": datetime.utcnow().isoformat(),
        "environment": os.getenv("ENVIRONMENT", "development"),
        "version": os.getenv("APP_VERSION", "1.0.0")
    }

@router.get("/health/ready")
async def readiness_check():
    """
    Readiness check - validates all external dependencies are available
    Returns 200 if ready, 503 if any dependency is unhealthy
    Executes all health checks in parallel for performance
    """
    # Run all health checks in parallel using asyncio.gather
    mongodb_check, s3_check, openai_check = await asyncio.gather(
        check_mongodb_connection(),
        check_s3_access(),
        check_openai_api(),
        return_exceptions=True
    )

    # Gather may return an Exception per check; log its text server-side but never
    # serialize it into this unauthenticated response body (issue #269).
    def _check_or_generic(name: str, result: Any) -> dict[str, Any]:
        if not isinstance(result, Exception):
            return result
        logger.error(f"{name} health check raised: {str(result)}")
        # latency_ms: None keeps the shape consistent with the other checks.
        return {"status": "unhealthy", "latency_ms": None, "error": "unavailable"}

    checks = {
        "mongodb": _check_or_generic("MongoDB", mongodb_check),
        "s3": _check_or_generic("S3", s3_check),
        "openai": _check_or_generic("OpenAI", openai_check),
    }

    # Determine overall health status
    # Critical services: MongoDB (only)
    # Optional services: S3, OpenAI (can be unhealthy/not_configured in dev/CI)
    critical_healthy = checks["mongodb"]["status"] == "healthy"

    # Backend is ready if MongoDB is healthy, regardless of S3/OpenAI status
    # S3 and OpenAI can be in any state (healthy, unhealthy, not_configured)
    status_code = 200 if critical_healthy else 503
    overall_status = "ready" if critical_healthy else "not_ready"

    return JSONResponse(
        status_code=status_code,
        content={
            "status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "checks": checks
        }
    )

@router.get("/metrics")
async def get_metrics():
    """Get application metrics for monitoring"""
    return monitor.get_health_metrics()

@router.get("/security")
async def get_security_metrics():
    """Get security-related metrics"""
    return monitor.get_security_summary()