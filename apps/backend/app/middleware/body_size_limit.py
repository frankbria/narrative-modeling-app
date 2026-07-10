"""Reject oversized request bodies before routing / multipart parsing (issue #270).

``read_upload_capped`` bounds the in-route read, but by the time an endpoint runs
Starlette's multipart parser has already consumed and spooled the whole body (to
disk past 1 MB). This ASGI middleware rejects an oversized body at the app edge
via its declared ``Content-Length`` — which every standard upload client (browser
form posts, httpx/requests multipart) sends — so the parser never sees it.

Defense-in-depth: nginx ``client_max_body_size`` is the production edge (and also
covers chunked/Content-Length-absent bodies); this middleware is the app-level
guard for direct/dev access; ``read_upload_capped`` remains the in-route memory
bound. A chunked body with no Content-Length still reaches the parser here and is
bounded by nginx + the in-route cap (documented beta limitation).
"""

import json
import os

from starlette.types import ASGIApp, Receive, Scope, Send

# Same source of truth as read_upload_capped's cap (issue #270).
MAX_BODY_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(100 * 1024 * 1024)))


class BodySizeLimitMiddleware:
    """Send 413 before the app runs when Content-Length exceeds the cap."""

    def __init__(self, app: ASGIApp, max_bytes: int | None = None) -> None:
        self.app = app
        self._max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        max_bytes = self._max_bytes if self._max_bytes is not None else MAX_BODY_BYTES

        for name, value in scope.get("headers", []):
            if name == b"content-length":
                try:
                    declared = int(value)
                except ValueError:
                    break
                if declared > max_bytes:
                    await self._reject(send, max_bytes)
                    return
                break

        await self.app(scope, receive, send)

    @staticmethod
    async def _reject(send: Send, max_bytes: int) -> None:
        body = json.dumps(
            {
                "detail": f"Request body too large. Maximum size is "
                f"{max_bytes // (1024 * 1024)} MB."
            }
        ).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
