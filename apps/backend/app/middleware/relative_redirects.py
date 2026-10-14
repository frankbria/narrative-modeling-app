"""A redirect to this app's own host carries a path, not a scheme and host (#942).

Starlette builds the redirect for a path missing its trailing slash from the request's
scheme, and behind the TLS-terminating nginx that scheme is http: the backend does not
trust `X-Forwarded-Proto` from the address nginx connects from, on purpose, because
trusting forwarded headers would also move the client address the rate limiter reads
(#455, #915). So `https://host/api/v1/ml` was sent to `http://host/api/v1/ml/`, which
nginx redirected back to https, and a POST arrived as a GET after that 301.

A `Location` that is an absolute path (RFC 9110 §10.2.2) keeps whatever scheme and host
the client used. Redirects to other hosts are left as they are.
"""

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

_REDIRECTS = {301, 302, 303, 307, 308}


def _own_origin(scope: Scope) -> str | None:
    """`scheme://host` as the app sees the request, or None without a Host header."""
    host = dict(scope.get("headers", [])).get(b"host")
    return f"{scope.get('scheme', 'http')}://{host.decode('latin-1')}" if host else None


class RelativeRedirectMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        origin = _own_origin(scope) if scope["type"] == "http" else None
        if origin is None:
            await self.app(scope, receive, send)
            return

        async def send_relative(message: Message) -> None:
            if message["type"] == "http.response.start" and message["status"] in _REDIRECTS:
                headers = MutableHeaders(scope=message)
                location = headers.get("location", "")
                if location.startswith(origin + "/"):
                    headers["location"] = location[len(origin):]
            await send(message)

        await self.app(scope, receive, send_relative)
