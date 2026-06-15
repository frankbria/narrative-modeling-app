"""
API rate-limiting middleware (issue #151).

Enforces request budgets on every ``/api/v1`` route. Identity is resolved per
request, cheapest first:

1. ``X-API-Key`` header **on a production route** (where the key is the real auth
   mechanism) → look up the :class:`APIKey` and use its ``rate_limit`` field over
   ``RATE_LIMIT_APIKEY_WINDOW_SECONDS`` (per-key override). Elsewhere the header is
   ignored so it cannot be used to escape the per-user/IP budget.
2. Session ``Authorization: Bearer`` token → the authenticated user id, with the
   default per-user budget.
3. Otherwise the client IP, with the same default budget (guards unauthenticated
   floods, e.g. against auth endpoints).

Over-budget requests get a ``429`` with a ``Retry-After`` header and never reach
the route handler. Allowed requests carry ``X-RateLimit-*`` headers.

Registered so that the CORS middleware stays *outermost* — a ``429`` returned here
still passes back through CORS and gains its headers, so browsers can read it.
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import settings
from app.services.rate_limit import RateLimitResult, RateLimitStore

logger = logging.getLogger(__name__)

_API_V1_PREFIX = "/api/v1"
# Routes where ``X-API-Key`` is the actual authentication mechanism (the production
# model-serving surface — see app/api/routes/production.py, mounted under
# /api/v1/production). The per-key bucket is honoured ONLY here; on every other
# /api/v1 route the header is meaningless, so it must not let a caller swap into a
# more favourable key budget and escape their per-user/IP limit.
_APIKEY_AUTH_PREFIX = "/api/v1/production"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fixed-window rate limiting for all ``/api/v1`` routes."""

    def __init__(
        self,
        app,
        store: Optional[RateLimitStore] = None,
        *,
        enabled: Optional[bool] = None,
        default_requests: Optional[int] = None,
        default_window_seconds: Optional[int] = None,
        apikey_window_seconds: Optional[int] = None,
        trust_forwarded_for: Optional[bool] = None,
        apikey_auth_prefix: str = _APIKEY_AUTH_PREFIX,
    ) -> None:
        super().__init__(app)
        # ``store`` may be injected (tests) or resolved from ``app.state`` per request
        # (set during lifespan). Falling back to app.state lets main.py build the
        # async Redis store after the event loop is running.
        self._store = store
        self._enabled = settings.RATE_LIMIT_ENABLED if enabled is None else enabled
        self._default_requests = (
            settings.RATE_LIMIT_DEFAULT_REQUESTS
            if default_requests is None
            else default_requests
        )
        self._default_window = (
            settings.RATE_LIMIT_DEFAULT_WINDOW_SECONDS
            if default_window_seconds is None
            else default_window_seconds
        )
        self._apikey_window = (
            settings.RATE_LIMIT_APIKEY_WINDOW_SECONDS
            if apikey_window_seconds is None
            else apikey_window_seconds
        )
        self._trust_forwarded_for = (
            settings.RATE_LIMIT_TRUST_FORWARDED_FOR
            if trust_forwarded_for is None
            else trust_forwarded_for
        )
        self._apikey_auth_prefix = apikey_auth_prefix

    def _resolve_store(self, request: Request) -> Optional[RateLimitStore]:
        if self._store is not None:
            return self._store
        return getattr(request.app.state, "rate_limit_store", None)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if not self._should_limit(request):
            return await call_next(request)

        store = self._resolve_store(request)
        if store is None:
            # No backend wired up — fail open (e.g. lifespan not run).
            return await call_next(request)

        bucket_key, limit, window = await self._resolve_identity(request)
        result = await store.hit(bucket_key, limit, window)

        if not result.allowed:
            return self._too_many_requests(result)

        response = await call_next(request)
        if result.limited:
            self._apply_headers(response, result)
        return response

    def _should_limit(self, request: Request) -> bool:
        if not self._enabled:
            return False
        # Preflight requests must pass untouched for CORS to work.
        if request.method == "OPTIONS":
            return False
        return request.url.path.startswith(_API_V1_PREFIX)

    async def _resolve_identity(self, request: Request) -> Tuple[str, int, int]:
        """Return ``(bucket_key, limit, window_seconds)`` for this request."""
        # 1. API key (per-key override) — only on the routes that authenticate with
        # X-API-Key, so the header can't be used to opt into a key budget elsewhere.
        if request.url.path.startswith(self._apikey_auth_prefix):
            api_key_header = request.headers.get("x-api-key")
            if api_key_header:
                identity = await self._identity_from_api_key(api_key_header)
                if identity is not None:
                    return identity

        # 2. Session user.
        user_id = await self._user_id_from_request(request)
        if user_id:
            return (f"user:{user_id}", self._default_requests, self._default_window)

        # 3. Client IP fallback.
        return (
            f"ip:{self._client_ip(request)}",
            self._default_requests,
            self._default_window,
        )

    def _client_ip(self, request: Request) -> str:
        # Only honour X-Forwarded-For when explicitly trusted (app behind a proxy
        # that overwrites it); otherwise it is attacker-controlled and lets an
        # anonymous caller forge a fresh bucket per request. See settings.
        if self._trust_forwarded_for:
            forwarded = request.headers.get("x-forwarded-for")
            if forwarded:
                return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def _identity_from_api_key(
        self, raw_key: str
    ) -> Optional[Tuple[str, int, int]]:
        """Resolve a bucket from a raw API key, or None if it can't be looked up."""
        try:
            from app.models.api_key import APIKey

            key_hash = APIKey.hash_key(raw_key)
            api_key = await APIKey.find_one({"key_hash": key_hash})
            if api_key is None or not api_key.is_valid():
                return None
            return (f"apikey:{api_key.key_id}", api_key.rate_limit, self._apikey_window)
        except Exception as exc:
            # DB not initialised, lookup failure, etc. — fall through to user/IP.
            logger.debug(
                "API-key rate-limit lookup failed (%s); using default budget.", exc
            )
            return None

    async def _user_id_from_request(self, request: Request) -> Optional[str]:
        """Best-effort authenticated user id; reuses the existing optional auth path."""
        auth_header = request.headers.get("authorization")
        if not auth_header:
            return None
        try:
            from app.auth.nextauth_auth import get_current_user_id_optional

            return await get_current_user_id_optional(authorization=auth_header)
        except Exception:  # pragma: no cover - optional auth never raises to caller
            return None

    @staticmethod
    def _apply_headers(response: Response, result: RateLimitResult) -> None:
        response.headers["X-RateLimit-Limit"] = str(result.limit)
        response.headers["X-RateLimit-Remaining"] = str(result.remaining)
        response.headers["X-RateLimit-Reset"] = str(result.reset_seconds)

    @staticmethod
    def _too_many_requests(result: RateLimitResult) -> JSONResponse:
        retry_after = result.retry_after
        return JSONResponse(
            status_code=429,
            content={
                "error": "RATE_LIMIT_EXCEEDED",
                "message": (
                    f"Rate limit exceeded. Limit is {result.limit} requests per window. "
                    f"Retry after {retry_after} seconds."
                ),
                "details": {"retry_after_seconds": retry_after},
            },
            headers={
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(result.limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(result.reset_seconds),
            },
        )
