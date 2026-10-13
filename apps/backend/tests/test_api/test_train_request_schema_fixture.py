"""The frontend's training request schema is the API's own (#969).

The Model Training stage builds `POST /ml/train`'s body by hand, and the request
models forbid undeclared fields, so a knob renamed on one side is a 422 for every
run. The frontend's `trainRequest.contract.test.ts` validates the bodies it builds
against this fixture, and this test keeps the fixture equal to the model the route
declares, the way the Prepare stage's are held (#855).

Regenerate after a deliberate request-model change:
    UPDATE_FIXTURES=1 PYTHONPATH=. uv run pytest tests/test_api/test_train_request_schema_fixture.py
"""

import json
import os
from pathlib import Path

from app.api.routes.model_training import TrainModelRequest

FIXTURE = (
    Path(__file__).resolve().parents[4]
    / "apps/frontend/__tests__/fixtures/trainModelRequestSchema.json"
)


def _portable_schema() -> dict:
    """The request schema, less the one bound that is a fact about the machine:
    ``n_jobs`` is capped at the host's core count, so its ``maximum`` is 8 on one
    box and 4 on the next, and a fixture holding it passes only where it was written."""
    schema = TrainModelRequest.model_json_schema()
    for option in schema["$defs"]["TuningConfigRequest"]["properties"]["n_jobs"]["anyOf"]:
        option.pop("maximum", None)
    return schema


def test_the_frontend_fixture_is_the_api_request_schema():
    schema = _portable_schema()
    if os.getenv("UPDATE_FIXTURES"):
        FIXTURE.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
    assert json.loads(FIXTURE.read_text()) == json.loads(json.dumps(schema)), (
        "regenerate the fixture: the training request model changed"
    )


def test_the_route_still_takes_this_model():
    from app.main import app

    # The OpenAPI document, not app.routes: routers are lazy wrappers (#459).
    body = app.openapi()["paths"]["/api/v1/ml/train"]["post"]["requestBody"]["content"]["application/json"]

    assert body["schema"]["$ref"].rsplit("/", 1)[-1] == TrainModelRequest.__name__
