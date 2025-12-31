from pydantic import BaseModel, field_validator
from typing import List
import os
import logging
from dotenv import load_dotenv
from pathlib import Path

logger = logging.getLogger(__name__)

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

    # AWS/S3 settings
    AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
    S3_BUCKET: str = os.getenv("S3_BUCKET", "narrative-modeling-uploads")

    # CORS settings
    @property
    def BACKEND_CORS_ORIGINS(self) -> List[str]:
        cors_origins = os.getenv("BACKEND_CORS_ORIGINS", '["*"]')
        if cors_origins:
            import json
            try:
                return json.loads(cors_origins)
            except (json.JSONDecodeError, ValueError):
                pass
        # Default to allow all origins in development
        return ["*"]

    @field_validator("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY")
    @classmethod
    def validate_no_dummy_credentials(cls, v: str, info) -> str:
        """Validate that dummy/test credentials aren't used in production."""
        dummy_patterns = ["test-", "dummy-", "sk-test-", "placeholder"]
        env = os.getenv("NODE_ENV", os.getenv("ENVIRONMENT", "development"))

        if env.lower() == "production":
            for pattern in dummy_patterns:
                if pattern in v.lower():
                    raise ValueError(
                        f"Dummy credential detected in production environment for {info.field_name}. "
                        f"Please set real credentials."
                    )
        elif any(pattern in v.lower() for pattern in dummy_patterns):
            logger.warning(
                f"Dummy credential detected for {info.field_name} in {env} environment. "
                "This is OK for testing but should not be used in production."
            )

        return v


settings = Settings()
