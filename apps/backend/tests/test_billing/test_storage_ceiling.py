"""FREE storage ceiling (#768 AC5).

10 uploads × 100 MB per free account, kept forever, with no reclamation. FREE may
hold `PlanLimits.storage_bytes` of datasets plus model artifacts; an upload that
would cross it answers 402 in the same `quota_exceeded` shape the frontend's one
plan-limit dialog already renders (#767), as `storage_mb`.
"""

from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.billing import storage
from app.billing.plans import PLAN_LIMITS
from app.models.ml_model import MLModel
from app.models.subscription import PlanTier, Subscription, SubscriptionStatus
from app.models.user_data import UserData

TEST_USER = "test_user_123"
MB = 1024 * 1024
FREE_LIMIT = PLAN_LIMITS[PlanTier.FREE].storage_bytes


async def _dataset(user_id: str, size: int | None) -> None:
    await UserData(
        user_id=user_id, filename="d.csv", original_filename="d.csv",
        s3_url="s3://b/datasets/x/d.csv", num_rows=1, num_columns=1, data_schema=[],
        file_size=size,
    ).insert()


async def _model(user_id: str, size: int) -> None:
    await MLModel(
        user_id=user_id, dataset_id="ds", model_id=f"m-{size}", name="M",
        problem_type="binary_classification", algorithm="RF", target_column="y",
        feature_names=["f"], cv_score=0.8, test_score=0.8, training_time=1.0,
        model_size=size, n_samples_train=10, n_features=1, model_path="s3://b/m.pkl",
    ).insert()


def test_free_is_capped_and_paid_tiers_are_not():
    assert FREE_LIMIT == 500 * MB
    assert PLAN_LIMITS[PlanTier.PRO].storage_bytes == -1
    assert PLAN_LIMITS[PlanTier.ENTERPRISE].storage_bytes == -1


async def test_stored_bytes_counts_datasets_and_models_of_this_tenant_only(setup_database):
    await _dataset(TEST_USER, 10 * MB)
    await _dataset(TEST_USER, None)  # pre-#768 row: counts as 0
    await _model(TEST_USER, 3 * MB)
    await _dataset("someone-else", 400 * MB)
    await _model("someone-else", 90 * MB)
    assert await storage.stored_bytes(TEST_USER) == 13 * MB


async def test_under_the_ceiling_passes(setup_database):
    await _dataset(TEST_USER, FREE_LIMIT - 2 * MB)
    await storage.enforce_storage_ceiling(TEST_USER, 2 * MB)  # exactly at the cap is fine


async def test_crossing_the_ceiling_is_a_402_in_the_quota_shape(setup_database):
    await _dataset(TEST_USER, FREE_LIMIT - 2 * MB)
    with pytest.raises(HTTPException) as exc:
        await storage.enforce_storage_ceiling(TEST_USER, 3 * MB)
    assert exc.value.status_code == 402
    detail = exc.value.detail
    assert detail["error"] == "quota_exceeded"
    assert detail["metric"] == "storage_mb"
    assert detail["limit"] == 500
    assert detail["used"] == 498
    assert detail["tier"] == "free"
    assert detail["resets_at"] is None  # storage does not roll over
    assert detail["upgrade_available"] is True
    assert "500 MB" in detail["message"]


async def test_a_paid_tenant_is_not_capped(setup_database):
    await Subscription(
        user_id=TEST_USER, plan_tier=PlanTier.PRO, status=SubscriptionStatus.ACTIVE,
    ).insert()
    await _dataset(TEST_USER, 5 * FREE_LIMIT)
    await storage.enforce_storage_ceiling(TEST_USER, 100 * MB)


async def test_secure_upload_is_refused_before_anything_is_stored(
    async_authorized_client, setup_database
):
    """Route level: the 402 lands before the S3 put and the insert, and the
    `uploads` unit the route reserved is refunded by the middleware."""
    from app.billing import metering

    await _dataset(TEST_USER, FREE_LIMIT)
    with patch("app.api.routes.secure_upload.upload_file_to_s3") as put:
        response = await async_authorized_client.post(
            "/api/v1/upload/secure",
            files={"file": ("d.csv", b"a,b\n1,2\n3,4\n", "text/csv")},
        )
    assert response.status_code == 402, response.text
    assert response.json()["detail"]["metric"] == "storage_mb"
    put.assert_not_called()
    assert await UserData.find(UserData.user_id == TEST_USER).count() == 1
    assert await metering.usage_for(TEST_USER, "uploads") == 0


async def test_an_accepted_upload_records_its_size(async_authorized_client, setup_database):
    """The ceiling can only count what the writers record: a successful upload
    stores `file_size`, so the next upload sees it."""
    body = b"a,b\n1,2\n3,4\n"
    with patch(
        "app.api.routes.secure_upload.upload_file_to_s3",
        return_value=(True, f"s3://bucket/datasets/{TEST_USER}/x.csv"),
    ), patch("app.utils.ai_summary.generate_dataset_summary"):
        response = await async_authorized_client.post(
            "/api/v1/upload/secure", files={"file": ("d.csv", body, "text/csv")}
        )
    assert response.status_code == 200, response.text
    assert await storage.stored_bytes(TEST_USER) == len(body)


async def test_the_datasets_upload_twin_records_its_size(setup_database):
    """`/datasets/upload` writes DatasetMetadata and a UserData twin; the twin is
    what the ceiling sums, so it must carry the size."""
    from app.services.dataset_service import DatasetService

    await DatasetService().create_dataset(
        user_id=TEST_USER, dataset_id="ds-size", filename="d.csv", original_filename="d.csv",
        file_type="csv", file_path=f"datasets/{TEST_USER}/d.csv",
        s3_url=f"s3://bucket/datasets/{TEST_USER}/d.csv", file_size=4242,
        num_rows=2, num_columns=2, columns=["a", "b"], data_schema=[],
    )
    assert await storage.stored_bytes(TEST_USER) == 4242
