"""Tests for ModelVersioningService lineage helpers (issue #78)."""

from datetime import UTC, datetime, timedelta

import pytest
from beanie.odm.operators.find.comparison import In

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
        await MLModel.find(In(MLModel.model_id, ["m1", "m2"])).delete()


@pytest.mark.asyncio
async def test_promote_and_get_production_version(setup_database):
    await _model("p1", "Promo", 0).insert()
    await _model("p2", "Promo", 10).insert()
    try:
        # No production version until one is promoted.
        assert (
            await model_versioning_service.get_production_version(
                USER, "ds-lineage", "Promo"
            )
            is None
        )

        promoted, demoted = await model_versioning_service.promote_to_production(
            "p2", USER
        )
        assert promoted.is_production is True
        assert demoted == []
        current = await model_versioning_service.get_production_version(
            USER, "ds-lineage", "Promo"
        )
        assert current is not None and current.model_id == "p2"

        # Re-promoting the current production version is an idempotent no-op.
        again, demoted2 = await model_versioning_service.promote_to_production(
            "p2", USER
        )
        assert again.is_production is True
        assert demoted2 == []
        current = await model_versioning_service.get_production_version(
            USER, "ds-lineage", "Promo"
        )
        assert current.model_id == "p2"
    finally:
        await MLModel.find(In(MLModel.model_id, ["p1", "p2"])).delete()


def test_capture_environment_records_python_and_sklearn():
    env = capture_environment()
    assert "python" in env and env["python"]
    assert "sklearn" in env  # always installed in this project
