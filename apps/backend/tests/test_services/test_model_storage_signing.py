"""Artifact signature verification in ModelStorageService.load_model (issue #266).

A bucket tamperer can replace ``model.pkl`` in S3, but the HMAC signature lives in
the trusted Mongo doc. ``load_model`` recomputes the HMAC over the downloaded bytes
and refuses to ``joblib.load`` anything that doesn't match.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

import app.services.model_storage as model_storage
from app.services.model_storage import ModelStorageService
from app.utils.artifact_signing import sign_bytes

pytestmark = [pytest.mark.usefixtures("beanie_models_initialized")]


@pytest.fixture(autouse=True)
def _clear_cache():
    model_storage._model_cache.clear()
    yield
    model_storage._model_cache.clear()


def _mock_ml_model(signature):
    ml = MagicMock()
    ml.model_path = "s3://bucket/models/u1/m1/model.pkl"
    ml.feature_transformer_path = None
    ml.model_signature = signature
    ml.feature_transformer_signature = None
    ml.save = AsyncMock()
    return ml


def _service(download_bytes):
    service = ModelStorageService()
    service.s3_service.bucket_name = "bucket"
    service.s3_service.download_file_obj = AsyncMock(return_value=download_bytes)
    return service


@pytest.mark.asyncio
async def test_valid_signature_loads(monkeypatch):
    data = b"\x80\x04genuine joblib bytes"
    service = _service(data)
    monkeypatch.setattr(model_storage.joblib, "load", lambda buf: "ESTIMATOR")
    monkeypatch.setattr(
        model_storage.MLModel,
        "find_one",
        AsyncMock(return_value=_mock_ml_model(sign_bytes(data))),
    )

    model, fe = await service.load_model("m1", "u1")
    assert model == "ESTIMATOR"
    assert fe is None


@pytest.mark.asyncio
async def test_tampered_bytes_are_refused(monkeypatch):
    # Signature was computed over the original artifact; S3 now returns different
    # (attacker-controlled) bytes → verification fails → refuse to deserialize.
    good_sig = sign_bytes(b"original artifact")
    service = _service(b"\x80\x04MALICIOUS payload")
    # joblib.load must never be reached; make it explode if it is.
    def _must_not_run(buf):
        # Raise a real AssertionError — pytest.fail() inside a to_thread worker
        # surfaces as a confusing background exception rather than a clean failure.
        raise AssertionError("joblib.load ran on tampered bytes")

    monkeypatch.setattr(model_storage.joblib, "load", _must_not_run)
    monkeypatch.setattr(
        model_storage.MLModel,
        "find_one",
        AsyncMock(return_value=_mock_ml_model(good_sig)),
    )

    with pytest.raises(ValueError, match="signature mismatch"):
        await service.load_model("m1", "u1")


@pytest.mark.asyncio
async def test_unsigned_legacy_model_loads_with_warning(monkeypatch, caplog):
    service = _service(b"legacy bytes")
    monkeypatch.setattr(model_storage.joblib, "load", lambda buf: "ESTIMATOR")
    monkeypatch.setattr(
        model_storage.MLModel,
        "find_one",
        AsyncMock(return_value=_mock_ml_model(None)),
    )

    loaded = MagicMock(return_value="ESTIMATOR")
    monkeypatch.setattr(model_storage.joblib, "load", loaded)

    with caplog.at_level("WARNING"):
        model, _ = await service.load_model("m1", "u1")

    assert model == "ESTIMATOR"
    loaded.assert_called_once()  # actually deserialized, not a hardcoded sentinel
    assert any("unsigned" in r.message.lower() for r in caplog.records)
