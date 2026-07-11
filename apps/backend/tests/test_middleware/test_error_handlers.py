"""Tests for safe error responses + request-id correlation (issue #269).

Contract:
- 5xx (explicit HTTPException OR unhandled Exception) -> generic
  ``{"detail": "Internal server error", "request_id": <id>}`` with an
  ``X-Request-ID`` header. Raw exception / detail text is NEVER in the body.
- 4xx passes through unchanged (safe validation text is preserved).
- Every response carries ``X-Request-ID``; an inbound ``X-Request-ID`` is echoed.
"""

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from app.middleware.error_handlers import (
    GENERIC_5XX_DETAIL,
    RequestIDMiddleware,
    register_error_handlers,
)

pytestmark = [pytest.mark.unit]

LEAK = "s3://secret-bucket/models/u1/artifact.pkl KeyError: 'age'"


def build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)
    register_error_handlers(app)

    @app.get("/leaky-500")
    async def leaky_500():
        raise HTTPException(status_code=500, detail=f"Error processing dataset: {LEAK}")

    @app.get("/unhandled")
    async def unhandled():
        raise RuntimeError(LEAK)

    @app.get("/service-unavailable")
    async def service_unavailable():
        raise HTTPException(status_code=503, detail="Cache service unavailable")

    @app.get("/not-implemented")
    async def not_implemented():
        raise HTTPException(status_code=501, detail="Use /some/other/endpoint instead")

    @app.get("/bad-request")
    async def bad_request():
        raise HTTPException(status_code=400, detail="Column 'age' must be numeric")

    @app.get("/not-found")
    async def not_found():
        raise HTTPException(status_code=404, detail="Dataset not found")

    @app.get("/ok")
    async def ok():
        return {"ok": True}

    return app


async def _client(app: FastAPI) -> AsyncClient:
    # raise_app_exceptions=False mirrors a real ASGI server: the registered
    # Exception handler's 500 response is returned to the client; the re-raise
    # ServerErrorMiddleware does for server-side logging is not propagated here.
    return AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    )


@pytest.mark.asyncio
async def test_explicit_500_is_sanitized():
    async with await _client(build_app()) as c:
        r = await c.get("/leaky-500")
    assert r.status_code == 500
    body = r.json()
    assert body["detail"] == GENERIC_5XX_DETAIL
    assert body["request_id"]
    assert LEAK not in r.text
    assert "Error processing dataset" not in r.text
    assert r.headers["X-Request-ID"] == body["request_id"]


@pytest.mark.asyncio
async def test_unhandled_exception_is_sanitized():
    async with await _client(build_app()) as c:
        r = await c.get("/unhandled")
    assert r.status_code == 500
    body = r.json()
    assert body["detail"] == GENERIC_5XX_DETAIL
    assert body["request_id"]
    assert LEAK not in r.text
    assert r.headers["X-Request-ID"] == body["request_id"]


@pytest.mark.asyncio
async def test_5xx_detail_never_echoed_status_appropriate_generic():
    """Non-500 5xx get a status-appropriate generic message (never exc.detail),
    so no str(e) can leak whatever a route raises (issue #269)."""
    async with await _client(build_app()) as c:
        r = await c.get("/service-unavailable")
    assert r.status_code == 503
    body = r.json()
    assert body["detail"] == "Service temporarily unavailable"
    assert body["request_id"]
    assert r.headers["X-Request-ID"] == body["request_id"]


@pytest.mark.asyncio
async def test_501_reports_not_implemented_not_internal_error():
    """501 must read as an intentional "Not implemented", not the misleading
    "Internal server error" fallback — while still not echoing exc.detail (#274)."""
    async with await _client(build_app()) as c:
        r = await c.get("/not-implemented")
    assert r.status_code == 501
    body = r.json()
    assert body["detail"] == "Not implemented"
    assert "other/endpoint" not in body["detail"]  # exc.detail still not echoed
    assert body["request_id"]


@pytest.mark.asyncio
async def test_4xx_detail_passes_through():
    async with await _client(build_app()) as c:
        r400 = await c.get("/bad-request")
        r404 = await c.get("/not-found")
    assert r400.status_code == 400
    assert r400.json()["detail"] == "Column 'age' must be numeric"
    assert r400.headers["X-Request-ID"]
    assert r404.status_code == 404
    assert r404.json()["detail"] == "Dataset not found"


@pytest.mark.asyncio
async def test_success_carries_request_id_header():
    async with await _client(build_app()) as c:
        r = await c.get("/ok")
    assert r.status_code == 200
    assert r.headers["X-Request-ID"]


@pytest.mark.asyncio
async def test_inbound_request_id_is_echoed():
    async with await _client(build_app()) as c:
        r = await c.get("/leaky-500", headers={"X-Request-ID": "trace-abc-123"})
    assert r.headers["X-Request-ID"] == "trace-abc-123"
    assert r.json()["request_id"] == "trace-abc-123"


@pytest.mark.asyncio
async def test_unsafe_inbound_request_id_is_replaced():
    """An inbound id with unsafe chars / excess length is not reflected."""
    async with await _client(build_app()) as c:
        r = await c.get("/ok", headers={"X-Request-ID": "bad id with spaces & <html>"})
    echoed = r.headers["X-Request-ID"]
    assert echoed != "bad id with spaces & <html>"
    assert echoed.isalnum()  # freshly minted uuid4().hex


def test_real_app_registers_handlers():
    """The production app wires the handlers + middleware."""
    from starlette.exceptions import HTTPException as StarletteHTTPException

    from app.main import app

    assert Exception in app.exception_handlers
    assert StarletteHTTPException in app.exception_handlers
    assert any(m.cls is RequestIDMiddleware for m in app.user_middleware)
