"""Tests for the model-artifact TTL-LRU cache in ModelStorageService (issue #265).

``load_model`` previously re-downloaded + ``joblib.load``-ed the estimator and
feature transformer from S3 on every prediction. A bounded TTL-LRU cache keyed by
``(model_id, user_id)`` now serves hot artifacts without touching S3 or Mongo, and
is invalidated on delete/retrain/deploy.
"""

import threading
from unittest.mock import AsyncMock, MagicMock

import pytest

import app.services.model_storage as model_storage
from app.services.model_storage import (
    ModelStorageService,
    _ModelArtifactCache,
    get_inference_lock,
    invalidate_model_cache,
)

# TestLoadModelCaching builds Beanie query expressions (MLModel.model_id == ...),
# which require the document models to be registered (mongomock, service-free).
pytestmark = [pytest.mark.usefixtures("beanie_models_initialized")]


@pytest.fixture(autouse=True)
def _clear_cache():
    """Isolate each test — the cache is process-global."""
    model_storage._model_cache.clear()
    yield
    model_storage._model_cache.clear()


class TestModelArtifactCache:
    """Pure cache semantics — no S3/Mongo."""

    @pytest.mark.unit
    def test_get_miss_returns_none(self):
        cache = _ModelArtifactCache(max_size=4, ttl=100.0)
        assert cache.get(("m1", "u1")) is None

    @pytest.mark.unit
    def test_put_then_get_hits(self):
        cache = _ModelArtifactCache(max_size=4, ttl=100.0)
        cache.put(("m1", "u1"), ("est", "fe"))
        assert cache.get(("m1", "u1")) == ("est", "fe")

    @pytest.mark.unit
    def test_keyed_by_model_and_user(self):
        cache = _ModelArtifactCache(max_size=4, ttl=100.0)
        cache.put(("m1", "u1"), "a")
        assert cache.get(("m1", "u2")) is None  # different user → miss

    @pytest.mark.unit
    def test_ttl_expiry(self, monkeypatch):
        clock = {"t": 1000.0}
        monkeypatch.setattr(model_storage.time, "monotonic", lambda: clock["t"])
        cache = _ModelArtifactCache(max_size=4, ttl=30.0)
        cache.put(("m1", "u1"), "a")
        clock["t"] = 1029.0
        assert cache.get(("m1", "u1")) == "a"  # still fresh
        clock["t"] = 1031.0
        assert cache.get(("m1", "u1")) is None  # expired

    @pytest.mark.unit
    def test_maxsize_evicts_lru(self):
        cache = _ModelArtifactCache(max_size=2, ttl=100.0)
        cache.put(("m1", "u"), "a")
        cache.put(("m2", "u"), "b")
        cache.get(("m1", "u"))  # touch m1 → m2 is now LRU
        cache.put(("m3", "u"), "c")  # evicts m2
        assert cache.get(("m1", "u")) == "a"
        assert cache.get(("m3", "u")) == "c"
        assert cache.get(("m2", "u")) is None

    @pytest.mark.unit
    def test_invalidate_evicts(self):
        cache = _ModelArtifactCache(max_size=4, ttl=100.0)
        cache.put(("m1", "u1"), "a")
        cache.invalidate(("m1", "u1"))
        assert cache.get(("m1", "u1")) is None

    @pytest.mark.unit
    def test_disabled_when_ttl_or_size_nonpositive(self):
        for cache in (_ModelArtifactCache(0, 100.0), _ModelArtifactCache(4, 0.0)):
            cache.put(("m1", "u1"), "a")
            assert cache.get(("m1", "u1")) is None


class TestInferenceLock:
    """Per-model inference lock guards the shared cached estimator (issue #265)."""

    @pytest.mark.unit
    def test_same_key_returns_same_lock(self):
        lock = get_inference_lock("m1", "u1")
        assert isinstance(lock, type(threading.Lock()))
        assert get_inference_lock("m1", "u1") is lock  # reused, so it can guard

    @pytest.mark.unit
    def test_different_model_or_user_gets_distinct_lock(self):
        base = get_inference_lock("m1", "u1")
        assert get_inference_lock("m2", "u1") is not base  # other model → parallel
        assert get_inference_lock("m1", "u2") is not base  # other user → parallel


def _mock_ml_model():
    ml = MagicMock()
    ml.model_path = "s3://bucket/models/u1/m1/model.pkl"
    ml.feature_transformer_path = None
    ml.model_signature = None  # pre-#266: loads with a warning, no verification
    ml.feature_transformer_signature = None
    ml.save = AsyncMock()
    return ml


class TestLoadModelCaching:
    """load_model dedups S3 + joblib work through the cache."""

    @pytest.mark.asyncio
    async def test_second_load_is_a_cache_hit(self, monkeypatch):
        service = ModelStorageService()
        service.s3_service.bucket_name = "bucket"
        service.s3_service.download_file_obj = AsyncMock(return_value=b"bytes")
        monkeypatch.setattr(model_storage.joblib, "load", lambda buf: "ESTIMATOR")
        monkeypatch.setattr(
            model_storage.MLModel, "find_one", AsyncMock(return_value=_mock_ml_model())
        )

        first = await service.load_model("m1", "u1")
        second = await service.load_model("m1", "u1")

        assert first == ("ESTIMATOR", None)
        assert second == first
        # S3 + Mongo touched exactly once despite two loads.
        service.s3_service.download_file_obj.assert_awaited_once()
        model_storage.MLModel.find_one.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_invalidate_forces_reload(self, monkeypatch):
        service = ModelStorageService()
        service.s3_service.bucket_name = "bucket"
        service.s3_service.download_file_obj = AsyncMock(return_value=b"bytes")
        monkeypatch.setattr(model_storage.joblib, "load", lambda buf: "ESTIMATOR")
        monkeypatch.setattr(
            model_storage.MLModel, "find_one", AsyncMock(return_value=_mock_ml_model())
        )

        await service.load_model("m1", "u1")
        invalidate_model_cache("m1", "u1")
        await service.load_model("m1", "u1")

        assert service.s3_service.download_file_obj.await_count == 2

    @pytest.mark.asyncio
    async def test_different_user_does_not_share_cache(self, monkeypatch):
        service = ModelStorageService()
        service.s3_service.bucket_name = "bucket"
        service.s3_service.download_file_obj = AsyncMock(return_value=b"bytes")
        monkeypatch.setattr(model_storage.joblib, "load", lambda buf: "ESTIMATOR")
        monkeypatch.setattr(
            model_storage.MLModel, "find_one", AsyncMock(return_value=_mock_ml_model())
        )

        await service.load_model("m1", "u1")
        await service.load_model("m1", "u2")  # foreign user → miss → reload

        assert service.s3_service.download_file_obj.await_count == 2
