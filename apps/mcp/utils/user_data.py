from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
from ..models.user_data import UserData
import os
import asyncio

client = AsyncIOMotorClient(os.getenv("MONGODB_URI"))
db = client.get_default_database()


# Ideally, run this once at startup, not per-call
async def init():
    await init_beanie(database=db, document_models=[UserData])


async def get_user_data_by_id(dataset_id: str) -> UserData | None:
    try:
        # Ensure Beanie is initialized (only once in practice)
        if not UserData.__database__:
            await init()
        return await UserData.get(dataset_id)
    except Exception as e:
        print(f"Error loading UserData: {e}")
        return None
