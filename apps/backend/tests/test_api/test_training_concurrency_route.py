"""POST /api/v1/ml/train returns 429 when the caller is at their concurrent
training cap, and the ``training_runs`` unit the quota dependency reserved is
refunded (#498). Mirrors the batch equivalent (test_batch_concurrency_route.py).
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.billing import metering
from app.services.training_admission import TrainingConcurrencyLimitError

pytestmark = pytest.mark.asyncio

TEST_USER = "test_user_123"


async def test_over_cap_is_429_and_refunds_the_reserved_unit(
    async_authorized_client, setup_database
):
    from app.models.training_job import TrainingJob
    from app.models.user_data import UserData

    dataset = UserData(
        user_id=TEST_USER,
        filename="demo.csv",
        original_filename="demo.csv",
        s3_url="s3://test-bucket/demo.csv",
        num_rows=10,
        num_columns=2,
        data_schema=[],
    )
    await dataset.insert()
    before = await metering.usage_for(TEST_USER, "training_runs")
    try:
        # The admission check raises as if the tenant were already at their cap.
        with patch(
            "app.api.routes.model_training.enforce_training_per_user_cap",
            new_callable=AsyncMock,
            side_effect=TrainingConcurrencyLimitError(2, 2),
        ):
            resp = await async_authorized_client.post(
                "/api/v1/ml/train",
                json={"dataset_id": str(dataset.id), "target_column": "target"},
            )
        assert resp.status_code == 429, resp.text
        assert "wait for one to finish" in resp.json()["detail"]
        # No job should have been created, and the reserved unit is refunded.
        assert await TrainingJob.find(TrainingJob.dataset_id == str(dataset.id)).count() == 0
        assert await metering.usage_for(TEST_USER, "training_runs") == before
    finally:
        await TrainingJob.find(TrainingJob.dataset_id == str(dataset.id)).delete()
        await dataset.delete()
