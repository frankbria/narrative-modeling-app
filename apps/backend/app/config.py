from pydantic import BaseModel, field_validator
from typing import List, Optional
import os
import sys
import logging
from dotenv import load_dotenv
from pathlib import Path

logger = logging.getLogger(__name__)

# Get the path to the .env file
env_path = Path(__file__).resolve().parent.parent / ".env"
print(f"Loading .env file from config.py: {env_path}")
load_dotenv(dotenv_path=env_path)

# Environments where disabling authentication (SKIP_AUTH=true) is permitted
ALLOWED_SKIP_AUTH_ENVIRONMENTS = {"development", "test"}


def get_environment(default: str = "development") -> str:
    """Return the canonical deployment environment, normalized to lowercase.

    Reads ``ENVIRONMENT`` first, falling back to the legacy ``NODE_ENV``.
    When neither is set during a pytest run, the environment counts as
    ``test``; otherwise ``default`` is returned.
    """
    env = os.getenv("ENVIRONMENT") or os.getenv("NODE_ENV")
    if env is None and "pytest" in sys.modules:
        env = "test"
    return (env or default).strip().lower()


def validate_skip_auth(
    skip_auth: Optional[bool] = None, environment: Optional[str] = None
) -> None:
    """Fail hard if SKIP_AUTH is enabled outside development/test (issue #149).

    Raises ``RuntimeError`` when ``skip_auth`` is true and the environment is
    not explicitly one of ``ALLOWED_SKIP_AUTH_ENVIRONMENTS``. An unset
    environment is treated as unsafe — production hosts often leave
    ``ENVIRONMENT`` undefined, and authentication must never be silently
    bypassed there.

    Args default to the ``SKIP_AUTH`` env var and ``get_environment()``.
    """
    if skip_auth is None:
        skip_auth = os.getenv("SKIP_AUTH", "false").strip().lower() == "true"
    if not skip_auth:
        return

    if environment is not None:
        signals = [environment]
    else:
        # Check EVERY set environment signal, not just the canonical one — a
        # stray .env supplying ENVIRONMENT=development must not outvote a
        # legacy deployment's real NODE_ENV=production (issue #149 review).
        signals = [v for v in (os.getenv("ENVIRONMENT"), os.getenv("NODE_ENV")) if v]
        if not signals and "pytest" in sys.modules:
            signals = ["test"]

    normalized = [s.strip().lower() for s in signals]
    if not normalized or any(
        s not in ALLOWED_SKIP_AUTH_ENVIRONMENTS for s in normalized
    ):
        got = ", ".join(repr(s) for s in normalized) or "unset"
        raise RuntimeError(
            f"SKIP_AUTH=true is only permitted when ENVIRONMENT (and legacy "
            f"NODE_ENV, if set) is explicitly 'development' or 'test' "
            f"(got {got}). Refusing to start with authentication disabled. "
            f"Unset SKIP_AUTH or set ENVIRONMENT=development."
        )

    logger.warning(
        "⚠️  SKIP_AUTH is enabled (environment=%s)! All authentication is "
        "bypassed — never use this outside development/test.",
        normalized[0],
    )


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
        production_envs = {"production", "prod", "staging", "live", "release"}
        env = get_environment()

        # Check for empty/blank credentials in production-like environments
        if v is None or v.strip() == "":
            if env.lower() in production_envs:
                raise ValueError(
                    f"Empty or blank credential for {info.field_name} in {env} environment. "
                    f"Please set real credentials."
                )
            return v

        # Check for dummy patterns in production-like environments
        is_production_like = env.lower() in production_envs
        if is_production_like:
            for pattern in dummy_patterns:
                if pattern in v.lower():
                    raise ValueError(
                        f"Dummy credential detected in production-like environment ({env}) for {info.field_name}. "
                        f"Please set real credentials."
                    )
        elif any(pattern in v.lower() for pattern in dummy_patterns):
            logger.warning(
                f"Dummy credential detected for {info.field_name} in {env} environment. "
                "This is OK for testing but should not be used in production."
            )

        return v


settings = Settings()
