"""delete_model must never orphan an S3 artifact (#521).

Before #521, delete_model swallowed an S3 delete failure and deleted the Mongo row
anyway — leaving the artifact in the bucket with nothing referencing it (storage
cost + a GDPR erasure that reports success over surviving customer-derived data).
Now an S3 failure raises ModelArtifactDeletionError and the row is retained.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.ml_model import MLModel
from app.services.model_storage import ModelArtifactDeletionError, ModelStorageService


def _live_s3(svc: ModelStorageService) -> None:
    """Force the real-S3 branch so delete_file is actually exercised, regardless of
    whether the test env has AWS creds (mock mode skips S3 entirely, #521)."""
    svc.s3_service.is_mock_mode = False
    svc.s3_service.s3_client = MagicMock()


async def _seed_model(model_id: str = "del_me", user_id: str = "u1") -> MLModel:
    model = MLModel(
        user_id=user_id,
        dataset_id="ds1",
        model_id=model_id,
        name="m",
        problem_type="binary_classification",
        algorithm="Random Forest",
        target_column="target",
        feature_names=["f1", "f2"],
        cv_score=0.8,
        test_score=0.78,
        training_time=1.0,
        model_size=10,
        n_samples_train=100,
        n_features=2,
        model_path="s3://bucket/models/u1/del_me/model.pkl",
    )
    await model.insert()
    return model


@pytest.mark.asyncio
async def test_s3_failure_does_not_delete_the_mongo_row(setup_database):
    """AC5: an S3 delete failure raises and the MLModel record survives."""
    await _seed_model()
    svc = ModelStorageService()
    _live_s3(svc)
    svc.s3_service.delete_file = AsyncMock(side_effect=RuntimeError("S3 down"))

    with pytest.raises(ModelArtifactDeletionError):
        await svc.delete_model("del_me", "u1")

    # The reference is retained so the orphaned object stays findable.
    assert await MLModel.find_one(MLModel.model_id == "del_me") is not None


@pytest.mark.asyncio
async def test_successful_s3_delete_removes_the_mongo_row(setup_database):
    """The happy path still deletes the row once every artifact is gone."""
    await _seed_model(model_id="ok_del")
    svc = ModelStorageService()
    _live_s3(svc)
    svc.s3_service.delete_file = AsyncMock(return_value=True)

    result = await svc.delete_model("ok_del", "u1")

    assert result is True
    assert await MLModel.find_one(MLModel.model_id == "ok_del") is None


@pytest.mark.asyncio
async def test_mock_mode_deletes_row_without_calling_s3(setup_database):
    """In mock mode (no real AWS) delete_file() raises unconditionally, so S3 is
    skipped entirely and the row is still deleted — the old code only worked here
    because it swallowed that RuntimeError (codex #521)."""
    await _seed_model(model_id="mock_del")
    svc = ModelStorageService()
    svc.s3_service.is_mock_mode = True
    svc.s3_service.delete_file = AsyncMock(side_effect=AssertionError("no S3 in mock mode"))

    assert await svc.delete_model("mock_del", "u1") is True
    assert await MLModel.find_one(MLModel.model_id == "mock_del") is None


@pytest.mark.asyncio
async def test_missing_model_returns_false_without_touching_s3(setup_database):
    """An unknown id is a plain not-found (False), no S3 call, no raise."""
    svc = ModelStorageService()
    svc.s3_service.delete_file = AsyncMock(side_effect=AssertionError("must not be called"))

    assert await svc.delete_model("nope", "u1") is False
