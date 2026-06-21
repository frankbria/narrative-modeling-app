"""Tests for ModelVersioningService lineage helpers (issue #78)."""

from datetime import UTC, datetime, timedelta

import pytest

from app.models.ml_model import MLModel
from app.services.model_versioning_service import (
    capture_environment,
    model_versioning_service,
)

USER = "test_user_123"


def _model(model_id: str, name: str, offset: int) -> MLModel:
    return MLModel(
        user_id=USER,
        dataset_id="ds-lineage",
        model_id=model_id,
        name=name,
        problem_type="regression",
        algorithm="Linear Regression",
        target_column="y",
        feature_names=["a"],
        cv_score=0.5,
        test_score=0.5,
        training_time=1.0,
        model_size=1,
        n_samples_train=10,
        n_features=1,
        model_path="s3://b/m.pkl",
        created_at=datetime.now(UTC) + timedelta(seconds=offset),
    )


@pytest.mark.asyncio
async def test_resolve_parent_chains_to_latest_family_member(setup_database):
    await _model("m1", "Sales", 0).insert()
    await _model("m2", "Sales", 10).insert()
    try:
        # New version's parent = most recent existing family member.
        parent = await model_versioning_service.resolve_parent(USER, "ds-lineage", "Sales")
        assert parent == "m2"
        # First version of a different family has no parent.
        assert (
            await model_versioning_service.resolve_parent(USER, "ds-lineage", "New")
            is None
        )
    finally:
        await MLModel.find(MLModel.user_id == USER).delete()


def test_capture_environment_records_python_and_sklearn():
    env = capture_environment()
    assert "python" in env and env["python"]
    assert "sklearn" in env  # always installed in this project
