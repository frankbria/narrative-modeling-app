from fastapi import APIRouter, HTTPException
from datetime import datetime
import os
from app.services.monitoring import monitor

router = APIRouter()

@router.get("/health")
async def health_check():
    """Health check endpoint for load balancer and monitoring"""
    health_metrics = monitor.get_health_metrics()
    
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "environment": os.getenv("ENVIRONMENT", "development"),
        "version": os.getenv("APP_VERSION", "1.0.0"),
        "metrics": health_metrics
    }

@router.get("/ready")
async def readiness_check():
    """Readiness check to ensure all dependencies are available"""
    # Add checks for database, S3, etc.
    checks = {
        "database": True,  # TODO: Add actual MongoDB check
        "storage": True,   # TODO: Add actual S3 check
    }
    
    all_ready = all(checks.values())
    
    return {
        "ready": all_ready,
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat()
    }

@router.get("/metrics")
async def get_metrics():
    """Get application metrics for monitoring"""
    return monitor.get_health_metrics()

@router.get("/security")
async def get_security_metrics():
    """Get security-related metrics"""
    return monitor.get_security_summary()