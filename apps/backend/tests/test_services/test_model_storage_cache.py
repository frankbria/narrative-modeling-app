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


def _mock_ml_model(cache_generation: int = 0):
    ml = MagicMock()
    ml.model_path = "s3://bucket/models/u1/m1/model.pkl"
    ml.feature_transformer_path = None
    ml.model_signature = None  # pre-#266: loads with a warning, no verification
    ml.feature_transformer_signature = None
    ml.cache_generation = cache_generation  # #489 cross-worker generation
    # load_model stamps last_used_at via an atomic single-field .set() (#279),
    # not a full-document .save().
    ml.set = AsyncMock()
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
        # The expensive S3 download + joblib.load happens exactly once. The cache
        # hit still costs one cheap indexed Mongo read to confirm the generation
        # hasn't advanced on another worker (#489), so find_one runs twice: the
        # initial metadata load and the freshness check.
        service.s3_service.download_file_obj.assert_awaited_once()
        assert model_storage.MLModel.find_one.await_count == 2

    @pytest.mark.asyncio
    async def test_cache_hit_skips_mongo_when_generation_passed(self, monkeypatch):
        # The production hot path already read the doc, so it passes
        # expected_generation and a cache hit does zero Mongo work (#489).
        service = ModelStorageService()
        service.s3_service.bucket_name = "bucket"
        service.s3_service.download_file_obj = AsyncMock(return_value=b"bytes")
        monkeypatch.setattr(model_storage.joblib, "load", lambda buf: "ESTIMATOR")
        monkeypatch.setattr(
            model_storage.MLModel, "find_one", AsyncMock(return_value=_mock_ml_model())
        )

        await service.load_model("m1", "u1")  # cold: find_one #1
        again = await service.load_model("m1", "u1", expected_generation=0)

        assert again == ("ESTIMATOR", None)
        service.s3_service.download_file_obj.assert_awaited_once()
        model_storage.MLModel.find_one.assert_awaited_once()  # no freshness query

    @pytest.mark.asyncio
    async def test_higher_generation_forces_reload(self, monkeypatch):
        # A sibling worker's invalidate bumps cache_generation in Mongo; the next
        # load here sees the higher generation and reloads the artifact (#489).
        service = ModelStorageService()
        service.s3_service.bucket_name = "bucket"
        service.s3_service.download_file_obj = AsyncMock(return_value=b"bytes")
        monkeypatch.setattr(model_storage.joblib, "load", lambda buf: "ESTIMATOR")
        # First load caches generation 0; the freshness check then returns 1.
        monkeypatch.setattr(
            model_storage.MLModel,
            "find_one",
            AsyncMock(
                side_effect=[
                    _mock_ml_model(cache_generation=0),  # cold load
                    _mock_ml_model(cache_generation=1),  # freshness check → stale
                    _mock_ml_model(cache_generation=1),  # reload metadata
                ]
            ),
        )

        await service.load_model("m1", "u1")
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


def _make_real_model(model_id="m1", user_id="u1", cache_generation=0) -> "model_storage.MLModel":
    """A real (insertable) MLModel doc — the cross-worker tests need shared Mongo."""
    return model_storage.MLModel(
        user_id=user_id,
        dataset_id="dataset_123",
        model_id=model_id,
        name="Test Model",
        problem_type="binary_classification",
        algorithm="Random Forest",
        target_column="target",
        feature_names=["f1", "f2"],
        cv_score=0.85,
        test_score=0.83,
        training_time=1.0,
        model_size=1024,
        n_samples_train=100,
        n_features=2,
        model_path="s3://bucket/models/u1/m1/model.pkl",
        cache_generation=cache_generation,
    )


class TestCrossWorkerInvalidation:
    """#489: the cache is process-local but 2 workers share Mongo. Invalidation
    must propagate via the persisted ``cache_generation`` so no worker serves a
    deleted/retrained/redeployed model from a stale local entry."""

    @pytest.mark.asyncio
    async def test_invalidate_bumps_shared_generation(self, setup_database):
        # AC1: invalidate writes a cross-worker signal to shared Mongo.
        doc = await _make_real_model().insert()
        assert doc.cache_generation == 0

        await invalidate_model_cache("m1", "u1")

        refetched = await model_storage.MLModel.find_one(
            model_storage.MLModel.model_id == "m1",
            model_storage.MLModel.user_id == "u1",
        )
        assert refetched.cache_generation == 1

    @pytest.mark.asyncio
    async def test_sibling_invalidation_observed_on_next_load(
        self, setup_database, monkeypatch
    ):
        # AC3/AC4: a bump made by another worker (shared Mongo only, this worker's
        # local cache untouched) is observed on the next load, which reloads.
        await _make_real_model().insert()
        service = ModelStorageService()
        service.s3_service.bucket_name = "bucket"
        service.s3_service.download_file_obj = AsyncMock(return_value=b"bytes")
        artifact = {"v": "OLD"}
        monkeypatch.setattr(model_storage.joblib, "load", lambda buf: artifact["v"])

        first = await service.load_model("m1", "u1")
        assert first == ("OLD", None)

        # Sibling worker bumps the shared generation but does NOT touch this
        # process's cache — exactly the cross-worker condition.
        await model_storage.MLModel.find_one(
            model_storage.MLModel.model_id == "m1",
            model_storage.MLModel.user_id == "u1",
        ).update(model_storage.Inc({model_storage.MLModel.cache_generation: 1}))
        artifact["v"] = "NEW"

        second = await service.load_model("m1", "u1")
        assert second == ("NEW", None)  # stale hit detected, reloaded
        assert service.s3_service.download_file_obj.await_count == 2

    @pytest.mark.asyncio
    async def test_deleted_model_not_served_from_cache(
        self, setup_database, monkeypatch
    ):
        # AC2: after a delete on another worker, a cached hit must not answer.
        doc = await _make_real_model().insert()
        service = ModelStorageService()
        service.s3_service.bucket_name = "bucket"
        service.s3_service.download_file_obj = AsyncMock(return_value=b"bytes")
        monkeypatch.setattr(model_storage.joblib, "load", lambda buf: "ESTIMATOR")

        await service.load_model("m1", "u1")  # populate cache
        await doc.delete()  # sibling worker deletes the model

        with pytest.raises(ValueError, match="not found"):
            await service.load_model("m1", "u1")

    @pytest.mark.asyncio
    async def test_key_scoping_survives(self, setup_database, monkeypatch):
        # AC5: the (model_id, user_id) key must not regress to model_id-only —
        # one user's invalidation must not disturb another user's same-id model.
        await _make_real_model(user_id="u1").insert()
        await _make_real_model(user_id="u2").insert()
        service = ModelStorageService()
        service.s3_service.bucket_name = "bucket"
        service.s3_service.download_file_obj = AsyncMock(return_value=b"bytes")
        monkeypatch.setattr(model_storage.joblib, "load", lambda buf: "ESTIMATOR")

        await service.load_model("m1", "u1")
        await service.load_model("m1", "u2")
        assert service.s3_service.download_file_obj.await_count == 2

        await invalidate_model_cache("m1", "u1")  # only u1's model

        # u2 is a cache hit (its generation is unchanged) — no reload.
        await service.load_model("m1", "u2", expected_generation=0)
        assert service.s3_service.download_file_obj.await_count == 2
        # u1 reloads (its generation advanced).
        await service.load_model("m1", "u1")
        assert service.s3_service.download_file_obj.await_count == 3
