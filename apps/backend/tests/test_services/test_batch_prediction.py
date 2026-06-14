"""
Unit tests for BatchPredictionService inference + summary logic (issue #82).

These exercise the pure pieces of the batch pipeline (no MongoDB): chunk
inference reusing the fitted feature pipeline, summary-statistic aggregation,
tabular CSV flattening, and S3 result upload (S3 mocked at the method level).
The full job lifecycle with real Mongo + S3 is covered by the integration
round-trip test.
"""

import json
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pandas as pd
import pytest

from app.models.batch_job import BatchPredictionConfig
from app.services.batch_prediction import BatchPredictionService


class _FakeFeatureEngineer:
    """Minimal fitted feature engineer with an async transform (passthrough)."""

    numeric_features = ["age"]
    categorical_features = []

    async def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        return df[self.numeric_features]


class _FakeClassifier:
    def predict(self, X):
        return np.array([1] * len(X))

    def predict_proba(self, X):
        return np.array([[0.2, 0.8]] * len(X))


def _service() -> BatchPredictionService:
    svc = BatchPredictionService()
    # Never touch real S3 in unit tests.
    svc.s3_service = MagicMock()
    svc.s3_service.upload_file_obj = AsyncMock(return_value="s3://bucket/key")
    svc.s3_service.download_file_obj = AsyncMock()
    return svc


def _model(problem_type="binary_classification"):
    model = MagicMock()
    model.problem_type = problem_type
    model.feature_names = ["age"]
    model.model_id = "model_123"
    model.version = "1.0.0"
    return model


@pytest.mark.asyncio
async def test_predict_chunk_awaits_async_transform_and_adds_confidence():
    """_predict_chunk awaits the async transform and records confidence (#82)."""
    svc = _service()
    config = BatchPredictionConfig(model_id="model_123", include_probabilities=True)
    chunk = pd.DataFrame([{"age": 30}, {"age": 41}])

    results = await svc._predict_chunk(
        chunk, _FakeClassifier(), _FakeFeatureEngineer(), _model(), config
    )

    assert len(results) == 2
    assert all("error" not in r for r in results)
    assert results[0]["prediction"] == 1
    assert results[0]["probabilities"] == [0.2, 0.8]
    assert results[0]["confidence"] == 0.8


@pytest.mark.asyncio
async def test_predict_chunk_records_per_row_errors():
    """A row that fails inference is captured as an error, not raised (#82)."""
    svc = _service()
    config = BatchPredictionConfig(model_id="model_123", include_probabilities=False)

    class _Boom:
        async def transform(self, df):
            raise ValueError("bad row")

        numeric_features = ["age"]
        categorical_features = []

    chunk = pd.DataFrame([{"age": 30}])
    results = await svc._predict_chunk(
        chunk, _FakeClassifier(), _Boom(), _model(), config
    )

    assert results[0]["error"] == "bad row"


def test_calculate_summary_statistics_classification():
    """Classification summary has a class distribution + confidence stats (#82)."""
    svc = _service()
    predictions = [
        {"prediction": "yes", "confidence": 0.9, "error": None},
        {"prediction": "no", "confidence": 0.6, "error": None},
        {"prediction": "yes", "confidence": 0.8, "error": None},
        {"error": "boom"},
    ]

    stats = svc._calculate_summary_statistics(predictions, _model())

    assert stats["total_predictions"] == 4
    assert stats["success_count"] == 3
    assert stats["error_count"] == 1
    assert stats["prediction_distribution"] == {"yes": 2, "no": 1}
    assert stats["confidence_stats"]["max"] == 0.9
    assert stats["confidence_stats"]["min"] == 0.6
    assert round(stats["confidence_stats"]["mean"], 4) == round(
        (0.9 + 0.6 + 0.8) / 3, 4
    )


def test_calculate_summary_statistics_regression():
    """Regression summary reports value stats, not a class distribution (#82)."""
    svc = _service()
    predictions = [
        {"prediction": 10.0, "error": None},
        {"prediction": 20.0, "error": None},
        {"prediction": 30.0, "error": None},
    ]

    stats = svc._calculate_summary_statistics(predictions, _model("regression"))

    assert stats["prediction_distribution"] == {}
    assert stats["prediction_value_stats"]["min"] == 10.0
    assert stats["prediction_value_stats"]["max"] == 30.0
    assert stats["prediction_value_stats"]["mean"] == 20.0


def test_results_to_dataframe_flattens_inputs_and_outputs():
    """Downloadable CSV flattens input columns + prediction/confidence (#82)."""
    svc = _service()
    predictions = [
        {
            "input_data": {"age": 30, "city": "NYC"},
            "prediction": "yes",
            "confidence": 0.8,
            "probabilities": [0.2, 0.8],
        },
        {"input_data": {"age": 41, "city": "LA"}, "error": "boom"},
    ]

    df = svc._results_to_dataframe(predictions)

    assert list(df.columns)[:2] == ["age", "city"]
    assert "prediction" in df.columns
    assert "confidence" in df.columns
    assert "error" in df.columns
    # probabilities are JSON-encoded so the cell stays a scalar
    assert json.loads(df.iloc[0]["probabilities"]) == [0.2, 0.8]


class _LowConfClassifier:
    def predict(self, X):
        return np.array([1] * len(X))

    def predict_proba(self, X):
        # 0.55 max → below the 0.7 low-confidence threshold
        return np.array([[0.45, 0.55]] * len(X))


class _FakeRegressor:
    def predict(self, X):
        return np.array([10.0] * len(X))


@pytest.mark.asyncio
async def test_predict_chunk_flags_low_confidence():
    """Predictions below the threshold are flagged low_confidence (#83)."""
    svc = _service()
    config = BatchPredictionConfig(model_id="model_123", include_probabilities=False)
    chunk = pd.DataFrame([{"age": 30}])

    results = await svc._predict_chunk(
        chunk, _LowConfClassifier(), _FakeFeatureEngineer(), _model(), config
    )

    assert results[0]["confidence"] == 0.55
    assert results[0]["low_confidence"] is True
    # Confidence is computed even though full probabilities were not requested.
    assert "probabilities" not in results[0]


@pytest.mark.asyncio
async def test_predict_chunk_regression_interval():
    """Regression rows carry a prediction interval from residual_std (#83)."""
    svc = _service()
    config = BatchPredictionConfig(model_id="model_123")
    model = _model("regression")
    model.residual_std = 2.0
    chunk = pd.DataFrame([{"age": 30}])

    results = await svc._predict_chunk(
        chunk, _FakeRegressor(), _FakeFeatureEngineer(), model, config
    )

    low, high = results[0]["prediction_interval"]
    assert low == pytest.approx(10.0 - 1.96 * 2.0)
    assert high == pytest.approx(10.0 + 1.96 * 2.0)


@pytest.mark.asyncio
async def test_predict_chunk_includes_explanation_when_requested():
    """With include_explanations, rows carry a model-native explanation (#83)."""
    from sklearn.datasets import make_classification
    from sklearn.linear_model import LogisticRegression

    X, y = make_classification(
        n_samples=80,
        n_features=1,
        n_informative=1,
        n_redundant=0,
        n_clusters_per_class=1,
        random_state=0,
    )
    estimator = LogisticRegression().fit(X, y)

    svc = _service()
    config = BatchPredictionConfig(model_id="model_123", include_explanations=True)
    model = _model()
    model.feature_importance = None
    chunk = pd.DataFrame([{"age": float(X[0][0])}])

    results = await svc._predict_chunk(
        chunk, estimator, _FakeFeatureEngineer(), model, config
    )

    assert "explanation_text" in results[0]
    assert results[0]["explanation"]["method"] == "linear_coefficients"


def test_summary_counts_low_confidence():
    """Summary reports how many successful predictions were low-confidence (#83)."""
    svc = _service()
    predictions = [
        {
            "prediction": "yes",
            "confidence": 0.9,
            "low_confidence": False,
            "error": None,
        },
        {"prediction": "no", "confidence": 0.6, "low_confidence": True, "error": None},
        {"prediction": "no", "confidence": 0.55, "low_confidence": True, "error": None},
    ]

    stats = svc._calculate_summary_statistics(predictions, _model())

    assert stats["low_confidence_count"] == 2


def test_results_to_dataframe_includes_low_confidence_column():
    """CSV export carries the low_confidence column + interval/explanation (#83)."""
    svc = _service()
    predictions = [
        {
            "input_data": {"age": 30},
            "prediction": 10.0,
            "low_confidence": False,
            "prediction_interval": [6.0, 14.0],
            "explanation_text": "driven by age",
        },
    ]

    df = svc._results_to_dataframe(predictions)

    assert "low_confidence" in df.columns
    assert (
        df.iloc[0]["low_confidence"] is False or df.iloc[0]["low_confidence"] == False
    )  # noqa: E712
    assert json.loads(df.iloc[0]["prediction_interval"]) == [6.0, 14.0]
    assert df.iloc[0]["explanation"] == "driven by age"


@pytest.mark.asyncio
async def test_save_results_uploads_csv_and_returns_key():
    """_save_results uploads via the real S3 API and returns the object key (#82)."""
    svc = _service()
    config = BatchPredictionConfig(model_id="model_123", output_format="csv")
    job = MagicMock()
    job.user_id = "test_user_123"

    predictions = [
        {"input_data": {"age": 30}, "prediction": "yes", "confidence": 0.8},
    ]

    key = await svc._save_results(job, predictions, config)

    assert key.startswith("batch-jobs/test_user_123/model_123/")
    assert key.endswith("results.csv")
    svc.s3_service.upload_file_obj.assert_awaited_once()
    # Uploaded a binary buffer to the same key.
    args, _ = svc.s3_service.upload_file_obj.call_args
    assert args[1] == key


@pytest.mark.asyncio
async def test_prepare_input_data_uploads_dataframe():
    """A DataFrame input is uploaded as CSV bytes via upload_file_obj (#82)."""
    svc = _service()
    df = pd.DataFrame([{"age": 1}, {"age": 2}, {"age": 3}])

    key, total = await svc._prepare_input_data(df, "test_user_123", "model_123")

    assert total == 3
    assert key.endswith("input.csv")
    svc.s3_service.upload_file_obj.assert_awaited_once()
