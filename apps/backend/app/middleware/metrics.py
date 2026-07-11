# apps/backend/app/middleware/metrics.py
"""
Prometheus metrics middleware for FastAPI.

Tracks:
- Request latency histogram (buckets: 0.1, 0.5, 1, 2, 5, 10s)
- Request count by endpoint, method, and status code
- Active request gauge

Usage:
    from app.middleware.metrics import MetricsMiddleware, metrics_registry

    app.add_middleware(MetricsMiddleware)

    @app.get("/metrics")
    async def metrics():
        return Response(
            content=generate_latest(metrics_registry),
            media_type=CONTENT_TYPE_LATEST
        )
"""

import time
from collections.abc import Callable

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

# Create a custom registry for application metrics
metrics_registry = CollectorRegistry()

# Request latency histogram with specified buckets
request_latency = Histogram(
    name="http_request_duration_seconds",
    documentation="HTTP request latency in seconds",
    labelnames=["method", "endpoint", "status_code"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0),
    registry=metrics_registry,
)

# Request counter by endpoint, method, and status
request_count = Counter(
    name="http_requests_total",
    documentation="Total HTTP requests",
    labelnames=["method", "endpoint", "status_code"],
    registry=metrics_registry,
)

# Active requests gauge. Labeled by method only: the matched route template is
# not known until *after* routing (inside call_next), but the gauge must inc at
# request start — so labeling it by endpoint would either be wrong or reintroduce
# the raw-path cardinality bomb. Method-only is bounded and still useful.
active_requests = Gauge(
    name="http_requests_active",
    documentation="Number of active HTTP requests",
    labelnames=["method"],
    registry=metrics_registry,
)

# Label for requests that matched no route (404s, scans). Using the raw path here
# would let an attacker mint unbounded time series, so collapse them to one.
UNMATCHED_ENDPOINT = "__unmatched__"


def _endpoint_label(request: Request) -> str:
    """The matched route *template* (e.g. ``/ml/{model_id}/status``), not the raw
    URL path — so ``/ml/1/status`` and ``/ml/2/status`` share one time series
    instead of one per id (cardinality bomb, issue #273). Populated by the router
    during ``call_next``; ``None`` when no route matched."""
    route = request.scope.get("route")
    return getattr(route, "path", None) or UNMATCHED_ENDPOINT


class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware to collect Prometheus metrics for HTTP requests.

    Tracks request latency, count, and active requests for all endpoints
    except the /metrics endpoint itself to avoid metric pollution.
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip metrics collection for the metrics endpoint itself
        if request.url.path == "/metrics":
            return await call_next(request)

        method = request.method

        # Track active requests (method-only label; see gauge comment above)
        active_requests.labels(method=method).inc()

        # Start timing
        start_time = time.time()

        try:
            # Process the request
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            # Track errors as 500
            status_code = 500
            raise
        finally:
            # Calculate latency
            latency = time.time() - start_time

            # Resolve the endpoint label AFTER routing so it's the route template,
            # not the high-cardinality raw path.
            endpoint = _endpoint_label(request)

            # Record metrics
            request_latency.labels(
                method=method, endpoint=endpoint, status_code=status_code
            ).observe(latency)

            request_count.labels(
                method=method, endpoint=endpoint, status_code=status_code
            ).inc()

            # Decrement active requests
            active_requests.labels(method=method).dec()

        return response


def get_metrics() -> bytes:
    """
    Generate Prometheus metrics in the exposition format.

    Returns:
        bytes: Metrics in Prometheus text format
    """
    return generate_latest(metrics_registry)
