import os
import sys
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from pathlib import Path
import logging

# Get the path to the .env file and load it first
env_path = Path(__file__).resolve().parent.parent / ".env"
print(f"Loading .env file from: {env_path}")
load_dotenv(dotenv_path=env_path, override=True)

sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../../shared"))
)


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
)
from app.config import settings
from app.db.mongodb import connect_to_mongo, close_mongo_connection
from shared.models.user_data import UserData
from app.models.analytics_result import AnalyticsResult
from app.models.plot import Plot
from app.models.trained_model import TrainedModel
from app.models.column_stats import ColumnStats
from app.utils.ai_summary import initialize_openai_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: connect to DB
    mongo_uri = os.getenv("MONGODB_URI")
    db_name = os.getenv("MONGODB_DB")
    client = AsyncIOMotorClient(mongo_uri)
    await init_beanie(
        database=client[db_name],
        document_models=[UserData, AnalyticsResult, Plot, TrainedModel, ColumnStats],
    )

    # Initialize OpenAI client
    initialize_openai_client()

    await connect_to_mongo()
    yield
    await close_mongo_connection()


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


@app.get("/")
async def root():
    return {"message": "Welcome to the Narrative Modeling API"}
