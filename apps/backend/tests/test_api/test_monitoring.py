"""
Tests for monitoring API endpoints.

HTTP-level cases run against the real app (``async_authorized_client``, which
mounts the monitoring router) with real MongoDB documents and assert exact
statuses — replacing the pre-#267 suite that drove a stub app mounting only two
routers, so every ``/api/v1/monitoring/*`` request 404'd and ``in [200, 404]``
tested nothing. The response-formatting cases call the route functions directly
with a mocked monitoring service (fast, no DB) and stay as-is.
"""
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.models.api_key import APIKey
from app.models.ml_model import MLModel

TEST_USER = "test_user_123"  # matches async_authorized_client's overridden auth


def _make_model(model_id: str = "model_123", user_id: str = TEST_USER) -> MLModel:
    return MLModel(
        user_id=user_id,
        dataset_id="dataset_123",
        model_id=model_id,
        name="Test Model",
        problem_type="binary_classification",
        algorithm="Random Forest",
        target_column="target",
        feature_names=["feature1", "feature2"],
        cv_score=0.85,
        test_score=0.83,
        training_time=45.2,
        model_size=1048576,
        n_samples_train=1000,
        n_features=2,
        model_path="s3://bucket/models/model_123.pkl",
        version="1.0.0",
        is_active=True,
        last_used_at=datetime.utcnow(),
    )


@pytest.mark.integration
class TestMonitoringAPIIntegration:
    """Drive the real monitoring routes end to end with real MongoDB ownership."""

    @pytest.fixture(autouse=True)
    def _reset_prediction_log(self):
        """The monitoring metrics read a process-global in-memory prediction log
        that ``setup_database`` (Mongo-only) never touches — clear it so per-model
        counts are deterministic regardless of what serving tests ran before."""
        from app.services.prediction_monitoring import prediction_log

        prediction_log.logs.clear()
        yield
        prediction_log.logs.clear()

    @pytest.mark.asyncio
    async def test_get_model_metrics_for_owned_model(
        self, async_authorized_client, setup_database
    ):
        await _make_model().insert()
        resp = await async_authorized_client.get(
            "/api/v1/monitoring/models/model_123/metrics"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["model_id"] == "model_123"
        assert body["model_name"] == "Test Model"
        assert body["total_predictions"] == 0  # no predictions logged yet
        assert body["time_window_hours"] == 24

    @pytest.mark.asyncio
    async def test_get_model_metrics_custom_window(
        self, async_authorized_client, setup_database
    ):
        await _make_model().insert()
        resp = await async_authorized_client.get(
            "/api/v1/monitoring/models/model_123/metrics?hours=48"
        )
        assert resp.status_code == 200
        assert resp.json()["time_window_hours"] == 48

    @pytest.mark.asyncio
    async def test_get_model_metrics_unknown_model_404(
        self, async_authorized_client, setup_database
    ):
        resp = await async_authorized_client.get(
            "/api/v1/monitoring/models/nope/metrics"
        )
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Model not found"

    @pytest.mark.asyncio
    async def test_get_model_metrics_invalid_hours_422(
        self, async_authorized_client, setup_database
    ):
        """hours>168 is rejected by Query validation before the route body runs."""
        resp = await async_authorized_client.get(
            "/api/v1/monitoring/models/model_123/metrics?hours=200"
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_cross_tenant_metrics_404(
        self, async_authorized_client, setup_database
    ):
        """A model owned by another user is invisible (find_one is user-scoped)."""
        await _make_model(model_id="foreign", user_id="someone_else").insert()
        resp = await async_authorized_client.get(
            "/api/v1/monitoring/models/foreign/metrics"
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_prediction_distribution(
        self, async_authorized_client, setup_database
    ):
        await _make_model().insert()
        resp = await async_authorized_client.get(
            "/api/v1/monitoring/models/model_123/distribution"
        )
        assert resp.status_code == 200
        assert resp.json()["model_id"] == "model_123"

    @pytest.mark.asyncio
    async def test_get_usage_timeline(self, async_authorized_client, setup_database):
        await _make_model().insert()
        resp = await async_authorized_client.get(
            "/api/v1/monitoring/models/model_123/timeline?hours=24"
        )
        assert resp.status_code == 200
        assert resp.json()["model_id"] == "model_123"

    @pytest.mark.asyncio
    async def test_get_usage_timeline_invalid_bucket_422(
        self, async_authorized_client, setup_database
    ):
        resp = await async_authorized_client.get(
            "/api/v1/monitoring/models/model_123/timeline?bucket_minutes=5000"
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_get_deployment_health(
        self, async_authorized_client, setup_database
    ):
        await _make_model().insert()
        resp = await async_authorized_client.get(
            "/api/v1/monitoring/models/model_123/health"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["model_id"] == "model_123"
        assert body["status"] in {"healthy", "degraded", "unhealthy", "unknown"}

    @pytest.mark.asyncio
    async def test_check_drift(self, async_authorized_client, setup_database):
        await _make_model().insert()
        resp = await async_authorized_client.get(
            "/api/v1/monitoring/models/model_123/drift"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["model_id"] == "model_123"
        # #274: with no logged predictions the endpoint reports NOT assessed —
        # never a fabricated "no drift detected".
        assert body["assessed"] is False
        assert body["sample_size"] == 0
        assert "insufficient" in body["recommendation"].lower()

    @pytest.mark.asyncio
    async def test_get_usage_overview(self, async_authorized_client, setup_database):
        await _make_model(model_id="m1").insert()
        await _make_model(model_id="m2").insert()
        resp = await async_authorized_client.get("/api/v1/monitoring/overview")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_models"] == 2
        assert body["active_models"] == 2
        assert len(body["models"]) == 2

    @pytest.mark.asyncio
    async def test_get_api_key_usage(self, async_authorized_client, setup_database):
        await APIKey(
            key_id="mk1",
            key_hash=APIKey.hash_key("sk_live_monitoring_usage_key_0001"),
            name="usage-key",
            user_id=TEST_USER,
        ).insert()
        resp = await async_authorized_client.get("/api/v1/monitoring/api-keys/usage")
        assert resp.status_code == 200
        assert any(k["api_key_id"] == "mk1" for k in resp.json())

    @pytest.mark.asyncio
    async def test_get_prediction_logs(
        self, async_authorized_client, setup_database
    ):
        await _make_model().insert()
        resp = await async_authorized_client.get(
            "/api/v1/monitoring/models/model_123/logs"
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_prediction_logs_invalid_limit_422(
        self, async_authorized_client, setup_database
    ):
        resp = await async_authorized_client.get(
            "/api/v1/monitoring/models/model_123/logs?limit=2000"
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_monitoring_requires_auth(self, async_test_client, setup_database):
        """Without a bearer token the HTTPBearer dependency rejects with 401
        (missing credentials) — driven by the unauthenticated client (no auth
        override). starlette>=1.x returns 401, not 403, for missing bearer
        credentials (issue #270 upgrade)."""
        for endpoint in (
            "/api/v1/monitoring/overview",
            "/api/v1/monitoring/models/model_123/metrics",
            "/api/v1/monitoring/models/model_123/health",
            "/api/v1/monitoring/api-keys/usage",
        ):
            resp = await async_test_client.get(endpoint)
            assert resp.status_code == 401


class TestMonitoringRouteFormatting:
    """Response-model mapping, exercised by calling the route functions directly
    with a mocked monitoring service (no app/DB needed)."""

    @pytest.mark.asyncio
    @patch('app.api.routes.monitoring.MLModel')
    @patch('app.api.routes.monitoring.monitoring_service')
    async def test_timeline_response_format(self, mock_service, mock_model):
        """Timeline endpoint maps the service payload into the response model"""
        from app.api.routes.monitoring import get_usage_timeline

        mock_model.find_one = AsyncMock(return_value=Mock())
        mock_service.get_usage_timeline = AsyncMock(return_value={
            "bucket_minutes": 60,
            "time_window_hours": 24,
            "buckets": [
                {"timestamp": "2026-06-25T00:00:00", "requests": 5,
                 "errors": 1, "avg_latency_ms": 20.0},
                {"timestamp": "2026-06-25T01:00:00", "requests": 0,
                 "errors": 0, "avg_latency_ms": 0.0},
            ],
        })

        result = await get_usage_timeline(
            model_id="model_123", hours=24, bucket_minutes=60, current_user_id="user_123"
        )
        assert result.model_id == "model_123"
        assert result.bucket_minutes == 60
        assert len(result.buckets) == 2
        assert result.buckets[0].requests == 5
        assert result.buckets[0].errors == 1

    @pytest.mark.asyncio
    @patch('app.api.routes.monitoring.MLModel')
    @patch('app.api.routes.monitoring.monitoring_service')
    async def test_health_response_format(self, mock_service, mock_model):
        """Health endpoint maps the service payload into the response model"""
        from app.api.routes.monitoring import get_deployment_health

        mock_model.find_one = AsyncMock(return_value=Mock())
        mock_service.get_health = AsyncMock(return_value={
            "status": "degraded",
            "error_rate": 0.08,
            "avg_latency_ms": 120.0,
            "requests": 50,
            "last_request_at": datetime.utcnow().isoformat(),
            "alerts": [{"level": "warning", "type": "error_rate", "message": "high"}],
            "time_window_hours": 24,
        })

        result = await get_deployment_health(
            model_id="model_123", hours=24, current_user_id="user_123"
        )
        assert result.status == "degraded"
        assert result.alerts[0].type == "error_rate"
        assert result.requests == 50

    @pytest.mark.asyncio
    @patch('app.api.routes.monitoring.MLModel')
    @patch('app.api.routes.monitoring.APIKey')
    @patch('app.api.routes.monitoring.monitoring_service')
    async def test_usage_overview_calculation(self, mock_service, mock_api_key, mock_model):
        """Test usage overview calculation logic"""
        from app.api.routes.monitoring import get_usage_overview

        # Mock models
        mock_models = [
            Mock(
                model_id="model_1",
                name="Model 1",
                is_active=True,
                last_used_at=datetime.utcnow()
            ),
            Mock(
                model_id="model_2",
                name="Model 2",
                is_active=False,
                last_used_at=None
            )
        ]
        mock_model.find.return_value.to_list = AsyncMock(return_value=mock_models)

        # Mock API keys
        mock_keys = [
            Mock(is_active=True),
            Mock(is_active=True),
            Mock(is_active=False)
        ]
        mock_api_key.find.return_value.to_list = AsyncMock(return_value=mock_keys)

        # Mock metrics on the service instance
        mock_service.get_model_metrics = AsyncMock(side_effect=[
            {"total_predictions": 100, "avg_latency_ms": 50},
            {"total_predictions": 50, "avg_latency_ms": 75}
        ])

        # Test the calculation
        result = await get_usage_overview(current_user_id="user_123")

        assert result.total_models == 2
        assert result.active_models == 1
        assert result.total_predictions_24h == 150
        assert result.total_api_keys == 3
        assert result.active_api_keys == 2
        assert len(result.models) == 2

    @pytest.mark.asyncio
    @patch('app.api.routes.monitoring.MLModel')
    @patch('app.api.routes.monitoring.monitoring_service')
    async def test_model_metrics_response_format(self, mock_service, mock_model):
        """Test model metrics response format"""
        from app.api.routes.monitoring import get_model_metrics

        # Mock model
        mock_model_instance = Mock()
        mock_model_instance.name = "Test Model"
        mock_model_instance.last_used_at = datetime.utcnow()
        mock_model.find_one = AsyncMock(return_value=mock_model_instance)

        # Mock metrics on the service instance
        mock_service.get_model_metrics = AsyncMock(return_value={
            "total_predictions": 1000,
            "error_count": 20,
            "avg_latency_ms": 45.5,
            "latency_percentiles": {"p50": 40.0, "p90": 80.0, "p95": 95.0, "p99": 120.0},
            "predictions_per_hour": 41.7,
            "avg_confidence": 0.85,
            "error_rate": 0.02,
            "time_window_hours": 24
        })

        result = await get_model_metrics(
            model_id="model_123",
            hours=24,
            current_user_id="user_123"
        )

        assert result.model_id == "model_123"
        assert result.model_name == "Test Model"
        assert result.total_predictions == 1000
        assert result.error_count == 20
        assert result.avg_latency_ms == 45.5
        assert result.latency_percentiles["p95"] == 95.0
        assert result.predictions_per_hour == 41.7
        assert result.avg_confidence == 0.85
        assert result.error_rate == 0.02
        assert result.time_window_hours == 24
        assert result.last_prediction_at is not None
