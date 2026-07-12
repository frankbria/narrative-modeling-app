"""
Unit tests for BatchPredictionService inference + summary logic (issue #82).

These exercise the pure pieces of the batch pipeline (no MongoDB): chunk
inference reusing the fitted feature pipeline, summary-statistic aggregation,
tabular CSV flattening, and S3 result upload (S3 mocked at the method level).
The full job lifecycle with real Mongo + S3 is covered by the integration
round-trip test.
"""

import io
import json
import os
import tempfile
from datetime import datetime
from typing import Any
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


class _CountingClassifier:
    """Classifier that records how many times predict/predict_proba run."""

    def __init__(self) -> None:
        self.predict_calls = 0
        self.proba_calls = 0

    def predict(self, X):
        self.predict_calls += 1
        return np.array([1] * len(X))

    def predict_proba(self, X):
        self.proba_calls += 1
        return np.array([[0.2, 0.8]] * len(X))


@pytest.mark.asyncio
async def test_predict_chunk_vectorizes_inference():
    """predict/predict_proba run once per chunk, not once per row (#202)."""
    svc = _service()
    config = BatchPredictionConfig(model_id="model_123", include_probabilities=True)
    clf = _CountingClassifier()
    chunk = pd.DataFrame([{"age": 30}, {"age": 41}, {"age": 52}])

    results = await svc._predict_chunk(
        chunk, clf, _FakeFeatureEngineer(), _model(), config
    )

    assert len(results) == 3
    assert all(r["prediction"] == 1 for r in results)
    assert all(r["confidence"] == 0.8 for r in results)
    assert clf.predict_calls == 1
    assert clf.proba_calls == 1


@pytest.mark.asyncio
async def test_predict_chunk_falls_back_to_sequential_on_batch_failure():
    """A chunk-level failure falls back to row-by-row so a batch-incompatible
    estimator (or one bad row) doesn't sink the whole chunk (#202)."""
    svc = _service()
    config = BatchPredictionConfig(model_id="model_123", include_probabilities=False)

    class _BatchOnlyFails:
        """Raises on multi-row calls; only single-row inference succeeds."""

        def __init__(self) -> None:
            self.single_row_predicts = 0

        def predict(self, X):
            if len(X) != 1:
                raise ValueError("batch predict not supported")
            self.single_row_predicts += 1
            return np.array([1])

        def predict_proba(self, X):
            if len(X) != 1:
                raise ValueError("batch predict not supported")
            return np.array([[0.3, 0.7]])

    clf = _BatchOnlyFails()
    chunk = pd.DataFrame([{"age": 30}, {"age": 41}])
    results = await svc._predict_chunk(
        chunk, clf, _FakeFeatureEngineer(), _model(), config
    )

    assert len(results) == 2
    assert all(r.get("error") is None for r in results)
    assert all(r["prediction"] == 1 for r in results)
    # Confirms the sequential path actually ran (one predict per row), not that
    # the vectorized path somehow succeeded on a 2-row chunk.
    assert clf.single_row_predicts == 2


@pytest.mark.asyncio
async def test_vectorized_and_sequential_paths_produce_identical_results():
    """The vectorized and sequential paths assemble identical per-row output for
    the same input — guards against row-ordering / index-alignment bugs (#202).

    Uses the default ``include_metadata=False`` config: metadata stamps a
    per-row ``datetime.utcnow()`` in both paths, so wall-clock timestamps would
    differ between the two runs and break a naive equality check.
    """
    svc = _service()
    config = BatchPredictionConfig(model_id="model_123", include_probabilities=True)
    chunk = pd.DataFrame([{"age": 30}, {"age": 41}, {"age": 52}])

    vectorized = await svc._predict_chunk_vectorized(
        chunk, _FakeClassifier(), _FakeFeatureEngineer(), _model(), config
    )
    sequential = await svc._predict_chunk_sequential(
        chunk, _FakeClassifier(), _FakeFeatureEngineer(), _model(), config
    )

    assert vectorized == sequential


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
    assert not bool(df.iloc[0]["low_confidence"])
    assert json.loads(df.iloc[0]["prediction_interval"]) == [6.0, 14.0]
    assert df.iloc[0]["explanation"] == "driven by age"


@pytest.mark.asyncio
async def test_upload_results_file_streams_from_disk_and_returns_key():
    """_upload_results_file streams an on-disk file to S3 and returns the key (#278)."""
    svc = _service()
    config = BatchPredictionConfig(model_id="model_123", output_format="csv")
    job = MagicMock()
    job.user_id = "test_user_123"

    fd, out_path = tempfile.mkstemp(suffix=".csv")
    with os.fdopen(fd, "w") as fh:
        fh.write("age,prediction\n30,yes\n")

    try:
        key = await svc._upload_results_file(out_path, job, config)
    finally:
        os.unlink(out_path)

    assert key.startswith("batch-jobs/test_user_123/model_123/")
    assert key.endswith("results.csv")
    svc.s3_service.upload_file_obj.assert_awaited_once()
    # Uploaded a file handle (not an in-memory buffer of the whole result) to the key.
    args, _ = svc.s3_service.upload_file_obj.call_args
    assert args[1] == key
    assert hasattr(args[0], "read")


def test_csv_header_is_deterministic_superset():
    """_csv_header reserves every possible output column, error last (#278)."""
    svc = _service()
    config = BatchPredictionConfig(
        model_id="m", include_probabilities=True, include_explanations=True
    )
    header = svc._csv_header(["age", "city"], True, True, _model(), config)

    assert header[:2] == ["age", "city"]
    for col in ("prediction", "confidence", "low_confidence", "probabilities",
                "explanation", "error"):
        assert col in header
    # "error" is always reserved last so a later all-error chunk cannot misalign.
    assert header[-1] == "error"


@pytest.mark.asyncio
async def test_prepare_input_data_rejects_oversize_batch(monkeypatch):
    """A batch over MAX_BATCH_PREDICT_RECORDS is rejected before any upload (#278)."""
    svc = _service()
    monkeypatch.setattr(
        "app.services.batch_prediction.MAX_BATCH_PREDICT_RECORDS", 2
    )
    df = pd.DataFrame([{"age": i} for i in range(3)])

    with pytest.raises(ValueError, match="exceeds the maximum"):
        await svc._prepare_input_data(df, "u1", "m1")

    svc.s3_service.upload_file_obj.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_batch_job_streams_results_across_chunks(monkeypatch):
    """Results stream to one file across chunks; summary folds incrementally (#278).

    Drives the full chunk loop with a passthrough feature engineer + fake
    classifier over two chunks and asserts the uploaded CSV contains every row in
    order with a single header, and the summary counts all successes — proving
    results are not accumulated per-chunk in memory.
    """
    svc = _service()

    uploaded: dict[str, Any] = {}

    async def _capture_upload(fh, key):
        uploaded["key"] = key
        uploaded["content"] = fh.read()
        return f"s3://bucket/{key}"

    svc.s3_service.upload_file_obj = AsyncMock(side_effect=_capture_upload)
    svc.model_storage.load_model = AsyncMock(
        return_value=(_FakeClassifier(), _FakeFeatureEngineer())
    )

    model = _model()
    monkeypatch.setattr(
        "app.services.batch_prediction.MLModel.find_one",
        AsyncMock(return_value=model),
    )

    chunk1 = pd.DataFrame([{"age": 30}, {"age": 40}])
    chunk2 = pd.DataFrame([{"age": 50}])

    async def _chunks(path, size):
        yield chunk1
        yield chunk2

    monkeypatch.setattr(svc, "_read_data_chunks", _chunks)

    job = MagicMock()
    job.user_id = "u1"
    job.input_path = "batch-jobs/u1/model_123/input.csv"
    job.config = BatchPredictionConfig(
        model_id="model_123", include_probabilities=True, output_format="csv"
    ).dict()
    job.save = AsyncMock()

    await svc._process_batch_job(job)

    job.mark_completed.assert_called_once()
    summary = job.mark_completed.call_args[0][0]
    assert summary["total_predictions"] == 3
    assert summary["success_count"] == 3

    out = pd.read_csv(io.BytesIO(uploaded["content"]))
    assert len(out) == 3
    assert list(out["age"]) == [30, 40, 50]
    assert "prediction" in out.columns
    assert "confidence" in out.columns


@pytest.mark.asyncio
async def test_process_batch_job_isolates_a_failed_chunk(monkeypatch):
    """A chunk whose inference blows up becomes per-row error rows, job completes (#278)."""
    svc = _service()

    uploaded: dict[str, Any] = {}

    async def _capture_upload(fh, key):
        uploaded["content"] = fh.read()
        return f"s3://bucket/{key}"

    svc.s3_service.upload_file_obj = AsyncMock(side_effect=_capture_upload)
    svc.model_storage.load_model = AsyncMock(
        return_value=(_FakeClassifier(), _FakeFeatureEngineer())
    )
    monkeypatch.setattr(
        "app.services.batch_prediction.MLModel.find_one",
        AsyncMock(return_value=_model()),
    )

    async def _chunks(path, size):
        yield pd.DataFrame([{"age": 30}])

    monkeypatch.setattr(svc, "_read_data_chunks", _chunks)
    # Force the whole chunk to fail so the outer per-chunk isolation kicks in.
    monkeypatch.setattr(
        svc, "_predict_chunk", AsyncMock(side_effect=RuntimeError("boom"))
    )

    job = MagicMock()
    job.user_id = "u1"
    job.input_path = "in.csv"
    job.config = BatchPredictionConfig(
        model_id="model_123", output_format="csv"
    ).dict()
    job.save = AsyncMock()

    await svc._process_batch_job(job)

    job.mark_completed.assert_called_once()
    summary = job.mark_completed.call_args[0][0]
    assert summary["total_predictions"] == 1
    assert summary["error_count"] == 1
    out = pd.read_csv(io.BytesIO(uploaded["content"]))
    assert "error" in out.columns


@pytest.mark.asyncio
async def test_prepare_input_data_uploads_dataframe():
    """A DataFrame input is uploaded as CSV bytes via upload_file_obj (#82)."""
    svc = _service()
    df = pd.DataFrame([{"age": 1}, {"age": 2}, {"age": 3}])

    key, total = await svc._prepare_input_data(df, "test_user_123", "model_123")

    assert total == 3
    assert key.endswith("input.csv")
    svc.s3_service.upload_file_obj.assert_awaited_once()


# --- Async-completion webhook (issue #86) ---------------------------------


def _completed_job(webhook_url=None, webhook_secret=None, status=None):
    """A minimal terminal-state batch job (no Mongo) for _fire_webhook."""
    from app.models.batch_job import JobStatus

    job = MagicMock()
    job.job_id = "batch_1"
    job.status = status or JobStatus.COMPLETED
    job.results = {"prediction_distribution": {"yes": 2}}
    job.completed_at = datetime(2026, 1, 1, 12, 0, 0)
    job.config = {
        "model_id": "model_123",
        "webhook_url": webhook_url,
        "webhook_secret": webhook_secret,
    }
    return job


def _patch_httpx(monkeypatch, post, *, safe=True):
    """Patch httpx.AsyncClient so _fire_webhook's POST is captured.

    ``safe=True`` also stubs DNS resolution to a public IP so the SSRF guard
    (``_is_safe_webhook_url``) passes for the test's fake host.
    """
    client = MagicMock()
    client.post = post
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(
        "app.services.batch_prediction.httpx.AsyncClient",
        lambda *a, **k: client,
    )
    # Don't actually wait out the retry backoff in tests.
    monkeypatch.setattr(
        "app.services.batch_prediction.asyncio.sleep", AsyncMock()
    )
    if safe:
        monkeypatch.setattr(
            "app.services.batch_prediction.socket.getaddrinfo",
            lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 443))],
        )


@pytest.mark.asyncio
async def test_fire_webhook_noop_without_url(monkeypatch):
    post = AsyncMock()
    _patch_httpx(monkeypatch, post)
    await _service()._fire_webhook(_completed_job())
    post.assert_not_awaited()


@pytest.mark.asyncio
async def test_fire_webhook_posts_signed_summary(monkeypatch):
    import hashlib
    import hmac

    post = AsyncMock()
    _patch_httpx(monkeypatch, post)

    job = _completed_job("https://hook.example/cb", "s3cr3t")
    await _service()._fire_webhook(job)

    post.assert_awaited_once()
    _, kwargs = post.call_args
    body = kwargs["content"]
    payload = json.loads(body)
    assert payload["job_id"] == "batch_1"
    assert payload["status"] == "completed"
    assert payload["summary"] == {"prediction_distribution": {"yes": 2}}
    # Signature is HMAC-SHA256 of the raw body with the secret.
    expected = hmac.new(b"s3cr3t", body, hashlib.sha256).hexdigest()
    assert kwargs["headers"]["X-Signature"] == expected


@pytest.mark.asyncio
async def test_fire_webhook_unsigned_when_no_secret(monkeypatch):
    post = AsyncMock()
    _patch_httpx(monkeypatch, post)
    await _service()._fire_webhook(_completed_job("https://hook.example/cb"))
    _, kwargs = post.call_args
    assert "X-Signature" not in kwargs["headers"]


@pytest.mark.asyncio
async def test_fire_webhook_never_raises_on_failure(monkeypatch):
    post = AsyncMock(side_effect=RuntimeError("boom"))
    _patch_httpx(monkeypatch, post)
    # Must swallow the error (and retry once → two attempts).
    await _service()._fire_webhook(_completed_job("https://hook.example/cb"))
    assert post.await_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("status_name", ["FAILED", "CANCELLED"])
async def test_fire_webhook_fires_on_non_completed_terminal_state(
    monkeypatch, status_name
):
    # The webhook fires on every terminal state, not just COMPLETED — the payload
    # carries the real status so receivers can act on failures/cancellations.
    from app.models.batch_job import JobStatus

    post = AsyncMock()
    _patch_httpx(monkeypatch, post)
    job = _completed_job("https://hook.example/cb", status=JobStatus[status_name])
    await _service()._fire_webhook(job)
    post.assert_awaited_once()
    _, kwargs = post.call_args
    assert json.loads(kwargs["content"])["status"] == status_name.lower()


def test_create_batch_route_exposes_webhook_form_params():
    # Guardrail: a refactor that drops the webhook Form params from the route
    # would silently break webhook registration (review #5).
    import inspect

    from app.api.routes.batch_prediction import create_batch_job

    params = inspect.signature(create_batch_job).parameters
    assert "webhook_url" in params
    assert "webhook_secret" in params
    # ...and the config model round-trips them through to the job.
    cfg = BatchPredictionConfig(
        model_id="m", webhook_url="https://h/cb", webhook_secret="s"
    ).dict()
    assert cfg["webhook_url"] == "https://h/cb"
    assert cfg["webhook_secret"] == "s"


@pytest.mark.asyncio
async def test_fire_webhook_retries_on_non_2xx(monkeypatch):
    # httpx doesn't raise on 5xx by default; _fire_webhook calls raise_for_status
    # so a non-2xx is retried, not silently treated as delivered (#86 review).
    response = MagicMock()
    response.raise_for_status.side_effect = RuntimeError("500")
    post = AsyncMock(return_value=response)
    _patch_httpx(monkeypatch, post)
    await _service()._fire_webhook(_completed_job("https://hook.example/cb"))
    assert post.await_count == 2


def test_redact_config_masks_webhook_secret():
    # The job-status API must never echo the HMAC signing key (review #4).
    from app.api.routes.batch_prediction import _redact_config

    redacted = _redact_config(
        {"model_id": "m", "webhook_url": "https://h/cb", "webhook_secret": "s3cr3t"}
    )
    assert redacted["webhook_secret"] == "****"
    assert redacted["webhook_url"] == "https://h/cb"  # non-secret fields preserved
    # No secret present → unchanged.
    assert _redact_config({"model_id": "m"}) == {"model_id": "m"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/cb",  # loopback
        "http://169.254.169.254/latest/meta-data",  # cloud metadata (link-local)
        "http://10.0.0.5/cb",  # RFC1918 private
        "ftp://example.com/cb",  # non-http scheme
        "not-a-url",
    ],
)
async def test_fire_webhook_blocks_ssrf_targets(monkeypatch, url):
    # The unsafe URL must never fire. Stub getaddrinfo to echo the host's literal
    # IP so the guard's classification logic is exercised deterministically (not
    # real DNS, which varies by CI runner for e.g. link-local 169.254.x).
    def fake_getaddrinfo(host, *a, **k):
        return [(2, 1, 6, "", (host, 0))]  # host is a literal IP for these cases

    monkeypatch.setattr(
        "app.services.batch_prediction.socket.getaddrinfo", fake_getaddrinfo
    )
    post = AsyncMock()
    _patch_httpx(monkeypatch, post, safe=False)
    await _service()._fire_webhook(_completed_job(url))
    post.assert_not_awaited()
