"""Bearer-token auth for the MCP SSE endpoint.

Defense-in-depth on top of the localhost bind: the only caller is the backend,
which sends `Authorization: Bearer <MCP_API_KEY>`. A pure-ASGI middleware is used
(not BaseHTTPMiddleware) so it does not buffer/break the SSE stream.
"""

import hmac

from starlette.responses import PlainTextResponse

_BEARER_PREFIX = "Bearer "


def require_api_key(api_key: str | None) -> str:
    """Return the configured API key, or raise if it is missing (fail closed).

    Starting the SSE tool surface without a token would recreate the original
    unauthenticated exposure, so we refuse rather than degrade.
    """
    if not api_key:
        raise RuntimeError(
            "MCP_API_KEY is not set; refusing to start unauthenticated."
        )
    return api_key


def verify_bearer_token(auth_header: str, expected_token: str | None) -> bool:
    """Constant-time check of an `Authorization: Bearer <token>` header.

    Fails closed: an unset/empty expected token rejects every request.
    """
    if not expected_token:
        return False
    if not auth_header.startswith(_BEARER_PREFIX):
        return False
    provided = auth_header[len(_BEARER_PREFIX):]
    return hmac.compare_digest(provided, expected_token)


class BearerAuthMiddleware:
    """Reject any HTTP request without a valid bearer token (401)."""

    def __init__(self, app, expected_token: str | None):
        self.app = app
        self.expected_token = expected_token

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        auth_header = headers.get(b"authorization", b"").decode("latin-1")
        if not verify_bearer_token(auth_header, self.expected_token):
            response = PlainTextResponse("Unauthorized", status_code=401)
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
