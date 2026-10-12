# apps/backend/app/main.py
import os
import sys
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from pathlib import Path
from typing import Any
import logging

# Add the app directory to sys.path if needed
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

# Get the path to the .env file and load it first. The real environment takes
# precedence over .env (no override): a stray .env on a server must never
# clobber deployment-set variables like ENVIRONMENT/SKIP_AUTH (issue #149).
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)


# Configure logging + error tracking (issue #273). configure_logging honors
# LOG_LEVEL/LOG_FORMAT (the old basicConfig ignored LOG_LEVEL) and quiets noisy
# AWS/HTTP libraries; init_sentry is a no-op unless SENTRY_DSN is set. Both run at
# import so startup logs/errors are captured.
from app.observability import configure_logging, init_sentry

configure_logging()
init_sentry()

logger = logging.getLogger(__name__)

from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from app.middleware.api_version import APIVersionMiddleware
from app.middleware.body_size_limit import BodySizeLimitMiddleware
from app.middleware.error_handlers import RequestIDMiddleware, register_error_handlers
from app.middleware.metrics import MetricsMiddleware, get_metrics
from app.billing import stripe_client
from app.billing.enforcement import QuotaRefundMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.upload_cleanup import UnownedUploadCleanupMiddleware
from app.services.rate_limit import build_rate_limit_store
from prometheus_client import CONTENT_TYPE_LATEST
from app.api.routes import (
    ab_testing,
    admin,
    ai_analysis,
    ai_orchestration,
    analytics_result,
    batch_prediction,
    billing,
    billing_webhook,
    cache,
    column_stats,
    data_issues,
    data_processing,
    datasets,
    feature_engineering,
    feature_store,
    features,
    feedback,
    health,
    model_export,
    model_training,
    models,
    monitoring,
    onboarding,
    plot,
    production,
    secure_upload,
    transformations,
    upload,
    user_data,
    versions,
    visualizations,
    workflows,
)
from app.services.api_documentation import published_spec
from app.auth.nextauth_auth import SKIP_AUTH, require_admin
from app.config import current_signup_mode, get_environment, settings, is_production_like
from app.models.registry import DOCUMENT_MODELS
from app.utils.ai_summary import initialize_openai_client
from app.services.redis_cache import init_cache, cleanup_cache


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: state the auth mode unambiguously (issue #149)
    logger.info(
        "Auth mode: %s (environment=%s)",
        "BYPASSED via SKIP_AUTH" if SKIP_AUTH else "ENFORCED (NextAuth JWT)",
        get_environment(),
    )
    # Signup mode (#768): "open" is a deliberate value, so it is said out loud.
    signup_mode = current_signup_mode()
    if signup_mode == "open":
        logger.warning("Signup mode: OPEN — any OAuth account may sign up (SIGNUP_MODE=open)")
    else:
        logger.info("Signup mode: invite (INVITE_ALLOWLIST only)")

    # Billing configuration, stated the same way (issue #457). Running with no
    # Stripe keys is supported (ADR-002) and silent, which is how staging shipped
    # with billing inert and nothing noticed. The warning distinguishes "billing is
    # off" from "checkout is live but cannot entitle anyone", because those call for
    # opposite reactions.
    billing_warning = stripe_client.configuration_warning()
    if billing_warning is None:
        logger.info("Billing: Stripe configured")
    else:
        logger.warning("Billing: %s", billing_warning)

    # Connect to DB (single place, all models via the canonical registry)
    mongo_uri = os.getenv("MONGODB_URI")
    db_name = os.getenv("MONGODB_DB")
    if not db_name:
        raise RuntimeError("MONGODB_DB environment variable is not set")
    client: AsyncIOMotorClient[Any] = AsyncIOMotorClient(mongo_uri)
    await init_beanie(
        database=client[db_name],
        document_models=DOCUMENT_MODELS,
    )

    # Fail fast on a missing/unwritable S3 bucket — but only in a production-like
    # environment, so dev/test (mock S3) and CI stay unaffected (#495). A refused
    # boot beats writing to a guessed or wrong bucket, and it catches a broken
    # credential rotation (P1.33).
    if is_production_like():
        from app.services.s3_service import s3_service

        s3_service.verify_bucket_writable()

    # Initialize OpenAI client
    initialize_openai_client()

    # Initialize Redis cache
    await init_cache()

    # Build the rate-limit store (Redis when configured, else in-memory). Exposed
    # on app.state so RateLimitMiddleware can resolve it per request (#151).
    app.state.rate_limit_store = build_rate_limit_store(settings.REDIS_URL)

    # Stale-job recovery (#484): reap jobs orphaned by a prior restart/crash so
    # they don't sit RUNNING forever holding quota. Heartbeat-based + atomically
    # claimed, so it is safe across the 2 gunicorn workers and never reaps a live
    # job. Sweep once on startup, then periodically. A reaper failure must never
    # block startup or crash the loop.
    import asyncio

    from app.services.job_reaper import JOB_REAPER_INTERVAL_SECONDS, reap_stale_jobs

    try:
        startup_summary = await reap_stale_jobs()
        logger.info(
            "stale-job reaper (startup): recovered %d job(s)", startup_summary.total
        )
    except Exception:
        logger.exception("stale-job reaper failed on startup")

    async def _reaper_loop() -> None:
        while True:
            await asyncio.sleep(JOB_REAPER_INTERVAL_SECONDS)
            try:
                await reap_stale_jobs()
            except Exception:
                logger.exception("stale-job reaper loop iteration failed")

    app.state.reaper_task = asyncio.create_task(_reaper_loop())

    yield

    # Stop the background reaper first.
    reaper_task = getattr(app.state, "reaper_task", None)
    if reaper_task is not None:
        reaper_task.cancel()
        try:
            await reaper_task
        except (asyncio.CancelledError, Exception):
            pass

    # Cleanup
    # Drain any in-flight fire-and-forget API-key usage writes before the Mongo
    # client closes, so a graceful shutdown doesn't drop pending $inc/$set (#279).
    from app.api.routes.production import flush_usage_tracking

    await flush_usage_tracking()
    client.close()
    await cleanup_cache()
    store = getattr(app.state, "rate_limit_store", None)
    if store is not None and hasattr(store, "close"):
        await store.close()


# ✅ Create the app only once
app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# Default so the attribute exists before lifespan runs (middleware resolves the
# real store from app.state per request; None ⇒ fail open). See lifespan above.
app.state.rate_limit_store = None

# ✅ Rate limiting (#151). Added FIRST so it is the innermost middleware — it runs
# just before the route handler and short-circuits over-budget requests, while the
# CORS middleware (added next) stays outermost and still decorates the 429 with
# CORS headers so browsers can read it.
app.add_middleware(RateLimitMiddleware)
# Outside RateLimitMiddleware in registration order, so it wraps the routes and
# sees the final status of anything that reserved quota (#368).
app.add_middleware(QuotaRefundMiddleware)
# Beside the refund, for the same reason: a request that fails after writing an S3
# object deletes what no document ended up owning (#735).
app.add_middleware(UnownedUploadCleanupMiddleware)

# ✅ Upload byte cap (#270). Added before CORS so it stays inner and CORS still
# decorates the 413; rejects an oversized Content-Length before the multipart
# parser spools the body. Pairs with nginx client_max_body_size (edge) and the
# in-route read_upload_capped (memory bound).
app.add_middleware(BodySizeLimitMiddleware)

# ✅ Apply CORS to the correct app instance
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Apply API versioning middleware
app.add_middleware(APIVersionMiddleware)

# ✅ Apply Prometheus metrics middleware
app.add_middleware(MetricsMiddleware)

# ✅ Request-id stamping (#269). Added last ⇒ outermost, so every request gets
# an id before any inner middleware/handler runs and it can be echoed on every
# response (including sanitized 5xx errors) for log correlation.
app.add_middleware(RequestIDMiddleware)

# ✅ Sanitizing exception handlers (#269): generic {detail, request_id} on 5xx,
# full detail logged server-side; safe 4xx validation text passes through.
register_error_handlers(app)

# ✅ Include routers
# Health check routes at root level (no version prefix)
app.include_router(health.router, tags=["health"])
# Liveness ONLY under /api/v1 (#479): the browser reaches the backend through
# nginx's /api/ proxy, so the admin widget needs a versioned liveness path — but
# NOT /health/ready, which does per-request outbound work (#503).
app.include_router(
    health.liveness_router, prefix=settings.API_V1_STR, tags=["health"]
)

app.include_router(
    upload.router, prefix=f"{settings.API_V1_STR}/upload", tags=["upload"]
)
app.include_router(
    secure_upload.router, prefix=f"{settings.API_V1_STR}/upload", tags=["upload"]
)
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
    models.router, prefix=f"{settings.API_V1_STR}/models", tags=["models"]
)
app.include_router(
    visualizations.router,
    prefix=f"{settings.API_V1_STR}/visualizations",
    tags=["visualizations"],
)
app.include_router(
    column_stats.router,
    prefix=f"{settings.API_V1_STR}/column_stats",
    tags=["column_stats"],
)
app.include_router(
    data_processing.router,
    prefix=f"{settings.API_V1_STR}/data",
    tags=["data_processing"],
)
app.include_router(
    ai_analysis.router,
    prefix=f"{settings.API_V1_STR}/ai",
    tags=["ai_analysis"],
)
app.include_router(
    ai_orchestration.router,
    prefix=f"{settings.API_V1_STR}/ai",
    tags=["ai_orchestration"],
)
app.include_router(
    model_training.router,
    prefix=f"{settings.API_V1_STR}/ml",
    tags=["model_training"],
)
app.include_router(
    production.router,
    prefix=f"{settings.API_V1_STR}",
    tags=["production"],
)
app.include_router(
    monitoring.router,
    prefix=f"{settings.API_V1_STR}",
    tags=["monitoring"],
)
app.include_router(
    ab_testing.router,
    prefix=f"{settings.API_V1_STR}",
    tags=["ab-testing"],
)
app.include_router(
    batch_prediction.router,
    prefix=f"{settings.API_V1_STR}",
    tags=["batch-prediction"],
)
app.include_router(
    model_export.router,
    prefix=f"{settings.API_V1_STR}",
    tags=["model-export"],
)
app.include_router(
    onboarding.router,
    prefix=f"{settings.API_V1_STR}/onboarding",
    tags=["onboarding"],
)
app.include_router(
    feedback.router,
    prefix=f"{settings.API_V1_STR}/feedback",
    tags=["feedback"],
)
app.include_router(
    cache.router,
    prefix=f"{settings.API_V1_STR}/cache",
    tags=["cache"],
)
app.include_router(
    transformations.router,
    prefix=f"{settings.API_V1_STR}/transformations",
    tags=["transformations"],
)
app.include_router(
    # Was registered only on an aggregator that nothing attached to the app (removed in
    # #530), so the whole feature 404'd (#471). tests/test_api/test_every_router_is_mounted.py
    # fails on any route module that is not mounted here.
    data_issues.router,
    prefix=f"{settings.API_V1_STR}/data-issues",
    tags=["data-issues"],
)
app.include_router(
    versions.router,
    prefix=f"{settings.API_V1_STR}",
    tags=["versioning"],
)
app.include_router(
    datasets.router,
    prefix=f"{settings.API_V1_STR}",
    tags=["datasets"],
)
app.include_router(
    feature_engineering.router,
    prefix=f"{settings.API_V1_STR}",
    tags=["feature-engineering"],
)
app.include_router(
    features.router,
    prefix=f"{settings.API_V1_STR}",
    tags=["feature-builder"],
)
app.include_router(
    feature_store.router,
    prefix=f"{settings.API_V1_STR}/feature-store",
    tags=["feature-store"],
)
app.include_router(
    workflows.router,
    prefix=f"{settings.API_V1_STR}",
    tags=["workflows"],
)
# Deliberately OUTSIDE API_V1_STR. RateLimitMiddleware limits everything under
# /api/v1 and buckets unauthenticated callers by IP — and Stripe delivers every
# event for every tenant from a small set of IPs, so a burst would 429, Stripe
# would retry, and the retries would bucket too. A webhook is also not a versioned
# public API surface: it is Stripe's endpoint, already excluded from the OpenAPI
# schema. Protection here is signature verification plus the body-size limit, not
# an IP budget (#367).
app.include_router(
    billing.router,
    prefix=f"{settings.API_V1_STR}/billing",
    tags=["billing"],
)
app.include_router(
    billing_webhook.router,
    prefix="/webhooks/stripe",
    tags=["billing"],
)
app.include_router(admin.router, prefix=f"{settings.API_V1_STR}/admin", tags=["admin"])


# AGPL-3.0 §13: a network-deployed service must offer its users the
# Corresponding Source. This is the machine-readable half of that offer
# (the UI half is the frontend SiteFooter link).
SOURCE_CODE_URL = "https://github.com/frankbria/narrative-modeling-app"


@app.get("/")
async def root():
    return {
        "message": "Welcome to the Narrative Modeling API",
        "license": "AGPL-3.0-or-later",
        "source_code": SOURCE_CODE_URL,
        "source_offer": (
            "This program is free software licensed under the GNU AGPL v3. "
            "In accordance with section 13, the complete corresponding source "
            f"code is available at {SOURCE_CODE_URL}."
        ),
    }


@app.get("/metrics", dependencies=[Depends(require_admin)])
async def metrics():
    """
    Prometheus metrics endpoint, for ``ADMIN_EMAILS`` identities only (#768).

    Returns metrics in Prometheus text exposition format for scraping. It sits
    outside ``/api/v1`` and the rate limiter; everyone else gets a 404.
    """
    return Response(content=get_metrics(), media_type=CONTENT_TYPE_LATEST)


# The published API description (#512): FastAPI's generated document, which is
# the live route table.
@app.get(f"{settings.API_V1_STR}/docs/openapi.json", tags=["documentation"])
async def get_published_openapi():
    """The OpenAPI document for this instance: every route it serves, what each
    requires, and the rate limits it enforces."""
    return published_spec(app)


@app.get(f"{settings.API_V1_STR}/docs/openapi.yaml", tags=["documentation"])
async def get_published_openapi_yaml():
    """The same document as YAML."""
    import yaml

    spec = published_spec(app)
    yaml_content = yaml.dump(spec, default_flow_style=False, sort_keys=False)
    return Response(content=yaml_content, media_type="application/x-yaml")
