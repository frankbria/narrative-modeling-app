"""Tests for the model evaluation dashboard endpoints (issue #79).

GET /api/v1/ml/{model_id}/evaluation and POST /api/v1/ml/compare, exercised
through the authorized async client against the test database.
"""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest

CLASSIFICATION_PAYLOAD = {
    "problem_type": "binary_classification",
    "y_test": [0, 1, 1, 0, 1, 0, 1, 1, 0, 0],
    "y_pred": [0, 1, 0, 0, 1, 0, 1, 1, 1, 0],
    "y_proba": [
        [0.9, 0.1],
        [0.2, 0.8],
        [0.6, 0.4],
        [0.8, 0.2],
        [0.3, 0.7],
        [0.7, 0.3],
        [0.1, 0.9],
        [0.25, 0.75],
        [0.45, 0.55],
        [0.85, 0.15],
    ],
    "class_labels": ["0", "1"],
    "created_at": "2026-06-11T00:00:00+00:00",
}

REGRESSION_PAYLOAD = {
    "problem_type": "regression",
    "y_test": [10.0, 12.0, 9.0, 15.0, 11.0],
    "y_pred": [10.5, 11.5, 9.2, 14.0, 11.3],
    "y_proba": None,
    "class_labels": None,
    "created_at": "2026-06-11T00:00:00+00:00",
}


async def _insert_model(
    model_id: str,
    *,
    user_id: str = "test_user_123",
    dataset_id: str = "dataset_123",
    problem_type: str = "binary_classification",
    evaluation_data_path=None,
    algorithm: str = "Random Forest",
    evaluation_on_calibration_set: bool = False,
):
    from app.models.ml_model import MLModel

    model = MLModel(
        evaluation_on_calibration_set=evaluation_on_calibration_set,
        user_id=user_id,
        dataset_id=dataset_id,
        model_id=model_id,
        name=f"Model {model_id}",
        problem_type=problem_type,
        algorithm=algorithm,
        target_column="target",
        feature_names=["f1", "f2"],
        cv_score=0.85,
        test_score=0.82,
        metrics={"cv_score": 0.85, "test_score": 0.82, "training_time": 12.5},
        training_time=12.5,
        model_size=1024,
        n_samples_train=100,
        n_features=2,
        model_path="s3://test-bucket/models/u/m/model.pkl",
        evaluation_data_path=evaluation_data_path,
        feature_importance={"f1": 0.6, "f2": 0.4},
    )
    await model.insert()
    return model


@asynccontextmanager
async def _models(*specs):
    """Insert MLModel docs and guarantee cleanup."""
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


class TestGetEvaluationEndpoint:
    """GET /api/v1/ml/{model_id}/evaluation"""

    @pytest.mark.asyncio
    async def test_unknown_model_404(self, async_authorized_client):
        resp = await async_authorized_client.get("/api/v1/ml/no_such_model/evaluation")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_foreign_model_404(self, async_authorized_client):
        async with _models({"model_id": "m_foreign", "user_id": "someone_else"}):
            resp = await async_authorized_client.get("/api/v1/ml/m_foreign/evaluation")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_partial_without_artifacts(self, async_authorized_client):
        """Models trained before #79 have no evaluation_data_path."""
        async with _models({"model_id": "m_partial"}):
            resp = await async_authorized_client.get("/api/v1/ml/m_partial/evaluation")

        assert resp.status_code == 200
        body = resp.json()
        assert body["partial"] is True
        assert body["model_id"] == "m_partial"
        assert body["problem_type"] == "binary_classification"
        assert body["metrics"] is None
        assert body["confusion_matrix"] is None
        assert body["roc_curve"] is None
        assert body["pr_curve"] is None
        assert body["stored_metrics"]["cv_score"] == pytest.approx(0.85)
        assert body["stored_metrics"]["test_score"] == pytest.approx(0.82)
        assert body["feature_importance"] == {"f1": 0.6, "f2": 0.4}
        assert body["evaluated_at"] is not None

    @pytest.mark.asyncio
    async def test_partial_when_artifact_load_fails(self, async_authorized_client):
        """A set path whose download fails degrades to partial, never 500."""
        spec = {
            "model_id": "m_load_fail",
            "evaluation_data_path": "s3://test-bucket/models/u/m/evaluation_data.json",
        }
        async with _models(spec):
            with _patch_artifacts(None):
                resp = await async_authorized_client.get(
                    "/api/v1/ml/m_load_fail/evaluation"
                )

        assert resp.status_code == 200
        body = resp.json()
        assert body["partial"] is True
        assert body["metrics"] is None

    @pytest.mark.asyncio
    async def test_full_classification_evaluation(
        self, async_authorized_client, monkeypatch
    ):
        from app.services.evaluation_explanation_service import (
            evaluation_explanation_service,
        )

        # Force the deterministic fallback (no OpenAI call from tests)
        monkeypatch.setattr(evaluation_explanation_service, "client", None)

        spec = {
            "model_id": "m_full",
            "evaluation_data_path": "s3://test-bucket/models/u/m/evaluation_data.json",
        }
        async with _models(spec):
            with _patch_artifacts(CLASSIFICATION_PAYLOAD):
                resp = await async_authorized_client.get("/api/v1/ml/m_full/evaluation")

        assert resp.status_code == 200
        body = resp.json()
        assert body["partial"] is False
        assert body["problem_type"] == "binary_classification"
        assert body["algorithm"] == "Random Forest"

        # 8/10 correct in the fixture payload
        assert body["metrics"]["accuracy"] == pytest.approx(0.8)
        assert body["metrics"]["per_class_metrics"].keys() == {"0", "1"}

        assert body["confusion_matrix"]["labels"] == ["0", "1"]
        assert sum(sum(row) for row in body["confusion_matrix"]["matrix"]) == 10

        assert set(body["roc_curve"]["curves"]) == {"0", "1"}
        assert body["roc_curve"]["macro_auc"] is not None
        assert set(body["pr_curve"]["baseline_per_class"]) == {"0", "1"}

        assert body["ai_explanation"]["generated_by"] == "fallback"
        assert body["ai_explanation"]["overall_assessment"]
        assert body["feature_importance"] == {"f1": 0.6, "f2": 0.4}
        # Honest split (the default) -> no calibration-set caveat (issue #201).
        assert body["evaluation_on_calibration_set"] is False
        assert not any(
            "calibration set" in c for c in body["ai_explanation"]["concerns"]
        )

    @pytest.mark.asyncio
    async def test_calibration_set_caveat_surfaced(
        self, async_authorized_client, monkeypatch
    ):
        """A model flagged evaluation_on_calibration_set (issue #201 fallback)
        surfaces the flag and a report-card concern."""
        from app.services.evaluation_explanation_service import (
            evaluation_explanation_service,
        )

        monkeypatch.setattr(evaluation_explanation_service, "client", None)

        spec = {
            "model_id": "m_cal",
            "evaluation_data_path": "s3://test-bucket/models/u/m/evaluation_data.json",
            "evaluation_on_calibration_set": True,
        }
        async with _models(spec):
            with _patch_artifacts(CLASSIFICATION_PAYLOAD):
                resp = await async_authorized_client.get("/api/v1/ml/m_cal/evaluation")

        assert resp.status_code == 200
        body = resp.json()
        assert body["evaluation_on_calibration_set"] is True
        assert any(
            "calibration set" in c for c in body["ai_explanation"]["concerns"]
        )

    @pytest.mark.asyncio
    async def test_full_regression_evaluation(
        self, async_authorized_client, monkeypatch
    ):
        from app.services.evaluation_explanation_service import (
            evaluation_explanation_service,
        )

        monkeypatch.setattr(evaluation_explanation_service, "client", None)

        spec = {
            "model_id": "m_reg",
            "problem_type": "regression",
            "algorithm": "Ridge Regression",
            "evaluation_data_path": "s3://test-bucket/models/u/m/evaluation_data.json",
        }
        async with _models(spec):
            with _patch_artifacts(REGRESSION_PAYLOAD):
                resp = await async_authorized_client.get("/api/v1/ml/m_reg/evaluation")

        assert resp.status_code == 200
        body = resp.json()
        assert body["partial"] is False
        assert body["metrics"]["mae"] > 0
        assert body["metrics"]["r2"] is not None
        # Classification-only sections stay None for regression
        assert body["confusion_matrix"] is None
        assert body["roc_curve"] is None
        assert body["pr_curve"] is None
        assert body["ai_explanation"]["generated_by"] == "fallback"

    @pytest.mark.asyncio
    async def test_explanation_failure_degrades_to_fallback(
        self, async_authorized_client, monkeypatch
    ):
        """Even if the explanation service itself blows up, the endpoint succeeds."""
        spec = {
            "model_id": "m_ai_boom",
            "evaluation_data_path": "s3://test-bucket/models/u/m/evaluation_data.json",
        }
        async with _models(spec):
            with _patch_artifacts(CLASSIFICATION_PAYLOAD), patch(
                "app.services.evaluation_explanation_service."
                "EvaluationExplanationService.generate_report_card",
                new=AsyncMock(side_effect=RuntimeError("AI exploded")),
            ):
                resp = await async_authorized_client.get(
                    "/api/v1/ml/m_ai_boom/evaluation"
                )

        assert resp.status_code == 200
        body = resp.json()
        assert body["partial"] is False
        assert body["metrics"] is not None
        assert body["ai_explanation"] is None


class TestCompareEndpoint:
    """POST /api/v1/ml/compare"""

    @pytest.mark.asyncio
    async def test_happy_path(self, async_authorized_client):
        specs = (
            {"model_id": "cmp_a", "algorithm": "Random Forest"},
            {"model_id": "cmp_b", "algorithm": "XGBoost"},
        )
        async with _models(*specs):
            resp = await async_authorized_client.post(
                "/api/v1/ml/compare", json={"model_ids": ["cmp_a", "cmp_b"]}
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["problem_type"] == "binary_classification"
        assert body["dataset_id"] == "dataset_123"
        assert [m["model_id"] for m in body["models"]] == ["cmp_a", "cmp_b"]
        first = body["models"][0]
        assert first["algorithm"] == "Random Forest"
        assert first["cv_score"] == pytest.approx(0.85)
        assert first["test_score"] == pytest.approx(0.82)
        assert first["metrics"]["training_time"] == pytest.approx(12.5)
        assert first["created_at"] is not None

    @pytest.mark.asyncio
    async def test_mixed_problem_types_400(self, async_authorized_client):
        specs = (
            {"model_id": "cmp_clf"},
            {"model_id": "cmp_reg", "problem_type": "regression"},
        )
        async with _models(*specs):
            resp = await async_authorized_client.post(
                "/api/v1/ml/compare", json={"model_ids": ["cmp_clf", "cmp_reg"]}
            )
        assert resp.status_code == 400
        assert "problem type" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_mixed_datasets_400(self, async_authorized_client):
        specs = (
            {"model_id": "cmp_ds1", "dataset_id": "dataset_1"},
            {"model_id": "cmp_ds2", "dataset_id": "dataset_2"},
        )
        async with _models(*specs):
            resp = await async_authorized_client.post(
                "/api/v1/ml/compare", json={"model_ids": ["cmp_ds1", "cmp_ds2"]}
            )
        assert resp.status_code == 400
        assert "dataset" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_too_few_ids_422(self, async_authorized_client):
        resp = await async_authorized_client.post(
            "/api/v1/ml/compare", json={"model_ids": ["only_one"]}
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_too_many_ids_422(self, async_authorized_client):
        resp = await async_authorized_client.post(
            "/api/v1/ml/compare", json={"model_ids": [f"m{i}" for i in range(6)]}
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_unknown_model_404(self, async_authorized_client):
        async with _models({"model_id": "cmp_known"}):
            resp = await async_authorized_client.post(
                "/api/v1/ml/compare", json={"model_ids": ["cmp_known", "cmp_missing"]}
            )
        assert resp.status_code == 404
        assert "cmp_missing" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_foreign_model_404(self, async_authorized_client):
        specs = (
            {"model_id": "cmp_mine"},
            {"model_id": "cmp_theirs", "user_id": "someone_else"},
        )
        async with _models(*specs):
            resp = await async_authorized_client.post(
                "/api/v1/ml/compare", json={"model_ids": ["cmp_mine", "cmp_theirs"]}
            )
        assert resp.status_code == 404
