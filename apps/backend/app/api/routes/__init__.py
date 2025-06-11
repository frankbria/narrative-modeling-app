from fastapi import APIRouter
from app.api.routes import (
    user_data,
    analytics_result,
    plot,
    trained_model,
    upload,
    store,
    column_stats,
    health,
    secure_upload,
)

api_router = APIRouter()

api_router.include_router(user_data.router, prefix="/user_data", tags=["user_data"])
api_router.include_router(
    analytics_result.router, prefix="/analytics_result", tags=["analytics_result"]
)
api_router.include_router(plot.router, prefix="/plot", tags=["plot"])
api_router.include_router(
    trained_model.router, prefix="/trained_model", tags=["trained_model"]
)
api_router.include_router(upload.router, prefix="/upload", tags=["upload"])
api_router.include_router(store.router, prefix="/store", tags=["store"])
api_router.include_router(
    column_stats.router, prefix="/column_stats", tags=["column_stats"]
)
api_router.include_router(health.router, prefix="", tags=["health"])
api_router.include_router(secure_upload.router, prefix="/secure-upload", tags=["secure-upload"])
