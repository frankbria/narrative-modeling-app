"""Tests for the real model-deploy endpoint on the ``/api/v1/ml/`` surface (issue #84).

Pre-#84 the deploy button hit ``PUT /api/v1/models/{id}/deploy`` (the dead
``ModelConfig`` surface), so it 404'd against every real ``MLModel``. The deploy
route now lives on the real surface and serving already works by ``model_id``
(``POST /api/v1/production/v1/models/{id}/predict``). ``async_authorized_client``
authenticates as ``test_user_123``.
"""

import pytest
from beanie.odm.operators.find.comparison import In

from app.models.ml_model import MLModel

USER = "test_user_123"


def _model(model_id: str, *, user_id: str = USER) -> MLModel:
    return MLModel(
        user_id=user_id,
        dataset_id="ds-deploy",
        model_id=model_id,
        name="Deploy Me",
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
async def deployable():
    model = _model("deploy-1")
    await model.insert()
    yield model
    await MLModel.find(In(MLModel.model_id, ["deploy-1", "deploy-foreign"])).delete()


class TestDeploy:
    @pytest.mark.asyncio
    async def test_deploy_marks_model_and_synthesizes_endpoint(
        self, async_authorized_client, deployable
    ):
        resp = await async_authorized_client.put("/api/v1/ml/deploy-1/deploy", json={})
        assert resp.status_code == 200
        body = resp.json()
        assert body["model_id"] == "deploy-1"
        assert body["status"] == "deployed"
        assert body["deployed_at"] is not None
        # Endpoint synthesized server-side → the real production serving route.
        assert body["deployment_endpoint"].endswith(
            "/api/v1/production/v1/models/deploy-1"
        )

        # Status is readable on the model record (no separate route).
        got = await async_authorized_client.get("/api/v1/ml/deploy-1")
        assert got.status_code == 200
        model = got.json()
        assert model["is_deployed"] is True
        assert model["deployment_endpoint"].endswith(
            "/api/v1/production/v1/models/deploy-1"
        )
        assert model["deployed_at"] is not None

    @pytest.mark.asyncio
    async def test_deploy_honors_supplied_endpoint(
        self, async_authorized_client, deployable
    ):
        resp = await async_authorized_client.put(
            "/api/v1/ml/deploy-1/deploy",
            json={"endpoint": "https://custom.example/predict"},
        )
        assert resp.status_code == 200
        assert resp.json()["deployment_endpoint"] == "https://custom.example/predict"

    @pytest.mark.asyncio
    async def test_unknown_model_returns_404(self, async_authorized_client):
        resp = await async_authorized_client.put("/api/v1/ml/nope/deploy", json={})
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_foreign_model_returns_404(self, async_authorized_client):
        foreign = _model("deploy-foreign", user_id="someone_else")
        await foreign.insert()
        resp = await async_authorized_client.put(
            "/api/v1/ml/deploy-foreign/deploy", json={}
        )
        assert resp.status_code == 404
