"""
Tests for production API endpoints.

The HTTP-level cases run against the *real* app (``async_authorized_client``,
which mounts the production router) with real MongoDB documents and assert exact
statuses + bodies — replacing the pre-#267 suite that drove a stub app mounting
only two routers, so every ``/api/v1/production/*`` request 404'd and the
``in [200, 404, 422]`` assertions tested nothing.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from fastapi import HTTPException
from sklearn.ensemble import RandomForestClassifier

from app.api.routes.production import (
    ProductionPredictRequest,
    hash_api_key,
    production_predict,
)
from app.models.api_key import APIKey
from app.models.ml_model import MLModel

TEST_USER = "test_user_123"  # matches async_authorized_client's overridden auth


def _make_model(
    model_id: str = "model_123",
    user_id: str = TEST_USER,
    feature_names: list[str] | None = None,
    is_active: bool = True,
) -> MLModel:
    return MLModel(
        user_id=user_id,
        dataset_id="dataset_123",
        model_id=model_id,
        name="Test Model",
        problem_type="binary_classification",
        algorithm="Random Forest",
        target_column="target",
        feature_names=feature_names or ["feature1", "feature2", "feature3"],
        cv_score=0.85,
        test_score=0.83,
        training_time=45.2,
        model_size=1048576,
        n_samples_train=1000,
        n_features=len(feature_names or ["feature1", "feature2", "feature3"]),
        model_path="s3://bucket/models/model_123.pkl",
        version="1.0.0",
        is_active=is_active,
    )


def _make_api_key(
    raw_key: str,
    user_id: str = TEST_USER,
    model_ids: list[str] | None = None,
) -> APIKey:
    return APIKey(
        key_id=f"key_{raw_key[-8:]}",
        key_hash=hash_api_key(raw_key),
        name="Test API Key",
        user_id=user_id,
        rate_limit=1000,
        is_active=True,
        model_ids=model_ids or [],
    )


class TestProductionUnit:
    """Pure-unit cases with no app/DB dependency."""

    def test_hash_api_key(self):
        """Hashing is deterministic, SHA256-shaped, and collision-free per key."""
        key = "sk_live_test123"
        hash1 = hash_api_key(key)
        hash2 = hash_api_key(key)

        assert hash1 == hash2
        assert len(hash1) == 64
        assert all(c in "0123456789abcdef" for c in hash1)
        assert hash1 != hash_api_key("sk_live_different")

    @pytest.mark.asyncio
    async def test_verify_api_key_format(self):
        """A key missing the sk_live_ prefix (or empty) is rejected 401."""
        from app.api.routes.production import verify_api_key

        with pytest.raises(HTTPException) as exc_info:
            await verify_api_key(api_key="invalid_format")
        assert exc_info.value.status_code == 401

        with pytest.raises(HTTPException) as exc_info:
            await verify_api_key(api_key="")
        assert exc_info.value.status_code == 401


class TestApiKeyModelAccess:
    """Exercise the REAL APIKey.has_model_access — the cross-tenant authz control
    the production route relies on (pre-#267 this test redefined a local copy and
    never touched the shipped method). Beanie isn't initialized here, so we invoke
    the real unbound method with a duck-typed ``self`` carrying model_ids; the
    integration serving tests below cover it through the route as well."""

    @staticmethod
    def _access(model_ids: list[str], model_id: str) -> bool:
        return APIKey.has_model_access(SimpleNamespace(model_ids=model_ids), model_id)

    def test_scoped_key_allows_only_listed_models(self):
        listed = ["model_123", "model_456"]
        assert self._access(listed, "model_123") is True
        assert self._access(listed, "model_456") is True
        assert self._access(listed, "model_789") is False

    def test_unscoped_key_allows_all_models(self):
        assert self._access([], "model_123") is True
        assert self._access([], "any_model") is True


@pytest.mark.integration
class TestProductionAPIKeyManagement:
    """API-key CRUD against the real app + MongoDB (session-authed surface)."""

    @pytest.mark.asyncio
    async def test_create_list_and_revoke_api_key(
        self, async_authorized_client, setup_database
    ):
        # Create — returns the plaintext key exactly once.
        create = await async_authorized_client.post(
            "/api/v1/production/api-keys",
            json={
                "name": "Production Key",
                "description": "Test key for production",
                "rate_limit": 5000,
                "expires_in_days": 30,
            },
        )
        assert create.status_code == 200
        body = create.json()
        assert body["name"] == "Production Key"
        assert body["rate_limit"] == 5000
        assert body["api_key"].startswith("sk_live_")
        key_id = body["key_id"]

        # List — the new key is present (plaintext key never re-exposed).
        listed = await async_authorized_client.get("/api/v1/production/api-keys")
        assert listed.status_code == 200
        keys = listed.json()
        entry = next(k for k in keys if k["key_id"] == key_id)
        assert entry["name"] == "Production Key"
        assert entry["is_active"] is True
        assert "api_key" not in entry

        # Revoke — flips is_active off.
        revoke = await async_authorized_client.delete(
            f"/api/v1/production/api-keys/{key_id}"
        )
        assert revoke.status_code == 200
        assert revoke.json() == {"message": "API key revoked successfully"}

        after = (await async_authorized_client.get("/api/v1/production/api-keys")).json()
        assert next(k for k in after if k["key_id"] == key_id)["is_active"] is False

    @pytest.mark.asyncio
    async def test_create_api_key_invalid_data_rejected(
        self, async_authorized_client, setup_database
    ):
        """A malformed body (missing the required name) is a 422, not a silent pass."""
        resp = await async_authorized_client.post(
            "/api/v1/production/api-keys", json={"rate_limit": 5000}
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_revoke_unknown_key_returns_404(
        self, async_authorized_client, setup_database
    ):
        resp = await async_authorized_client.delete(
            "/api/v1/production/api-keys/key_does_not_exist"
        )
        assert resp.status_code == 404


@pytest.mark.integration
class TestProductionServing:
    """The core deployed-model REST API driven end to end with real API-key auth,
    real MongoDB documents, and (for the happy path) a real fitted estimator."""

    @pytest.mark.asyncio
    async def test_predict_without_api_key_returns_422(
        self, async_authorized_client, setup_database
    ):
        """X-API-Key is a required header — omitting it is a 422 (FastAPI validation)."""
        resp = await async_authorized_client.post(
            "/api/v1/production/v1/models/model_123/predict",
            json={"data": [{"feature1": 1, "feature2": "value"}]},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_predict_with_malformed_api_key_returns_401(
        self, async_authorized_client, setup_database
    ):
        resp = await async_authorized_client.post(
            "/api/v1/production/v1/models/model_123/predict",
            json={"data": [{"feature1": 1}]},
            headers={"X-API-Key": "not_a_real_key"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid API key format"

    @pytest.mark.asyncio
    async def test_predict_with_unknown_api_key_returns_401(
        self, async_authorized_client, setup_database
    ):
        """A well-formed but unregistered sk_live_ key is rejected 401."""
        resp = await async_authorized_client.post(
            "/api/v1/production/v1/models/model_123/predict",
            json={"data": [{"feature1": 1}]},
            headers={"X-API-Key": "sk_live_unregistered_key_value_0000"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid API key"

    @pytest.mark.asyncio
    async def test_predict_forbidden_when_key_lacks_model_access(
        self, async_authorized_client, setup_database
    ):
        """A key scoped to other models gets 403 via the real has_model_access —
        before any model lookup."""
        raw = "sk_live_scoped_serving_key_00001"
        await _make_api_key(raw, model_ids=["some_other_model"]).insert()

        resp = await async_authorized_client.post(
            "/api/v1/production/v1/models/model_123/predict",
            json={"data": [{"feature1": 1, "feature2": 2, "feature3": 3}]},
            headers={"X-API-Key": raw},
        )
        assert resp.status_code == 403
        assert resp.json()["detail"] == "API key does not have access to this model"

    @pytest.mark.asyncio
    async def test_predict_cross_tenant_model_returns_404(
        self, async_authorized_client, setup_database
    ):
        """An all-access key can't reach a model owned by a different user: the
        MLModel lookup is scoped to the key's own user_id, so it 404s."""
        await _make_model(model_id="owned_by_a", user_id="owner_a").insert()
        raw = "sk_live_tenant_b_key_000000000001"
        await _make_api_key(raw, user_id="tenant_b", model_ids=[]).insert()

        resp = await async_authorized_client.post(
            "/api/v1/production/v1/models/owned_by_a/predict",
            json={"data": [{"feature1": 1, "feature2": 2, "feature3": 3}]},
            headers={"X-API-Key": raw},
        )
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Model not found or inactive"

    @pytest.mark.asyncio
    async def test_end_to_end_serving_with_real_fitted_model(
        self, async_authorized_client, setup_database
    ):
        """Full serving path: real API-key auth → real has_model_access → real
        MLModel lookup → real fitted RandomForest inference → enriched response.
        Only the S3 artifact download (load_model) is stubbed with a genuinely
        fitted estimator."""
        features = ["feature1", "feature2", "feature3"]
        await _make_model(feature_names=features).insert()
        raw = "sk_live_e2e_serving_key_0000000001"
        await _make_api_key(raw, model_ids=[]).insert()

        # A real, fitted classifier whose columns match model.feature_names.
        rng = np.random.default_rng(0)
        import pandas as pd

        X = pd.DataFrame(rng.random((40, 3)), columns=features)
        y = (X["feature1"] > 0.5).astype(int)
        clf = RandomForestClassifier(n_estimators=5, random_state=0).fit(X, y)

        with patch(
            "app.services.model_storage.ModelStorageService.load_model",
            new_callable=AsyncMock,
            return_value=(clf, None),  # no feature engineer -> df[feature_names]
        ):
            resp = await async_authorized_client.post(
                "/api/v1/production/v1/models/model_123/predict",
                json={
                    "data": [
                        {"feature1": 0.9, "feature2": 0.1, "feature3": 0.2},
                        {"feature1": 0.1, "feature2": 0.8, "feature3": 0.3},
                    ]
                },
                headers={"X-API-Key": raw},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert len(body["predictions"]) == 2
        assert body["model_version"] == "1.0.0"
        # Enrichment ran end to end: per-record confidence derived from proba.
        assert body["confidence"] is not None
        assert len(body["confidence"]) == 2
        assert all(0.0 <= c <= 1.0 for c in body["confidence"])

    @pytest.mark.asyncio
    async def test_missing_required_feature_returns_422_over_http(
        self, async_authorized_client, setup_database
    ):
        """A record missing a required raw feature is a client 422 through the
        real HTTP stack, naming the missing feature (not a 500 leak)."""
        features = ["feature1", "feature2", "feature3"]
        await _make_model(feature_names=features).insert()
        raw = "sk_live_missing_feature_key_000001"
        await _make_api_key(raw, model_ids=[]).insert()

        with patch(
            "app.services.model_storage.ModelStorageService.load_model",
            new_callable=AsyncMock,
            return_value=(MagicMock(), None),
        ):
            resp = await async_authorized_client.post(
                "/api/v1/production/v1/models/model_123/predict",
                json={"data": [{"feature1": 1.0}]},  # feature2, feature3 missing
                headers={"X-API-Key": raw},
            )

        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert "feature2" in detail and "feature3" in detail

    @pytest.mark.asyncio
    async def test_get_model_info_returns_metadata(
        self, async_authorized_client, setup_database
    ):
        await _make_model().insert()
        raw = "sk_live_info_key_00000000000000001"
        await _make_api_key(raw, model_ids=[]).insert()

        resp = await async_authorized_client.get(
            "/api/v1/production/v1/models/model_123/info",
            headers={"X-API-Key": raw},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["model_id"] == "model_123"
        assert body["algorithm"] == "Random Forest"
        assert body["performance"]["cv_score"] == 0.85


class TestServingMetricsLogging:
    """Tests for per-request monitoring logging from the serving path (issue #85)."""

    @pytest.mark.asyncio
    async def test_logs_each_prediction(self):
        from app.api.routes.production import _record_serving_metrics
        from app.services.prediction_monitoring import prediction_log

        prediction_log.logs.clear()
        await _record_serving_metrics(
            model_id="m_serve",
            request_data=[{"a": 1}, {"a": 2}, {"a": 3}],
            predictions=["x", "y", "z"],
            confidence=[0.9, 0.8, None],
            latency_ms=30.0,
            api_key_id="key_1",
        )

        logged = prediction_log.logs["m_serve"]
        assert len(logged) == 3
        assert [e["prediction"] for e in logged] == ["x", "y", "z"]
        # Batch latency is split per record.
        assert all(e["latency_ms"] == 10.0 for e in logged)
        assert all(e["error"] is None for e in logged)
        assert logged[2]["probability"] is None

    @pytest.mark.asyncio
    async def test_logs_error_event(self):
        from app.api.routes.production import _record_serving_metrics
        from app.services.prediction_monitoring import prediction_log

        prediction_log.logs.clear()
        await _record_serving_metrics(
            model_id="m_err",
            request_data=[{"a": 1}],
            predictions=[],
            confidence=None,
            latency_ms=12.0,
            api_key_id="key_1",
            error="kaboom",
        )

        logged = prediction_log.logs["m_err"]
        assert len(logged) == 1
        assert logged[0]["error"] == "kaboom"
        assert logged[0]["prediction"] is None

    @pytest.mark.asyncio
    async def test_batch_error_logged_per_record(self):
        """A failed N-record batch logs N error entries so error_rate stays
        per-record consistent with successes (codex review)."""
        from app.api.routes.production import _record_serving_metrics
        from app.services.prediction_monitoring import (
            PredictionMonitoringService,
            prediction_log,
        )

        prediction_log.logs.clear()
        # One successful 3-record batch...
        await _record_serving_metrics(
            model_id="m_batch",
            request_data=[{"a": 1}, {"a": 2}, {"a": 3}],
            predictions=["x", "y", "z"],
            confidence=None,
            latency_ms=30.0,
            api_key_id="k",
        )
        # ...then one failed 3-record batch.
        await _record_serving_metrics(
            model_id="m_batch",
            request_data=[{"a": 4}, {"a": 5}, {"a": 6}],
            predictions=[],
            confidence=None,
            latency_ms=9.0,
            api_key_id="k",
            error="boom",
        )

        assert len(prediction_log.logs["m_batch"]) == 6
        metrics = await PredictionMonitoringService.get_model_metrics("m_batch", 24)
        assert metrics["total_predictions"] == 3
        assert metrics["error_count"] == 3
        assert metrics["error_rate"] == 0.5  # 3 / 6, not 1 / 4

    @pytest.mark.asyncio
    async def test_never_raises(self):
        """Monitoring logging must not break serving even on bad input."""
        from app.api.routes.production import _record_serving_metrics

        # predictions is None -> would raise inside; must be swallowed.
        await _record_serving_metrics(
            model_id="m_bad",
            request_data=[],
            predictions=None,  # type: ignore[arg-type]
            confidence=None,
            latency_ms=1.0,
            api_key_id=None,
        )


class TestProductionPredictErrorHandling:
    """Production serving predict mirrors the internal /ml twin (issue #264):
    client errors → 422 with a sanitized message, 500 reserved for true faults
    without echoing internal text, and a bounded record cap."""

    @staticmethod
    def _api_key() -> MagicMock:
        key = MagicMock(user_id="user_123", key_id="key_1")
        key.has_model_access.return_value = True
        return key

    @staticmethod
    def _model(problem_type: str = "binary_classification") -> MagicMock:
        return MagicMock(
            feature_names=["feature1", "feature2"],
            problem_type=problem_type,
            n_features=2,
            name="Test Model",
            algorithm="Random Forest",
            version="1.0.0",
            residual_std=None,
            is_calibrated=False,
            calibration_method=None,
            feature_importance=None,
        )

    def _patch_load(self, model):
        """Patch model lookup + artifact load; caller sets load_model's return
        inside the ``with`` block."""
        find = patch(
            "app.models.ml_model.MLModel.find_one",
            new_callable=AsyncMock,
            return_value=model,
        )
        load = patch(
            "app.services.model_storage.ModelStorageService.load_model",
            new_callable=AsyncMock,
        )
        return find, load

    @pytest.mark.asyncio
    async def test_missing_feature_returns_422(self):
        """A record missing a required raw input feature → 422, not 500."""
        model = self._model()
        find, load = self._patch_load(model)
        with find, load as mock_load:
            mock_load.return_value = (MagicMock(), None)  # no feature engineer
            request = ProductionPredictRequest(data=[{"feature1": 1.0}])  # feature2 missing

            with pytest.raises(HTTPException) as exc:
                await production_predict("model_123", request, self._api_key())

        assert exc.value.status_code == 422
        assert "feature2" in exc.value.detail
        assert "Missing required feature" in exc.value.detail

    @pytest.mark.asyncio
    async def test_empty_data_returns_422(self):
        """An empty records list is a client error → 422, not a 500."""
        model = self._model()
        find, load = self._patch_load(model)
        with find, load as mock_load:
            mock_load.return_value = (MagicMock(), None)
            request = ProductionPredictRequest(data=[])

            with pytest.raises(HTTPException) as exc:
                await production_predict("model_123", request, self._api_key())

        assert exc.value.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_feature_value_returns_422(self):
        """A sklearn ValueError (e.g. unknown category) → 422 sanitized, not 500."""
        model = self._model()
        trained = MagicMock()
        raw = "y contains previously unseen labels: 'SECRET-COLUMN'"
        trained.predict.side_effect = ValueError(raw)
        find, load = self._patch_load(model)
        with find, load as mock_load:
            mock_load.return_value = (trained, None)
            request = ProductionPredictRequest(
                data=[{"feature1": 1.0, "feature2": 2.0}]
            )

            with pytest.raises(HTTPException) as exc:
                await production_predict("model_123", request, self._api_key())

        assert exc.value.status_code == 422
        assert "Invalid feature value" in exc.value.detail
        assert raw not in exc.value.detail  # sanitized: no raw sklearn text leaked

    @pytest.mark.asyncio
    async def test_invalid_feature_keyerror_returns_422(self):
        """A KeyError from the transform/lookup path is also mapped to 422."""
        model = self._model()
        trained = MagicMock()
        trained.predict.side_effect = KeyError("feature2")
        find, load = self._patch_load(model)
        with find, load as mock_load:
            mock_load.return_value = (trained, None)
            request = ProductionPredictRequest(
                data=[{"feature1": 1.0, "feature2": 2.0}]
            )

            with pytest.raises(HTTPException) as exc:
                await production_predict("model_123", request, self._api_key())

        assert exc.value.status_code == 422
        assert "Invalid feature value" in exc.value.detail

    @pytest.mark.asyncio
    async def test_true_fault_returns_generic_500_without_leak(self):
        """An unexpected server fault → 500 that does NOT echo the internal message."""
        model = self._model()
        trained = MagicMock()
        secret = "connection string mongodb://secret@host leaked"
        trained.predict.side_effect = RuntimeError(secret)
        find, load = self._patch_load(model)
        with find, load as mock_load:
            mock_load.return_value = (trained, None)
            request = ProductionPredictRequest(
                data=[{"feature1": 1.0, "feature2": 2.0}]
            )

            with pytest.raises(HTTPException) as exc:
                await production_predict("model_123", request, self._api_key())

        assert exc.value.status_code == 500
        assert exc.value.detail == "Prediction failed"
        assert secret not in exc.value.detail  # no internal disclosure

    @pytest.mark.asyncio
    async def test_load_failure_returns_503_without_leak(self):
        """The model exists but its artifact won't load → 503 (broken deployment),
        never a 404 mis-signal and never leaking the S3 path."""
        model = self._model()
        find, load = self._patch_load(model)
        with find, load as mock_load:
            leaky = ValueError("failed to load s3://internal-bucket/models/secret.pkl")
            mock_load.side_effect = leaky
            request = ProductionPredictRequest(
                data=[{"feature1": 1.0, "feature2": 2.0}]
            )

            with pytest.raises(HTTPException) as exc:
                await production_predict("model_123", request, self._api_key())

        assert exc.value.status_code == 503
        assert "s3://" not in exc.value.detail  # no internal path leaked

    @pytest.mark.asyncio
    async def test_transform_valueerror_returns_422(self):
        """A ValueError from feature_engineer.transform (e.g. an unknown category
        at encode time) is also mapped to a sanitized 422, matching the internal
        twin's security guarantee — not only predict-level errors."""
        model = self._model()
        trained = MagicMock()
        engineer = MagicMock()
        raw = "Found unknown categories ['LEAK'] in column 0 during transform"
        engineer.transform = AsyncMock(side_effect=ValueError(raw))
        find, load = self._patch_load(model)
        with find, load as mock_load:
            mock_load.return_value = (trained, engineer)
            request = ProductionPredictRequest(
                data=[{"feature1": 1.0, "feature2": 2.0}]
            )

            with pytest.raises(HTTPException) as exc:
                await production_predict("model_123", request, self._api_key())

        assert exc.value.status_code == 422
        assert "Invalid feature value" in exc.value.detail
        assert raw not in exc.value.detail
        trained.predict.assert_not_called()  # failed before inference

    @pytest.mark.asyncio
    async def test_happy_path_returns_predictions(self):
        """A valid request runs the full inference path (predict/predict_proba
        via asyncio.to_thread) and returns a populated response."""
        model = self._model()
        trained = MagicMock()
        trained.predict.return_value = np.array([0, 1])
        trained.predict_proba.return_value = np.array([[0.8, 0.2], [0.3, 0.7]])
        find, load = self._patch_load(model)
        with find, load as mock_load:
            mock_load.return_value = (trained, None)
            request = ProductionPredictRequest(
                data=[
                    {"feature1": 1.0, "feature2": 2.0},
                    {"feature1": 3.0, "feature2": 4.0},
                ]
            )

            response = await production_predict("model_123", request, self._api_key())

        assert response.predictions == [0, 1]
        trained.predict.assert_called_once()
        trained.predict_proba.assert_called_once()
        # Enrichment pipeline ran end-to-end: confidence derived from proba.
        assert response.confidence == [0.8, 0.7]

    def test_request_caps_records_at_max(self):
        """The request schema rejects payloads over MAX_PREDICT_RECORDS (#264)."""
        from pydantic import ValidationError

        from app.api.routes.production import MAX_PREDICT_RECORDS

        oversized = [{"feature1": 1.0}] * (MAX_PREDICT_RECORDS + 1)
        with pytest.raises(ValidationError):
            ProductionPredictRequest(data=oversized)

        # Exactly at the cap is accepted.
        ProductionPredictRequest(data=[{"feature1": 1.0}] * MAX_PREDICT_RECORDS)


@pytest.mark.integration
class TestApiKeyUsageTracking:
    """verify_api_key records usage atomically and off the request path (#279).

    Pre-#279 it did read-modify-write `total_requests += 1; save()` in the hot
    path — a lost-update race, and a full-document save could revert a concurrent
    revoke. Now it fires an atomic `$inc`/`$set` off the request path.
    """

    @pytest.mark.asyncio
    async def test_usage_recorded_atomically(self, setup_database):
        from datetime import UTC, datetime

        from app.api.routes.production import flush_usage_tracking, verify_api_key

        # Naive UTC reference: motor/pymongo returns naive UTC datetimes on
        # read-back (tz_aware=False), so we compare freshness against a naive
        # baseline. (verify_api_key writes a tz-aware datetime.now(UTC), not the
        # deprecated naive datetime.utcnow() — the source change, not asserted
        # here because the driver strips tzinfo on the round-trip.)
        before = datetime.now(UTC).replace(tzinfo=None)

        raw = "sk_live_usage_tracking_key_000000"
        await _make_api_key(raw).insert()

        for _ in range(3):
            await verify_api_key(api_key=raw)
        await flush_usage_tracking()

        stored = await APIKey.find_one({"key_hash": hash_api_key(raw)})
        assert stored is not None
        assert stored.total_requests == 3  # every request counted, no lost update
        assert stored.last_used_at is not None
        # last_used_at was actually written by this run (fresh), not left default.
        recorded = stored.last_used_at
        if recorded.tzinfo is not None:
            recorded = recorded.astimezone(UTC).replace(tzinfo=None)
        assert recorded >= before

    @pytest.mark.asyncio
    async def test_usage_write_does_not_clobber_concurrent_revoke(self, setup_database):
        """A revoke that lands between verify and the usage write survives — the
        partial-field update never reverts is_active (the pre-#279 save() bug)."""
        from beanie.odm.operators.update.general import Set

        from app.api.routes.production import flush_usage_tracking, verify_api_key

        raw = "sk_live_revoke_race_key_000000000"
        await _make_api_key(raw).insert()

        # verify schedules the usage write (fire-and-forget, not yet flushed)...
        await verify_api_key(api_key=raw)
        # ...then the key is revoked atomically before the write lands.
        await APIKey.find_one({"key_hash": hash_api_key(raw)}).update(
            Set({APIKey.is_active: False})
        )
        await flush_usage_tracking()

        stored = await APIKey.find_one({"key_hash": hash_api_key(raw)})
        assert stored is not None
        assert stored.is_active is False  # revoke NOT clobbered by the usage write
        assert stored.total_requests == 1  # usage still counted

    @pytest.mark.asyncio
    async def test_usage_write_is_scheduled_off_the_request_path(self, setup_database):
        """verify_api_key returns without awaiting the DB write — it schedules a
        fire-and-forget task instead."""
        from app.api.routes import production

        raw = "sk_live_offpath_key_00000000000000"
        await _make_api_key(raw).insert()

        await production.flush_usage_tracking()  # start from a clean slate
        await production.verify_api_key(api_key=raw)

        # A task was scheduled rather than the write being awaited inline.
        assert len(production._usage_tracking_tasks) >= 1
        await production.flush_usage_tracking()
        assert len(production._usage_tracking_tasks) == 0
