from pydantic import BaseModel
from typing import List
import os
from dotenv import load_dotenv
from pathlib import Path

# Get the path to the .env file
env_path = Path(__file__).resolve().parent.parent / ".env"
print(f"Loading .env file from config.py: {env_path}")
load_dotenv(dotenv_path=env_path)


class Settings(BaseModel):
    # MongoDB settings
    MONGODB_URI: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    MONGODB_DB: str = os.getenv("MONGODB_DB", "narrative_modeling")
    TEST_MONGODB_DB: str = os.getenv("TEST_MONGODB_DB", "narrative_modeling_test")
    TEST_MONGODB_URI: str = os.getenv("TEST_MONGODB_URI", "mongodb://localhost:27017/narrative_modeling_test")

    # API settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Narrative Modeling API"

    # CORS settings
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "https://narrative-modeling.vercel.app",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "*",  # Fallback to allow all origins
    ]


settings = Settings()
