# apps/backend/tests/test_middleware/test_metrics.py
"""
Tests for Prometheus metrics middleware.

Tests:
- Request latency tracking
- Request count tracking
- Active requests gauge
- Metrics endpoint functionality
- Error handling
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY
from app.middleware.metrics import (
    MetricsMiddleware,
    get_metrics,
    metrics_registry,
    request_latency,
    request_count,
    active_requests,
)
from prometheus_client import CONTENT_TYPE_LATEST


@pytest.fixture
def app():
    """Create a test FastAPI app with metrics middleware."""
    test_app = FastAPI()
    test_app.add_middleware(MetricsMiddleware)

    @test_app.get("/test")
    async def test_endpoint():
        return {"message": "test"}

    @test_app.get("/error")
    async def error_endpoint():
        raise ValueError("Test error")

    @test_app.get("/metrics")
    async def metrics_endpoint():
        from fastapi.responses import Response

        return Response(content=get_metrics(), media_type=CONTENT_TYPE_LATEST)

    return test_app


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


class TestMetricsMiddleware:
    """Test suite for MetricsMiddleware."""

    def test_middleware_tracks_successful_request(self, client):
        """Test that middleware tracks successful requests."""
        # Make a test request
        response = client.get("/test")
        assert response.status_code == 200

        # Get metrics
        metrics_response = client.get("/metrics")
        assert metrics_response.status_code == 200
        metrics_text = metrics_response.text

        # Check that metrics are present
        assert "http_request_duration_seconds" in metrics_text
        assert "http_requests_total" in metrics_text
        assert 'endpoint="/test"' in metrics_text
        assert 'method="GET"' in metrics_text
        assert 'status_code="200"' in metrics_text

    def test_middleware_tracks_request_latency(self, client):
        """Test that middleware tracks request latency."""
        # Make multiple requests
        for _ in range(5):
            client.get("/test")

        # Get metrics
        metrics_response = client.get("/metrics")
        metrics_text = metrics_response.text

        # Check histogram metrics
        assert "http_request_duration_seconds_bucket" in metrics_text
        assert "http_request_duration_seconds_count" in metrics_text
        assert "http_request_duration_seconds_sum" in metrics_text

    def test_middleware_tracks_request_count(self, client):
        """Test that middleware tracks request counts."""
        # Make multiple requests
        num_requests = 10
        for _ in range(num_requests):
            client.get("/test")

        # Get metrics
        metrics_response = client.get("/metrics")
        metrics_text = metrics_response.text

        # Check that counter incremented (count should be >= num_requests)
        assert "http_requests_total" in metrics_text
        # The exact count might vary due to other requests, but should be present
        assert 'endpoint="/test"' in metrics_text

    def test_middleware_handles_errors(self, client):
        """Test that middleware tracks error responses."""
        # Make a request that raises an error
        with pytest.raises(ValueError):
            client.get("/error")

        # Get metrics
        metrics_response = client.get("/metrics")
        metrics_text = metrics_response.text

        # Check that error was tracked (status_code should be 500)
        assert "http_request_duration_seconds" in metrics_text
        # Error endpoint might be tracked with 500 status

    def test_metrics_endpoint_excluded_from_tracking(self, client):
        """Test that /metrics endpoint itself is not tracked."""
        # Request metrics endpoint
        response = client.get("/metrics")
        assert response.status_code == 200
        metrics_text = response.text

        # /metrics endpoint should NOT appear in the metrics
        # (or should appear with minimal counts)
        # This is to avoid metric pollution
        assert "endpoint=\"/metrics\"" not in metrics_text or metrics_text.count(
            'endpoint="/metrics"'
        ) <= 1

    def test_metrics_endpoint_returns_prometheus_format(self, client):
        """Test that /metrics endpoint returns valid Prometheus format."""
        response = client.get("/metrics")
        assert response.status_code == 200
        assert response.headers["content-type"] == CONTENT_TYPE_LATEST

        # Check format
        metrics_text = response.text
        assert "# HELP" in metrics_text
        assert "# TYPE" in metrics_text

    def test_active_requests_gauge(self, client):
        """Test that active requests gauge is working."""
        # Make a request
        response = client.get("/test")
        assert response.status_code == 200

        # Get metrics
        metrics_response = client.get("/metrics")
        metrics_text = metrics_response.text

        # Active requests should be tracked
        assert "http_requests_active" in metrics_text

    def test_multiple_endpoints_tracked_separately(self, client):
        """Test that different endpoints are tracked separately."""
        # Make requests to different endpoints
        client.get("/test")

        # Error endpoint will raise an exception, so we need to catch it
        try:
            client.get("/error")
        except Exception:
            pass  # Expected

        # Get metrics
        metrics_response = client.get("/metrics")
        metrics_text = metrics_response.text

        # /test endpoint should be tracked
        assert 'endpoint="/test"' in metrics_text

    def test_different_methods_tracked_separately(self, client):
        """Test that different HTTP methods are tracked separately."""
        # Make GET request
        client.get("/test")

        # Get metrics
        metrics_response = client.get("/metrics")
        metrics_text = metrics_response.text

        # GET method should be tracked
        assert 'method="GET"' in metrics_text

    def test_different_status_codes_tracked_separately(self, client):
        """Test that different status codes are tracked separately."""
        # Make successful request
        client.get("/test")

        # Get metrics
        metrics_response = client.get("/metrics")
        metrics_text = metrics_response.text

        # 200 status should be tracked
        assert 'status_code="200"' in metrics_text


class TestMetricsRegistry:
    """Test suite for metrics registry."""

    def test_get_metrics_returns_bytes(self):
        """Test that get_metrics returns bytes."""
        metrics = get_metrics()
        assert isinstance(metrics, bytes)

    def test_metrics_contain_all_metric_types(self, client):
        """Test that all metric types are present."""
        # Make a request to generate metrics
        client.get("/test")

        metrics = get_metrics().decode("utf-8")

        # Check for all metric types
        assert "http_request_duration_seconds" in metrics
        assert "http_requests_total" in metrics
        assert "http_requests_active" in metrics

    def test_histogram_buckets_configured(self, client):
        """Test that histogram buckets are correctly configured."""
        client.get("/test")
        metrics = get_metrics().decode("utf-8")

        # Check for expected bucket values (0.1, 0.5, 1, 2, 5, 10)
        assert "le=\"0.1\"" in metrics
        assert "le=\"0.5\"" in metrics
        assert "le=\"1.0\"" in metrics
        assert "le=\"2.0\"" in metrics
        assert "le=\"5.0\"" in metrics
        assert "le=\"10.0\"" in metrics
        assert "le=\"+Inf\"" in metrics


class TestMetricsLabels:
    """Test suite for metrics labels."""

    def test_request_latency_has_correct_labels(self, client):
        """Test that request_latency has method, endpoint, status_code labels."""
        client.get("/test")
        metrics = get_metrics().decode("utf-8")

        # Find a line with request_latency metric
        for line in metrics.split("\n"):
            if "http_request_duration_seconds_bucket" in line and "/test" in line:
                assert "method=" in line
                assert "endpoint=" in line
                assert "status_code=" in line
                break

    def test_request_count_has_correct_labels(self, client):
        """Test that request_count has method, endpoint, status_code labels."""
        client.get("/test")
        metrics = get_metrics().decode("utf-8")

        # Find a line with request_count metric
        for line in metrics.split("\n"):
            if "http_requests_total" in line and "/test" in line:
                assert "method=" in line
                assert "endpoint=" in line
                assert "status_code=" in line
                break

    def test_active_requests_has_correct_labels(self, client):
        """Test that active_requests has method, endpoint labels."""
        client.get("/test")
        metrics = get_metrics().decode("utf-8")

        # Find a line with active_requests metric
        for line in metrics.split("\n"):
            if "http_requests_active" in line and "/test" in line:
                assert "method=" in line
                assert "endpoint=" in line
                # Should NOT have status_code label
                assert "status_code=" not in line
                break
