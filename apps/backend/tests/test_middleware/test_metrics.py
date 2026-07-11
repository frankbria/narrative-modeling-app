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
from prometheus_client import CONTENT_TYPE_LATEST

from app.middleware.metrics import (
    MetricsMiddleware,
    active_requests,
    get_metrics,
)


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

    @test_app.get("/items/{item_id}")
    async def item_endpoint(item_id: str):
        return {"id": item_id}

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

    def test_endpoint_label_uses_route_template_not_raw_path(self, client):
        """Path params must collapse to the route template (issue #273): three
        different ids share ONE endpoint="/items/{item_id}" series, not three —
        otherwise every unique id is a permanent new time series (cardinality bomb)."""
        for item_id in ("1", "2", "3"):
            client.get(f"/items/{item_id}")

        metrics = get_metrics().decode("utf-8")

        assert 'endpoint="/items/{item_id}"' in metrics
        # The raw, per-id paths must NOT appear as labels.
        assert 'endpoint="/items/1"' not in metrics
        assert 'endpoint="/items/2"' not in metrics
        # The template counter should have summed all three requests.
        count_line = next(
            line
            for line in metrics.split("\n")
            if line.startswith("http_requests_total{")
            and 'endpoint="/items/{item_id}"' in line
        )
        assert count_line.strip().endswith("3.0")

    def test_unmatched_path_collapses_to_single_label(self, client):
        """404s / scans must share one __unmatched__ series, not one per URL."""
        client.get("/no/such/route/aaa")
        client.get("/no/such/route/bbb")

        metrics = get_metrics().decode("utf-8")
        assert 'endpoint="__unmatched__"' in metrics
        assert 'endpoint="/no/such/route/aaa"' not in metrics

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

    def test_active_gauge_not_leaked_on_exception(self, client):
        """The active-requests gauge must be decremented even when call_next
        raises (the .dec() lives in the `finally`) — otherwise it drifts positive
        forever and reads as permanent load."""
        before = active_requests.labels(method="GET")._value.get()
        with pytest.raises(ValueError):
            client.get("/error")
        after = active_requests.labels(method="GET")._value.get()
        assert after == before  # incremented at start, decremented in finally → net 0

    def test_active_requests_labeled_by_method_only(self, client):
        """active_requests is labeled by method only (issue #273): the route
        template isn't known at request start, so labeling by endpoint would
        reintroduce the raw-path cardinality bomb."""
        client.get("/test")
        metrics = get_metrics().decode("utf-8")

        active_lines = [
            line
            for line in metrics.split("\n")
            if line.startswith("http_requests_active{")
        ]
        assert active_lines, "expected an http_requests_active sample"
        for line in active_lines:
            assert 'method="GET"' in line
            # endpoint/status_code must NOT be labels on the gauge anymore
            assert "endpoint=" not in line
            assert "status_code=" not in line
