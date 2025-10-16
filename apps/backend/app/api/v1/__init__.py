"""
API v1 router - First versioned API for Narrative Modeling App.

This module provides the v1 API router that includes all endpoints
with the /api/v1 prefix for proper API versioning.
"""

from fastapi import APIRouter
from app.api.routes import (
    health,
    secure_upload,
    data_processing,
    ai_analysis,
    model_training,
    production,
    monitoring,
    visualizations,
    transformations,
    versions,
    datasets,
)

# Create v1 API router
api_v1_router = APIRouter(prefix="/api/v1", tags=["v1"])

# Include all route modules
api_v1_router.include_router(health.router, prefix="/health", tags=["health"])
api_v1_router.include_router(datasets.router, tags=["datasets"])  # New dataset routes
api_v1_router.include_router(secure_upload.router, prefix="/datasets", tags=["datasets"])
api_v1_router.include_router(data_processing.router, prefix="/datasets", tags=["data-processing"])
api_v1_router.include_router(ai_analysis.router, prefix="/ai", tags=["ai-analysis"])
api_v1_router.include_router(model_training.router, prefix="/models", tags=["model-training"])
api_v1_router.include_router(production.router, prefix="/predict", tags=["predictions"])
api_v1_router.include_router(monitoring.router, prefix="/monitoring", tags=["monitoring"])
api_v1_router.include_router(visualizations.router, prefix="/visualizations", tags=["visualizations"])
api_v1_router.include_router(transformations.router, prefix="/transformations", tags=["transformations"])
api_v1_router.include_router(versions.router, tags=["versioning"])

__all__ = ["api_v1_router"]
