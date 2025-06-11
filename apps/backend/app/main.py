# apps/backend/app/main.py
import os
import sys
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from pathlib import Path
import logging

# Add the app directory to sys.path if needed
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

# Get the path to the .env file and load it first
env_path = Path(__file__).resolve().parent.parent / ".env"
print(f"Loading .env file from: {env_path}")
load_dotenv(dotenv_path=env_path, override=True)


# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Suppress AWS logging
logging.getLogger("boto3").setLevel(logging.WARNING)
logging.getLogger("botocore").setLevel(logging.WARNING)
logging.getLogger("s3transfer").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    user_data,
    analytics_result,
    plot,
    trained_model,
    upload,
    store,
    visualizations,
    column_stats,
    s3,
    data_processing,
    ai_analysis,
    model_training,
    production,
    monitoring,
    ab_testing,
    batch_prediction,
    model_export,
    documentation,
    onboarding,
    cache,
)
from app.config import settings
from app.db.mongodb import connect_to_mongo, close_mongo_connection
from app.models.user_data import UserData
from app.models.analytics_result import AnalyticsResult
from app.models.plot import Plot
from app.models.trained_model import TrainedModel
from app.models.column_stats import ColumnStats
from app.models.ml_model import MLModel
from app.models.api_key import APIKey
from app.models.ab_test import ABTest
from app.models.batch_job import BatchJob
from app.utils.ai_summary import initialize_openai_client
from app.services.redis_cache import init_cache, cleanup_cache


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: connect to DB
    mongo_uri = os.getenv("MONGODB_URI")
    db_name = os.getenv("MONGODB_DB")
    client = AsyncIOMotorClient(mongo_uri)
    await init_beanie(
        database=client[db_name],
        document_models=[UserData, AnalyticsResult, Plot, TrainedModel, ColumnStats, MLModel, APIKey, ABTest, BatchJob],
    )

    # Initialize OpenAI client
    initialize_openai_client()

    # Initialize Redis cache
    await init_cache()

    await connect_to_mongo()
    yield
    await close_mongo_connection()
    await cleanup_cache()


# ✅ Create the app only once
app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# ✅ Apply CORS to the correct app instance
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Include routers
app.include_router(
    upload.router, prefix=f"{settings.API_V1_STR}/upload", tags=["upload"]
)
app.include_router(store.router, prefix=settings.API_V1_STR, tags=["store"])
app.include_router(
    user_data.router, prefix=f"{settings.API_V1_STR}/user_data", tags=["user_data"]
)
app.include_router(
    analytics_result.router,
    prefix=f"{settings.API_V1_STR}/analytics",
    tags=["analytics"],
)
app.include_router(plot.router, prefix=f"{settings.API_V1_STR}/plots", tags=["plots"])
app.include_router(
    trained_model.router, prefix=f"{settings.API_V1_STR}/models", tags=["models"]
)
app.include_router(
    visualizations.router,
    prefix=f"{settings.API_V1_STR}/visualizations",
    tags=["visualizations"],
)
app.include_router(
    column_stats.router,
    prefix=f"{settings.API_V1_STR}/column_stats",
    tags=["column_stats"],
)
app.include_router(
    s3.router,
    prefix=f"{settings.API_V1_STR}/s3",
    tags=["s3"],
)
app.include_router(
    data_processing.router,
    prefix=f"{settings.API_V1_STR}/data",
    tags=["data_processing"],
)
app.include_router(
    ai_analysis.router,
    prefix=f"{settings.API_V1_STR}/ai",
    tags=["ai_analysis"],
)
app.include_router(
    model_training.router,
    prefix=f"{settings.API_V1_STR}/ml",
    tags=["model_training"],
)
app.include_router(
    production.router,
    prefix=f"{settings.API_V1_STR}",
    tags=["production"],
)
app.include_router(
    monitoring.router,
    prefix=f"{settings.API_V1_STR}",
    tags=["monitoring"],
)
app.include_router(
    ab_testing.router,
    prefix=f"{settings.API_V1_STR}",
    tags=["ab-testing"],
)
app.include_router(
    batch_prediction.router,
    prefix=f"{settings.API_V1_STR}",
    tags=["batch-prediction"],
)
app.include_router(
    model_export.router,
    prefix=f"{settings.API_V1_STR}",
    tags=["model-export"],
)
app.include_router(
    documentation.router,
    prefix=f"{settings.API_V1_STR}",
    tags=["documentation"],
)
app.include_router(
    onboarding.router,
    prefix=f"{settings.API_V1_STR}",
    tags=["onboarding"],
)
app.include_router(
    cache.router,
    prefix=f"{settings.API_V1_STR}",
    tags=["cache"],
)


@app.get("/")
async def root():
    return {"message": "Welcome to the Narrative Modeling API"}
