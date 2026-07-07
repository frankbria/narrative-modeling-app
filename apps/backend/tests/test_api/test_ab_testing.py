"""Integration tests for the A/B testing route against the real backend (issue #262).

The feature was advertised in the main nav but unreachable: the frontend service
hit a relative URL with a non-existent auth token, so create/list silently 404'd.
These tests exercise the real ``/api/v1/ab-testing`` surface (real Mongo, real
auth dependency) so a working end-to-end path is guaranteed.

``async_authorized_client`` authenticates as ``test_user_123``; ``async_test_client``
sends no credentials.
"""

import pytest
from beanie.odm.operators.find.comparison import In

from app.models.ab_test import ABTest
from app.models.ml_model import MLModel

USER = "test_user_123"
MODEL_IDS = ["abtest-m1", "abtest-m2"]


def _model(model_id: str) -> MLModel:
    return MLModel(
        user_id=USER,
        dataset_id="ds-abtest",
        model_id=model_id,
        name="AB Model",
        problem_type="binary_classification",
        algorithm="Random Forest",
        target_column="target",
        feature_names=["f1", "f2"],
        cv_score=0.81,
        test_score=0.79,
        training_time=1.0,
        model_size=10,
        n_samples_train=100,
        n_features=2,
        model_path="s3://bucket/model.pkl",
    )


@pytest.fixture
async def two_models():
    models = [_model(mid) for mid in MODEL_IDS]
    for m in models:
        await m.insert()
    yield models
    await MLModel.find(In(MLModel.model_id, MODEL_IDS)).delete()
    await ABTest.find(ABTest.user_id == USER).delete()


class TestABTestingRoundTrip:
    @pytest.mark.asyncio
    async def test_create_then_list_experiment(self, async_authorized_client, two_models):
        create = await async_authorized_client.post(
            "/api/v1/ab-testing/experiments",
            json={
                "name": "Homepage model test",
                "model_ids": MODEL_IDS,
                "primary_metric": "accuracy",
            },
        )
        assert create.status_code == 200, create.text
        body = create.json()
        assert body["name"] == "Homepage model test"
        assert len(body["variants"]) == 2

        listed = await async_authorized_client.get("/api/v1/ab-testing/experiments")
        assert listed.status_code == 200
        ids = [e["experiment_id"] for e in listed.json()]
        assert body["experiment_id"] in ids

    @pytest.mark.asyncio
    async def test_create_rejects_unknown_model(self, async_authorized_client):
        resp = await async_authorized_client.post(
            "/api/v1/ab-testing/experiments",
            json={"name": "Bad", "model_ids": ["does-not-exist"], "primary_metric": "accuracy"},
        )
        assert resp.status_code == 400


class TestABTestingAuth:
    @pytest.mark.asyncio
    async def test_list_requires_auth(self, async_test_client):
        resp = await async_test_client.get("/api/v1/ab-testing/experiments")
        assert resp.status_code in (401, 403)
