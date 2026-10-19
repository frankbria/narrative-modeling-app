"""#1102: the HTTP status each bulk-apply failure maps to."""
import pytest

from app.api.routes.transformations import _bulk_apply_http_error
from app.services.exceptions import (
    NotFoundError,
    OperationError,
    PermissionDeniedError,
    ValidationError,
)


@pytest.mark.parametrize(
    ("error", "status", "detail"),
    [
        (NotFoundError("Dataset not found"), 404, "Dataset not found"),
        (ValidationError("No columns"), 400, "No columns"),
        (OperationError("Maximum concurrent jobs reached"), 429, "Maximum concurrent jobs reached"),
        (OperationError("Could not start"), 400, "Could not start"),
        (ValueError("bad type"), 400, "bad type"),
        (PermissionDeniedError("secret internals"), 500, "Internal server error"),
        (RuntimeError("secret internals"), 500, "Internal server error"),
    ],
)
def test_each_failure_maps_to_its_status(error, status, detail):
    mapped = _bulk_apply_http_error(error)

    assert (mapped.status_code, mapped.detail) == (status, detail)


@pytest.mark.asyncio
async def test_the_route_answers_each_failure_with_its_status(setup_database, async_authorized_client):
    url = "/api/v1/transformations/datasets/not-there/bulk-apply"
    body = {"selected_columns": ["a"], "transformation_type": "fill_missing"}

    missing = await async_authorized_client.post(url, json=body)

    assert missing.status_code == 404, missing.text
