"""Tests for the per-deployment SDK endpoints on ``/api/v1/ml/`` (issue #86).

``GET /ml/{id}/sdk`` (info), ``/sdk/{language}`` (source), ``/sdk/postman``.
``async_authorized_client`` authenticates as ``test_user_123``.
"""

import pytest
from beanie.odm.operators.find.comparison import In

from app.models.ml_model import MLModel

USER = "test_user_123"


def _model(model_id: str, *, user_id: str = USER) -> MLModel:
    return MLModel(
        user_id=user_id,
        dataset_id="ds-sdk",
        model_id=model_id,
        name="Sales Prediction Model",
        problem_type="regression",
        algorithm="Random Forest",
        target_column="revenue",
        feature_names=["month", "store_id", "temperature"],
        cv_score=0.81,
        test_score=0.79,
        training_time=1.0,
        model_size=10,
        n_samples_train=100,
        n_features=3,
        model_path="s3://bucket/model.pkl",
    )


@pytest.fixture
async def sdk_model():
    model = _model("sdk-1")
    await model.insert()
    yield model
    await MLModel.find(In(MLModel.model_id, ["sdk-1", "sdk-foreign"])).delete()


class TestSdkInfo:
    @pytest.mark.asyncio
    async def test_info_lists_languages_and_features(
        self, async_authorized_client, sdk_model
    ):
        resp = await async_authorized_client.get("/api/v1/ml/sdk-1/sdk")
        assert resp.status_code == 200
        body = resp.json()
        assert body["model_id"] == "sdk-1"
        assert set(body["languages"]) == {"python", "typescript", "javascript", "curl"}
        assert body["feature_names"] == ["month", "store_id", "temperature"]
        assert body["sample_record"] == {"month": 0, "store_id": 0, "temperature": 0}
        # Synthesized serving endpoint points at the real production route.
        assert body["serving_endpoint"].endswith(
            "/api/v1/production/v1/models/sdk-1"
        )

    @pytest.mark.asyncio
    async def test_info_prefers_persisted_deployment_endpoint(
        self, async_authorized_client
    ):
        # When the model has a persisted deployment_endpoint (#84), the SDK uses
        # it verbatim instead of synthesizing one from the request host.
        model = _model("sdk-deployed")
        model.deployment_endpoint = (
            "https://prod.example.com/api/v1/production/v1/models/sdk-deployed"
        )
        await model.insert()
        try:
            resp = await async_authorized_client.get("/api/v1/ml/sdk-deployed/sdk")
            assert resp.status_code == 200
            assert (
                resp.json()["serving_endpoint"]
                == "https://prod.example.com/api/v1/production/v1/models/sdk-deployed"
            )
        finally:
            await MLModel.find(MLModel.model_id == "sdk-deployed").delete()


class TestSdkSource:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("language", ["python", "typescript", "javascript", "curl"])
    async def test_each_language_carries_real_contract(
        self, async_authorized_client, sdk_model, language
    ):
        resp = await async_authorized_client.get(f"/api/v1/ml/sdk-1/sdk/{language}")
        assert resp.status_code == 200
        source = resp.text
        # Real serving contract: production route + X-API-Key + real features.
        assert "/api/v1/production/v1/models/sdk-1" in source
        assert "X-API-Key" in source
        assert "month" in source  # real feature name appears in the sample record

    @pytest.mark.asyncio
    async def test_unknown_language_returns_404(
        self, async_authorized_client, sdk_model
    ):
        resp = await async_authorized_client.get("/api/v1/ml/sdk-1/sdk/ruby")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_unknown_model_returns_404(self, async_authorized_client):
        resp = await async_authorized_client.get("/api/v1/ml/nope/sdk/python")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_foreign_model_returns_404(self, async_authorized_client):
        foreign = _model("sdk-foreign", user_id="someone_else")
        await foreign.insert()
        try:
            resp = await async_authorized_client.get(
                "/api/v1/ml/sdk-foreign/sdk/python"
            )
            assert resp.status_code == 404
        finally:
            await MLModel.find(
                MLModel.model_id == "sdk-foreign",
                MLModel.user_id == "someone_else",
            ).delete()


class TestSdkPostman:
    @pytest.mark.asyncio
    async def test_postman_collection_is_per_deployment(
        self, async_authorized_client, sdk_model
    ):
        resp = await async_authorized_client.get("/api/v1/ml/sdk-1/sdk/postman")
        assert resp.status_code == 200
        collection = resp.json()
        assert "Sales Prediction Model" in collection["info"]["name"]
        names = [item["name"] for item in collection["item"]]
        assert "Predict" in names
        endpoint_var = next(
            v for v in collection["variable"] if v["key"] == "endpoint"
        )
        assert endpoint_var["value"].endswith("/api/v1/production/v1/models/sdk-1")
