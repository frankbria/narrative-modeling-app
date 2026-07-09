"""
Integration tests for the transformation preview endpoint (issue #268).

Previously these tests asserted permissive status sets (``in [200, 404, 422]``)
that accepted the failure case, so a broken preview endpoint stayed green. They
now assert the EXACT status each request produces and exercise the real 200
path against a seeded dataset (with S3 mocked), so the endpoint's contract is
genuinely enforced:

  * empty ``transformation_steps``        -> 400 (route guard)
  * invalid ``transformation_type``       -> 422 (pydantic field validator)
  * valid request, unknown dataset        -> 404 (NotFoundError)
  * valid request, seeded dataset + S3    -> 200 with a real preview body

Note: ``preview_rows`` has no schema bound, so out-of-range values are NOT
rejected — they succeed. That real (unbounded) contract is documented by the
boundary test rather than asserted as a rejection.
"""

from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest

from app.models.dataset import DatasetMetadata

TEST_USER_ID = "test_user_123"  # matches async_authorized_client's auth override
S3_PATCH_TARGET = "app.services.transformation_engine.data_utils.get_dataframe_from_s3"


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "id": range(1, 101),
            "age": [25 + i % 30 for i in range(100)],
            "salary": [50000.0 + i * 100 for i in range(100)],
        }
    )


async def _seed_dataset(dataset_id: str) -> DatasetMetadata:
    """Insert a DatasetMetadata owned by the test user so the preview endpoint's
    ownership lookup succeeds and the (S3-mocked) 200 path runs."""
    dataset = DatasetMetadata(
        user_id=TEST_USER_ID,
        dataset_id=dataset_id,
        filename=f"{dataset_id}.csv",
        original_filename=f"{dataset_id}.csv",
        file_type="csv",
        file_path=f"datasets/{TEST_USER_ID}/{dataset_id}.csv",
        s3_url=f"s3://test-bucket/datasets/{TEST_USER_ID}/{dataset_id}.csv",
        num_rows=100,
        num_columns=3,
        columns=["id", "age", "salary"],
    )
    await dataset.insert()
    return dataset


@pytest.mark.integration
class TestPreviewAPIValidation:
    """Exact-status validation tests for POST /api/v1/transformations/preview."""

    @pytest.mark.asyncio
    async def test_preview_rejects_empty_transformation_steps(self, async_authorized_client):
        """Empty transformation_steps -> exactly 400 (route guard, not accepted)."""
        response = await async_authorized_client.post(
            "/api/v1/transformations/preview",
            json={
                "dataset_id": "test_dataset_123",
                "transformation_steps": [],
                "preview_rows": 100,
            },
        )
        assert response.status_code == 400
        assert "no transformation steps" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_preview_rejects_invalid_transformation_type(self, async_authorized_client):
        """Unknown transformation_type -> exactly 422 (pydantic field validator)."""
        response = await async_authorized_client.post(
            "/api/v1/transformations/preview",
            json={
                "dataset_id": "test_dataset_123",
                "transformation_steps": [
                    {"transformation_type": "invalid_transform_type", "column": "age"}
                ],
                "preview_rows": 100,
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_preview_unknown_dataset_returns_404(
        self, async_authorized_client, setup_database
    ):
        """A structurally valid request for a non-existent dataset -> exactly 404.

        This is the case the permissive ``in [200, 404, 422]`` set was hiding: a
        valid request must NOT silently succeed against a missing dataset.
        """
        response = await async_authorized_client.post(
            "/api/v1/transformations/preview",
            json={
                "dataset_id": "does_not_exist",
                "transformation_steps": [
                    {"transformation_type": "drop_missing", "column": "age"}
                ],
                "preview_rows": 100,
            },
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_preview_valid_request_succeeds(
        self, async_authorized_client, setup_database
    ):
        """Valid request + seeded dataset + mocked S3 -> exactly 200 with a real body."""
        await _seed_dataset("preview_ok_1")

        with patch(S3_PATCH_TARGET, new=AsyncMock(return_value=_sample_df())):
            response = await async_authorized_client.post(
                "/api/v1/transformations/preview",
                json={
                    "dataset_id": "preview_ok_1",
                    "transformation_steps": [
                        {"transformation_type": "drop_missing", "column": "age"}
                    ],
                    "preview_rows": 100,
                },
            )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        # A real preview returns sample rows and does not report an error.
        assert body["preview_data"] is not None
        assert body["error"] is None

    @pytest.mark.asyncio
    async def test_preview_accepts_extra_steps_but_previews_only_the_first(
        self, async_authorized_client, setup_database
    ):
        """A request with multiple steps is accepted (200), but the route
        previews ONLY transformation_steps[0] (transformations.py:98,118) — the
        second step is not applied. This documents the real contract rather than
        implying every step is previewed.
        """
        await _seed_dataset("preview_ok_2")

        with patch(S3_PATCH_TARGET, new=AsyncMock(return_value=_sample_df())):
            response = await async_authorized_client.post(
                "/api/v1/transformations/preview",
                json={
                    "dataset_id": "preview_ok_2",
                    "transformation_steps": [
                        {"transformation_type": "drop_missing", "column": "age"},
                        {
                            "transformation_type": "outlier_removal",
                            "column": "salary",
                            "parameters": {"method": "iqr"},
                        },
                    ],
                    "preview_rows": 100,
                },
            )

        assert response.status_code == 200
        assert response.json()["success"] is True

    @pytest.mark.asyncio
    @pytest.mark.parametrize("preview_rows", [5, 10, 1000, 2000])
    async def test_preview_rows_values_are_accepted(
        self, async_authorized_client, setup_database, preview_rows
    ):
        """``preview_rows`` is unbounded in the schema, so 5 and 2000 are NOT
        rejected — each yields a successful preview against a seeded dataset.

        This documents the real (unbounded) contract with an exact 200 instead
        of the old permissive set that accepted a phantom 422.
        """
        await _seed_dataset(f"preview_rows_{preview_rows}")

        with patch(S3_PATCH_TARGET, new=AsyncMock(return_value=_sample_df())):
            response = await async_authorized_client.post(
                "/api/v1/transformations/preview",
                json={
                    "dataset_id": f"preview_rows_{preview_rows}",
                    "transformation_steps": [
                        {"transformation_type": "drop_missing", "column": "id"}
                    ],
                    "preview_rows": preview_rows,
                },
            )

        assert response.status_code == 200
        assert response.json()["success"] is True
