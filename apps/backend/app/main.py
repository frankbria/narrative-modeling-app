# apps/backend/app/main.py
import os
import sys
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from pathlib import Path
import logging

# Add the app directory to sys.path if needed
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

# Get the path to the .env file and load it first. The real environment takes
# precedence over .env (no override): a stray .env on a server must never
# clobber deployment-set variables like ENVIRONMENT/SKIP_AUTH (issue #149).
env_path = Path(__file__).resolve().parent.parent / ".env"
print(f"Loading .env file from: {env_path}")
load_dotenv(dotenv_path=env_path)


# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# Suppress AWS logging
logging.getLogger("boto3").setLevel(logging.WARNING)
logging.getLogger("botocore").setLevel(logging.WARNING)
logging.getLogger("s3transfer").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from app.middleware.api_version import APIVersionMiddleware
from app.middleware.metrics import MetricsMiddleware, get_metrics
from prometheus_client import CONTENT_TYPE_LATEST
from app.api.routes import (
    health,
    user_data,
    analytics_result,
    plot,
    models,
    upload,
    secure_upload,
    store,
    visualizations,
    column_stats,
    s3,
    data_processing,
    ai_analysis,
    model_training,
    production,
    monitoring,
    ab_testing,
    batch_prediction,
    model_export,
    onboarding,
    cache,
    transformations,
    versions,
    datasets,
    feature_engineering,
    features,
    feature_store,
    workflows,
)
from app.services.api_documentation import APIDocumentationService
from app.auth.nextauth_auth import SKIP_AUTH
from app.config import get_environment, settings
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

    # Connect to DB (single place, all models via the canonical registry)
    mongo_uri = os.getenv("MONGODB_URI")
    db_name = os.getenv("MONGODB_DB")
    client = AsyncIOMotorClient(mongo_uri)
    await init_beanie(
        database=client[db_name],
        document_models=DOCUMENT_MODELS,
    )

    # Initialize OpenAI client
    initialize_openai_client()

    # Initialize Redis cache
    await init_cache()

    yield

    # Cleanup
    client.close()
    await cleanup_cache()


# ✅ Create the app only once
app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# Initialize API documentation service
# Note: Don't override app.openapi() as it causes recursion.
# The enhanced spec is available at /api/v1/docs/openapi.json
doc_service = APIDocumentationService(app)

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

# ✅ Include routers
# Health check routes at root level (no version prefix)
app.include_router(health.router, tags=["health"])

app.include_router(
    upload.router, prefix=f"{settings.API_V1_STR}/upload", tags=["upload"]
)
app.include_router(
    secure_upload.router, prefix=f"{settings.API_V1_STR}/upload", tags=["upload"]
)
app.include_router(store.router, prefix=settings.API_V1_STR, tags=["store"])
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
    s3.router,
    prefix=f"{settings.API_V1_STR}/s3",
    tags=["s3"],
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


@app.get("/")
async def root():
    return {"message": "Welcome to the Narrative Modeling API"}


@app.get("/metrics")
async def metrics():
    """
    Prometheus metrics endpoint.

    Returns metrics in Prometheus text exposition format for scraping.
    """
    return Response(content=get_metrics(), media_type=CONTENT_TYPE_LATEST)


# API Documentation endpoints
@app.get(f"{settings.API_V1_STR}/docs/openapi.json", tags=["documentation"])
async def get_enhanced_openapi():
    """
    Get enhanced OpenAPI specification with security schemes and examples.

    Returns the complete API specification including:
    - All endpoints with request/response schemas
    - Authentication schemes (JWT Bearer, API Key)
    - Error response examples
    - Comprehensive descriptions and metadata
    """
    return doc_service.generate_openapi_spec()


@app.get(f"{settings.API_V1_STR}/docs/openapi.yaml", tags=["documentation"])
async def get_enhanced_openapi_yaml():
    """
    Get enhanced OpenAPI specification in YAML format.

    Returns the same specification as the JSON endpoint but in YAML format
    for better readability and certain tooling compatibility.
    """
    import yaml
    spec = doc_service.generate_openapi_spec()
    yaml_content = yaml.dump(spec, default_flow_style=False, sort_keys=False)
    return Response(content=yaml_content, media_type="application/x-yaml")


@app.get(f"{settings.API_V1_STR}/docs/clients/{{language}}", tags=["documentation"])
async def get_client_library(language: str):
    """
    Get client library code for the specified language.

    Supported languages:
    - python: Complete Python client with authentication and error handling
    - javascript: JavaScript/TypeScript client for Node.js and browsers
    - curl: cURL examples for all major endpoints

    Args:
        language: Programming language for the client library

    Returns:
        Source code for the client library

    Raises:
        404: If the language is not supported
    """
    from fastapi import HTTPException

    libraries = doc_service.generate_client_libraries()
    if language not in libraries:
        raise HTTPException(
            status_code=404,
            detail=f"Language '{language}' not supported. Available: {', '.join(libraries.keys())}"
        )
    return Response(content=libraries[language], media_type="text/plain")


@app.get(f"{settings.API_V1_STR}/docs/integrations/{{framework}}", tags=["documentation"])
async def get_integration_example(framework: str):
    """
    Get integration example for the specified framework.

    Supported frameworks:
    - jupyter: Jupyter notebook integration example
    - colab: Google Colab integration example
    - streamlit: Streamlit app integration example
    - flask: Flask application integration example

    Args:
        framework: Framework for the integration example

    Returns:
        Source code for the integration example

    Raises:
        404: If the framework is not supported
    """
    from fastapi import HTTPException

    examples = doc_service.generate_integration_examples()
    if framework not in examples:
        raise HTTPException(
            status_code=404,
            detail=f"Framework '{framework}' not supported. Available: {', '.join(examples.keys())}"
        )
    return Response(content=examples[framework], media_type="text/plain")


@app.get(f"{settings.API_V1_STR}/docs/postman", tags=["documentation"])
async def get_postman_collection():
    """
    Get Postman collection for API testing.

    Returns a complete Postman collection including:
    - All API endpoints with examples
    - Authentication configuration
    - Environment variables
    - Pre-request scripts for token management

    The collection can be imported directly into Postman for interactive testing.
    """
    return doc_service.generate_postman_collection()
