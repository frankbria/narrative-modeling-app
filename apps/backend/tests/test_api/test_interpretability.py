"""Tests for the interpretability endpoints (issue #80).

GET /api/v1/ml/{model_id}/feature-importance and GET /api/v1/ml/{model_id}/shap,
exercised through the authorized async client against the test database. SHAP
artifact loads are patched so these stay unit-level (no S3).
"""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest

SHAP_PAYLOAD = {
    "explainer_type": "tree",
    "shap_importance": {"f1": 0.1, "f2": 0.6, "f3": 0.3},
    "base_value": 0.42,
    "n_samples": 80,
    "created_at": "2026-06-14T00:00:00+00:00",
}


async def _insert_model(
    model_id: str,
    *,
    user_id: str = "test_user_123",
    problem_type: str = "binary_classification",
    feature_importance=None,
    shap_values_path=None,
    shap_explainer_type=None,
):
    from app.models.ml_model import MLModel

    model = MLModel(
        user_id=user_id,
        dataset_id="dataset_123",
        model_id=model_id,
        name=f"Model {model_id}",
        problem_type=problem_type,
        algorithm="Random Forest",
        target_column="target",
        feature_names=["f1", "f2", "f3"],
        cv_score=0.85,
        test_score=0.82,
        metrics={"cv_score": 0.85, "test_score": 0.82},
        training_time=12.5,
        model_size=1024,
        n_samples_train=100,
        n_features=3,
        model_path="s3://test-bucket/models/u/m/model.pkl",
        feature_importance=feature_importance,
        shap_values_path=shap_values_path,
        shap_explainer_type=shap_explainer_type,
    )
    await model.insert()
    return model


@asynccontextmanager
async def _models(*specs):
    created = []
    try:
        for spec in specs:
            created.append(await _insert_model(**spec))
        yield created
    finally:
        for model in created:
            try:
                await model.delete()
            except Exception:
                pass


def _patch_shap(payload):
    return patch(
        "app.services.metrics_service.MetricsService.load_shap_artifacts",
        new=AsyncMock(return_value=payload),
    )


class TestFeatureImportanceEndpoint:
    """GET /api/v1/ml/{model_id}/feature-importance"""

    @pytest.mark.asyncio
    async def test_unknown_model_404(self, async_authorized_client):
        resp = await async_authorized_client.get(
            "/api/v1/ml/no_such/feature-importance"
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_foreign_model_404(self, async_authorized_client):
        async with _models({"model_id": "fi_foreign", "user_id": "someone_else"}):
            resp = await async_authorized_client.get(
                "/api/v1/ml/fi_foreign/feature-importance"
            )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_native_only_ranked_descending(self, async_authorized_client):
        spec = {"model_id": "fi_native", "feature_importance": {"f1": 0.2, "f2": 0.7}}
        async with _models(spec):
            with _patch_shap(None):
                resp = await async_authorized_client.get(
                    "/api/v1/ml/fi_native/feature-importance"
                )

        assert resp.status_code == 200
        body = resp.json()
        assert body["partial"] is False
        assert body["shap_importance"] is None
        # Ranked by descending importance
        assert [f["feature_name"] for f in body["native_importance"]] == ["f2", "f1"]
        assert body["message"] is not None

    @pytest.mark.asyncio
    async def test_with_shap_importance(self, async_authorized_client):
        spec = {
            "model_id": "fi_shap",
            "feature_importance": {"f1": 0.2, "f2": 0.7, "f3": 0.1},
            "shap_values_path": "s3://test-bucket/models/u/m/shap_data.json",
            "shap_explainer_type": "tree",
        }
        async with _models(spec):
            with _patch_shap(SHAP_PAYLOAD):
                resp = await async_authorized_client.get(
                    "/api/v1/ml/fi_shap/feature-importance"
                )

        assert resp.status_code == 200
        body = resp.json()
        assert body["partial"] is False
        assert body["explainer_type"] == "tree"
        assert [f["feature_name"] for f in body["shap_importance"]] == ["f2", "f3", "f1"]

    @pytest.mark.asyncio
    async def test_partial_when_no_importance(self, async_authorized_client):
        async with _models({"model_id": "fi_none", "feature_importance": None}):
            with _patch_shap(None):
                resp = await async_authorized_client.get(
                    "/api/v1/ml/fi_none/feature-importance"
                )

        assert resp.status_code == 200
        body = resp.json()
        assert body["partial"] is True
        assert body["native_importance"] == []
        assert body["shap_importance"] is None
        assert body["message"] is not None


class TestShapEndpoint:
    """GET /api/v1/ml/{model_id}/shap"""

    @pytest.mark.asyncio
    async def test_unknown_model_404(self, async_authorized_client):
        resp = await async_authorized_client.get("/api/v1/ml/no_such/shap")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_partial_without_shap_artifacts(self, async_authorized_client):
        """A model trained before #80 (or unsupported type) degrades, never 500."""
        async with _models({"model_id": "shap_partial"}):
            with _patch_shap(None):
                resp = await async_authorized_client.get("/api/v1/ml/shap_partial/shap")

        assert resp.status_code == 200
        body = resp.json()
        assert body["partial"] is True
        assert body["feature_importance"] == []
        assert body["problem_type"] == "binary_classification"
        assert body["message"] is not None
        assert body["evaluated_at"] is not None

    @pytest.mark.asyncio
    async def test_full_shap_summary(self, async_authorized_client):
        spec = {
            "model_id": "shap_full",
            "shap_values_path": "s3://test-bucket/models/u/m/shap_data.json",
            "shap_explainer_type": "tree",
        }
        async with _models(spec):
            with _patch_shap(SHAP_PAYLOAD):
                resp = await async_authorized_client.get("/api/v1/ml/shap_full/shap")

        assert resp.status_code == 200
        body = resp.json()
        assert body["partial"] is False
        assert body["explainer_type"] == "tree"
        assert body["base_value"] == pytest.approx(0.42)
        # Ranked by descending mean |SHAP|
        assert [f["feature_name"] for f in body["feature_importance"]] == [
            "f2",
            "f3",
            "f1",
        ]
        # Plain-language summary names the top driver
        assert "f2" in body["plain_language"]
