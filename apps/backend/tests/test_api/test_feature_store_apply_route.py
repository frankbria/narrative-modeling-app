"""#959: POST /feature-store/features/{id}/apply answers what the service did.

The service is stood in for here; what it does, and the wording of its answer, is
tested in tests/test_services/test_feature_store_service.py.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.exceptions import NotFoundError

pytestmark = pytest.mark.asyncio

ROUTE = "/api/v1/feature-store/features/f1/apply"
SERVICE = "app.api.routes.feature_store.FeatureStoreService.apply_feature"


async def test_the_route_returns_the_services_answer(async_authorized_client, setup_database):
    answer = {"success": True, "feature_id": "f1", "dataset_id": "d1", "output_column": "ratio",
              "message": "Feature validated against the dataset and recorded as applicable to it; no column was added."}
    with patch(SERVICE, AsyncMock(return_value=answer)):
        response = await async_authorized_client.post(ROUTE, json={"dataset_id": "d1"})

    assert response.status_code == 200
    assert response.json() == answer


async def test_an_unknown_feature_is_a_404(async_authorized_client, setup_database):
    with patch(SERVICE, AsyncMock(side_effect=NotFoundError(resource_type="Feature", resource_id="f1"))):
        response = await async_authorized_client.post(ROUTE, json={"dataset_id": "d1"})

    assert response.status_code == 404
