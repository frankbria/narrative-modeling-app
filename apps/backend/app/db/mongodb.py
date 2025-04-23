from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from app.config import settings
from shared.models.user_data import UserData
from app.models.column_stats import ColumnStats


async def connect_to_mongo():
    """Connect to MongoDB and initialize Beanie"""
    client = AsyncIOMotorClient(settings.MONGODB_URI)
    await init_beanie(
        database=client[settings.MONGODB_DB],
        document_models=[
            UserData,
            ColumnStats,
            # Add other document models here as needed
        ],
    )


async def close_mongo_connection():
    """Close MongoDB connection"""
    # Beanie handles connection closing automatically
    pass
