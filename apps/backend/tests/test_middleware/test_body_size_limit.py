"""Tests for BodySizeLimitMiddleware (issue #270).

Rejects an oversized request body via Content-Length BEFORE the app/parser runs.
"""

import pytest

from app.middleware.body_size_limit import BodySizeLimitMiddleware


def _http_scope(content_length: int | None) -> dict:
    headers = []
    if content_length is not None:
        headers.append((b"content-length", str(content_length).encode()))
    return {"type": "http", "method": "POST", "headers": headers, "path": "/"}


async def _run(scope, max_bytes):
    """Drive the middleware; return (app_called, sent_messages)."""
    called = {"app": False}

    async def app(scope, receive, send):
        called["app"] = True

    sent: list[dict] = []

    async def send(message):
        sent.append(message)

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    mw = BodySizeLimitMiddleware(app, max_bytes=max_bytes)
    await mw(scope, receive, send)
    return called["app"], sent


@pytest.mark.asyncio
async def test_rejects_oversized_content_length_before_app():
    app_called, sent = await _run(_http_scope(5000), max_bytes=1024)
    assert app_called is False  # app/parser never runs
    assert sent[0]["type"] == "http.response.start"
    assert sent[0]["status"] == 413


@pytest.mark.asyncio
async def test_allows_under_cap():
    app_called, sent = await _run(_http_scope(500), max_bytes=1024)
    assert app_called is True
    assert sent == []  # middleware sent nothing; app handles the response


@pytest.mark.asyncio
async def test_allows_missing_content_length():
    # No Content-Length (e.g. chunked) → passes through to the app (and the
    # in-route read_upload_capped / nginx bound it).
    app_called, _ = await _run(_http_scope(None), max_bytes=1024)
    assert app_called is True


@pytest.mark.asyncio
async def test_non_http_scope_passes_through():
    app_called, _ = await _run({"type": "lifespan"}, max_bytes=1024)
    assert app_called is True
