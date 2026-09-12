"""POST /api/v1/batch/jobs returns 429 when the caller is at their concurrent-job
cap, and the units the admission dependency reserved are refunded (#515).

The batch HTTP surface otherwise has no route tests (#516); this one covers the
concurrency mapping only.
"""

import io
from unittest.mock import AsyncMock, patch

import pytest

from app.billing import metering
from app.services.batch_prediction import BatchConcurrencyLimitError

pytestmark = pytest.mark.asyncio

TEST_USER = "test_user_123"


def _csv(rows: int = 3) -> dict:
    body = "age\n" + "\n".join(str(i) for i in range(rows)) + "\n"
    return {"file": ("in.csv", io.BytesIO(body.encode()), "text/csv")}


async def test_over_cap_is_429_and_refunds_the_reserved_units(async_authorized_client, setup_database):
    before = await metering.usage_for(TEST_USER, "predictions")
    with patch(
        "app.api.routes.batch_prediction.batch_service.create_batch_prediction_job",
        new_callable=AsyncMock,
        side_effect=BatchConcurrencyLimitError(3, 3),
    ):
        resp = await async_authorized_client.post(
            "/api/v1/batch/jobs", files=_csv(3), data={"model_id": "model_123"}
        )
    assert resp.status_code == 429, resp.text
    assert "wait for one to finish" in resp.json()["detail"]
    # The refund middleware returns everything reserved on a >= 400 response.
    assert await metering.usage_for(TEST_USER, "predictions") == before
