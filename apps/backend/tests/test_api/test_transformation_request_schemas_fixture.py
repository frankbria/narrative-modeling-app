"""The frontend's transformation request schemas are the API's own (#855).

The Prepare stage posted `{dataset_id, transformations: [{type, parameters}]}` to
`/transformations/preview` and `/apply`, and its recipes to `/recipes/save`; no route
accepted any of them (422, 422, 404), and the suite never noticed because nothing tied
the UI's payloads to the API. The frontend's `pipelineApi.contract.test.ts` validates
every payload it builds against this fixture, and this test keeps the fixture equal to
the request models the routes actually declare.

Regenerate after a deliberate request-model change:
    UPDATE_FIXTURES=1 PYTHONPATH=. uv run pytest tests/test_api/test_transformation_request_schemas_fixture.py
"""

import json
import os
from pathlib import Path

from app.schemas.transformation import (
    RecipeCreateRequest,
    TransformationApplyRequest,
    TransformationPreviewRequest,
)

FIXTURE = (
    Path(__file__).resolve().parents[4]
    / "apps/frontend/__tests__/fixtures/transformationRequestSchemas.json"
)

# Each request model the Prepare stage posts, by the route it posts it to.
MODELS = {
    "POST /transformations/preview": TransformationPreviewRequest,
    "POST /transformations/apply": TransformationApplyRequest,
    "POST /transformations/recipes": RecipeCreateRequest,
}


def test_the_frontend_fixture_is_the_api_request_schemas():
    schemas = {route: model.model_json_schema() for route, model in MODELS.items()}
    if os.getenv("UPDATE_FIXTURES"):
        FIXTURE.write_text(json.dumps(schemas, indent=2, sort_keys=True) + "\n")
    assert json.loads(FIXTURE.read_text()) == json.loads(json.dumps(schemas)), (
        "regenerate the fixture: a transformation request model changed"
    )


def test_the_routes_still_take_these_models():
    """The fixture is keyed by route; a route that stopped taking its model would
    leave the frontend validating against a schema nothing reads."""
    from app.main import app

    # The OpenAPI document, not app.routes: on FastAPI 0.139 routers are lazy
    # wrappers and app.routes is not flat (CLAUDE.md, #459).
    paths = app.openapi()["paths"]
    for route, model in MODELS.items():
        method, path = route.split(" ")
        body = paths[f"/api/v1{path}"][method.lower()]["requestBody"]["content"]["application/json"]
        assert body["schema"]["$ref"].rsplit("/", 1)[-1] == model.__name__, route


REGISTRY_FIXTURE = FIXTURE.with_name("availableTransformations.json")


def test_the_frontend_registry_fixture_is_the_available_list():
    """The pipeline's sidebar and config dialog read GET /transformations/available; its
    tests serve this captured list, so they cannot advertise a type the engine lacks."""
    from app.services.transformation_engine.transformation_engine import (
        available_transformations,
    )

    available = json.loads(json.dumps(available_transformations(), default=str))
    if os.getenv("UPDATE_FIXTURES"):
        REGISTRY_FIXTURE.write_text(json.dumps(available, indent=2, sort_keys=True) + "\n")
    assert json.loads(REGISTRY_FIXTURE.read_text()) == available, "regenerate the fixture"
