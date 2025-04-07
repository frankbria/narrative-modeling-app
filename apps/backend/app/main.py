import os
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.api.routes import s3, user_data, analytics_result, plot, trained_model
from dotenv import load_dotenv

from app.models.user_data import UserData
from app.models.analytics_result import AnalyticsResult
from app.models.plot import Plot
from app.models.trained_model import TrainedModel

app = FastAPI()

load_dotenv()

app.include_router(s3.router, prefix="/api")
app.include_router(user_data.router, prefix="/api/user_data", tags=["user_data"])
app.include_router(
    analytics_result.router, prefix="/api/analytics", tags=["AnalyticsResult"]
)
app.include_router(plot.router, prefix="/api/plots", tags=["Plot"])
app.include_router(trained_model.router, prefix="/api/models", tags=["TrainedModel"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: connect to DB
    mongo_uri = os.getenv("MONGODB_URI")
    db_name = os.getenv("MONGODB_DB")
    client = AsyncIOMotorClient(mongo_uri)
    await init_beanie(
        database=client[db_name],
        document_models=[UserData, AnalyticsResult, Plot, TrainedModel],
    )

    yield  # This is where the app will run


app = FastAPI(lifespan=lifespan)


@app.get("/")
def read_root():
    return {"message": "🎉 Your FastAPI app is live on Render!"}
