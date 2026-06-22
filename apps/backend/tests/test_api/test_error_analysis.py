"""Tests for the error-analysis endpoint (issue #81).

GET /api/v1/ml/{model_id}/errors, exercised through the authorized async client
against the test database. Mirrors test_model_evaluation.py.
"""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest


def _classification_payload(n=120, with_features=True):
    rng = np.random.default_rng(0)
    x = rng.normal(size=(n, 3))
    y_true = np.where(x[:, 0] > 0, "A", "B")
    y_pred = y_true.copy()
    low = np.where(x[:, 0] < -0.5)[0]
    y_pred[low[: int(len(low) * 0.6)]] = "A"
    payload = {
        "problem_type": "binary_classification",
        "y_test": y_true.tolist(),
        "y_pred": y_pred.tolist(),
        "y_proba": [[0.8, 0.2]] * n,
        "class_labels": ["A", "B"],
        "created_at": "2026-06-11T00:00:00+00:00",
    }
    if with_features:
        payload["X_test"] = x.tolist()
        payload["feature_names"] = ["feature_0", "feature_1", "feature_2"]
    return payload


REGRESSION_PAYLOAD = {
    "problem_type": "regression",
    "y_test": [float(v) for v in range(50)],
    "y_pred": [float(v) + (8.0 if v > 40 else 0.1) for v in range(50)],
    "y_proba": None,
    "class_labels": None,
    "X_test": [[float(v), float(v % 5)] for v in range(50)],
    "feature_names": ["f0", "f1"],
    "created_at": "2026-06-11T00:00:00+00:00",
}


async def _insert_model(
    model_id: str,
    *,
    user_id: str = "test_user_123",
    problem_type: str = "binary_classification",
    evaluation_data_path="s3://test-bucket/models/u/m/evaluation_data.json",
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
        feature_names=["feature_0", "feature_1", "feature_2"],
        cv_score=0.85,
        test_score=0.82,
        metrics={"cv_score": 0.85, "test_score": 0.82},
        training_time=12.5,
        model_size=1024,
        n_samples_train=100,
        n_features=3,
        model_path="s3://test-bucket/models/u/m/model.pkl",
        evaluation_data_path=evaluation_data_path,
        feature_importance={"feature_0": 0.6, "feature_1": 0.3, "feature_2": 0.1},
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


def _patch_artifacts(payload):
    return patch(
        "app.services.metrics_service.MetricsService.load_evaluation_artifacts",
        new=AsyncMock(return_value=payload),
    )


class TestErrorAnalysisEndpoint:
    """GET /api/v1/ml/{model_id}/errors"""

    @pytest.mark.asyncio
    async def test_unknown_model_404(self, async_authorized_client):
        resp = await async_authorized_client.get("/api/v1/ml/nope/errors")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_foreign_model_404(self, async_authorized_client):
        async with _models({"model_id": "m_foreign", "user_id": "other"}):
            resp = await async_authorized_client.get("/api/v1/ml/m_foreign/errors")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_partial_without_artifacts(self, async_authorized_client):
        async with _models({"model_id": "m_noart", "evaluation_data_path": None}):
            resp = await async_authorized_client.get("/api/v1/ml/m_noart/errors")
        assert resp.status_code == 200
        body = resp.json()
        assert body["partial"] is True
        assert body["distribution"] is None
        assert body["suggestions"] == []

    @pytest.mark.asyncio
    async def test_full_classification_analysis(self, async_authorized_client):
        async with _models({"model_id": "m_full"}):
            with _patch_artifacts(_classification_payload()):
                resp = await async_authorized_client.get("/api/v1/ml/m_full/errors")
        assert resp.status_code == 200
        body = resp.json()
        assert body["partial"] is False
        assert body["distribution"]["total_errors"] > 0
        assert body["confusion_pairs"]
        assert body["segments"]
        assert body["clusters"]
        assert body["patterns"]
        assert body["cases"]
        assert body["suggestions"]
        # generated_by is env-dependent (OpenAI key presence); fallback path is
        # covered directly in test_error_analysis_service.py.
        assert body["suggestions_generated_by"] in ("openai", "fallback")

    @pytest.mark.asyncio
    async def test_partial_when_features_missing(self, async_authorized_client):
        """Pre-#81 artifacts (no X_test) → partial; pairs/cases still present."""
        async with _models({"model_id": "m_nofeat"}):
            with _patch_artifacts(_classification_payload(with_features=False)):
                resp = await async_authorized_client.get("/api/v1/ml/m_nofeat/errors")
        assert resp.status_code == 200
        body = resp.json()
        assert body["partial"] is True
        assert body["confusion_pairs"]
        assert body["segments"] == []
        assert body["message"]

    @pytest.mark.asyncio
    async def test_regression_analysis(self, async_authorized_client):
        async with _models({"model_id": "m_reg", "problem_type": "regression"}):
            with _patch_artifacts(REGRESSION_PAYLOAD):
                resp = await async_authorized_client.get("/api/v1/ml/m_reg/errors")
        assert resp.status_code == 200
        body = resp.json()
        assert body["partial"] is False
        assert body["confusion_pairs"] == []
        assert body["distribution"]["total_errors"] > 0
