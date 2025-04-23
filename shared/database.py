# shared/database.py
import os
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
from shared.models.user_data import UserData


async def init_db():
    client = AsyncIOMotorClient(os.getenv("MONGODB_URI"))
    db = client.get_default_database()
    await init_beanie(database=db, document_models=[UserData])
