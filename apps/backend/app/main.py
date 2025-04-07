from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import FastAPI
from api.routes import s3, user_data, analytics_result, plot, trained_model

from models.user_data import UserData
from models.analytics_result import AnalyticsResult
from models.plot import Plot
from models.trained_model import TrainedModel

app = FastAPI()

app.include_router(s3.router, prefix="/api")
app.include_router(user_data.router, prefix="/api/user_data", tags=["user_data"])
app.include_router(
    analytics_result.router, prefix="/api/analytics", tags=["AnalyticsResult"]
)
app.include_router(plot.router, prefix="/api/plots", tags=["Plot"])
app.include_router(trained_model.router, prefix="/api/models", tags=["TrainedModel"])


@app.on_event("startup")
async def app_init():
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    await init_beanie(
        database=client["your-db-name"],
        document_models=[UserData, AnalyticsResult, Plot, TrainedModel],
    )


@app.get("/")
def read_root():
    return {"message": "🎉 Your FastAPI app is live on Render!"}
