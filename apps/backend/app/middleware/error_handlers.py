"""Safe error responses + request-id correlation (issue #269).

Two concerns, one small module:

1. ``RequestIDMiddleware`` stamps every request with a request id (echoing an
   inbound ``X-Request-ID`` when present) and returns it on the response header
   so a client-reported error can be traced to server logs.

2. Exception handlers that stop internal detail (``str(e)``, paths, S3 keys,
   library internals) leaking to clients on 5xx. The full detail is logged
   server-side with the request id; the client gets a generic
   ``{"detail": "Internal server error", "request_id": <id>}``. 4xx passes
   through unchanged so specific, safe validation text is preserved.

This centralizes the fix: every ``HTTPException(status_code>=500, ...)`` and
every unhandled exception across the app is sanitized here, instead of patching
~150 individual handlers.
"""

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"
GENERIC_5XX_DETAIL = "Internal server error"

# Status-appropriate generic messages. The client learns the *class* of failure
# (500 internal vs 503 unavailable) but never the underlying exception text —
# no ``str(e)`` at ANY 5xx can reach the client, whatever a route raises.
_GENERIC_5XX_BY_STATUS = {
    502: "Bad gateway",
    503: "Service temporarily unavailable",
    504: "Gateway timeout",
}


def _request_id(request: Request) -> str:
    """Request id set by the middleware; fall back to a fresh one defensively."""
    rid = getattr(request.state, "request_id", None)
    return rid if isinstance(rid, str) and rid else uuid.uuid4().hex


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a request id to ``request.state`` and the response header."""

    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        request.state.request_id = rid
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = rid
        return response


async def safe_http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Sanitize 5xx HTTPException bodies; pass 4xx through unchanged."""
    rid = _request_id(request)
    if exc.status_code >= 500:
        logger.error(
            "5xx response [request_id=%s] %s %s -> %s: %s",
            rid,
            request.method,
            request.url.path,
            exc.status_code,
            exc.detail,
        )
        # Never echo exc.detail on 5xx — a route may have built it from str(e).
        # Return a status-appropriate generic message + a request_id for tracing.
        detail = _GENERIC_5XX_BY_STATUS.get(exc.status_code, GENERIC_5XX_DETAIL)
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": detail, "request_id": rid},
            headers={REQUEST_ID_HEADER: rid},
        )
    # Safe client-error text is preserved (e.g. "Dataset not found").
    headers = dict(exc.headers or {})
    headers[REQUEST_ID_HEADER] = rid
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=headers,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all: log the full traceback, return a generic 500."""
    rid = _request_id(request)
    logger.exception(
        "Unhandled exception [request_id=%s] %s %s",
        rid,
        request.method,
        request.url.path,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": GENERIC_5XX_DETAIL, "request_id": rid},
        headers={REQUEST_ID_HEADER: rid},
    )


def register_error_handlers(app: FastAPI) -> None:
    """Wire the sanitizing handlers onto the app."""
    # Starlette types handlers as (Request, Exception); the narrower HTTPException
    # signature is intentional and safe here.
    app.add_exception_handler(StarletteHTTPException, safe_http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)
