from pydantic import BaseModel, field_validator
from typing import List, Optional
import os
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

# Environments where production-grade safety checks must apply
PRODUCTION_LIKE_ENVIRONMENTS = {"production", "prod", "staging", "live", "release"}


def environment_signals() -> List[str]:
    """All explicitly set environment signals (ENVIRONMENT, legacy NODE_ENV),
    normalized to lowercase.

    Security checks must consider every signal: a stray .env supplying
    ENVIRONMENT=development must not outvote a deployment's real
    NODE_ENV=production (issue #149 review).
    """
    # `if v` drops unset (None) and explicitly empty ("") values — both mean
    # "no signal"; do not weaken this if a default is ever added upstream.
    return [
        v.strip().lower()
        for v in (os.getenv("ENVIRONMENT"), os.getenv("NODE_ENV"))
        if v
    ]


def is_production_like() -> bool:
    """True if ANY set environment signal names a production-like environment."""
    return any(s in PRODUCTION_LIKE_ENVIRONMENTS for s in environment_signals())


def get_environment(default: str = "development") -> str:
    """Return the canonical deployment environment, normalized to lowercase.

    Reads ``ENVIRONMENT`` first, falling back to the legacy ``NODE_ENV``,
    then ``default``. No implicit test detection — the test suite sets
    ENVIRONMENT=test explicitly in tests/conftest.py (a "pytest in
    sys.modules" heuristic proved spoofable: pytest-cov's subprocess hook
    imports pytest into child processes).
    """
    env = os.getenv("ENVIRONMENT") or os.getenv("NODE_ENV")
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
        # Check EVERY set environment signal, not just the canonical one
        signals = environment_signals()

    normalized = [s.strip().lower() for s in signals]
    if not normalized or any(
        s not in ALLOWED_SKIP_AUTH_ENVIRONMENTS for s in normalized
    ):
        got = ", ".join(repr(s) for s in normalized) or "unset"
        raise RuntimeError(
            f"SKIP_AUTH=true is only permitted when ENVIRONMENT (and legacy "
            f"NODE_ENV, if set) is explicitly 'development' or 'test' "
            f"(got {got}). Refusing to start with authentication disabled. "
            f"Unset SKIP_AUTH or set ENVIRONMENT=development (or =test)."
        )

    logger.warning(
        "⚠️  SKIP_AUTH is enabled (environment=%s)! All authentication is "
        "bypassed — never use this outside development/test.",
        ", ".join(normalized),
    )


class Settings(BaseModel):
    # MongoDB settings
    MONGODB_URI: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    MONGODB_DB: str = os.getenv("MONGODB_DB", "narrative_modeling")
    TEST_MONGODB_DB: str = os.getenv("TEST_MONGODB_DB", "narrative_modeling_test")
    TEST_MONGODB_URI: str = os.getenv(
        "TEST_MONGODB_URI", "mongodb://localhost:27017/narrative_modeling_test"
    )

    # API settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Narrative Modeling API"

    # AWS/S3 settings
    AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
    S3_BUCKET: str = os.getenv("S3_BUCKET", "narrative-modeling-uploads")

    # Redis (shared by the cache service and rate-limit middleware). Empty means
    # "no Redis configured" — the limiter then fails open (#151).
    REDIS_URL: str = os.getenv("REDIS_URL", "")

    # Rate limiting (issue #151). All env-configurable.
    RATE_LIMIT_ENABLED: bool = (
        os.getenv("RATE_LIMIT_ENABLED", "true").strip().lower() == "true"
    )
    # Default per-identity budget for session/IP-identified callers.
    RATE_LIMIT_DEFAULT_REQUESTS: int = int(
        os.getenv("RATE_LIMIT_DEFAULT_REQUESTS", "100")
    )
    RATE_LIMIT_DEFAULT_WINDOW_SECONDS: int = int(
        os.getenv("RATE_LIMIT_DEFAULT_WINDOW_SECONDS", "60")
    )
    # Window over which an APIKey's `rate_limit` field is counted (the field is
    # documented as "Requests per hour", so the default window is one hour).
    RATE_LIMIT_APIKEY_WINDOW_SECONDS: int = int(
        os.getenv("RATE_LIMIT_APIKEY_WINDOW_SECONDS", "3600")
    )
    # Whether to trust the client IP from the X-Forwarded-For header. Default OFF:
    # an unauthenticated caller can forge XFF to land in a fresh IP bucket on every
    # request, defeating the anonymous-flood limit. Enable ONLY when the app sits
    # behind a trusted reverse proxy (e.g. nginx) that overwrites XFF with the real
    # peer address. When off, the limiter uses the direct socket peer.
    RATE_LIMIT_TRUST_FORWARDED_FOR: bool = (
        os.getenv("RATE_LIMIT_TRUST_FORWARDED_FOR", "false").strip().lower() == "true"
    )

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
        env = get_environment()
        # Fail-safe: production-like if ANY set signal says so (a stray .env
        # ENVIRONMENT=development must not outvote a real NODE_ENV=production)
        production_like = is_production_like()

        # Check for empty/blank credentials in production-like environments
        if v is None or v.strip() == "":
            if production_like:
                raise ValueError(
                    f"Empty or blank credential for {info.field_name} in {env} environment. "
                    f"Please set real credentials."
                )
            return v

        # Check for dummy patterns in production-like environments
        if production_like:
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
