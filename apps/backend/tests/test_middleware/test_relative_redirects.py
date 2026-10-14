"""#942: the trailing-slash redirect keeps the client's https behind the TLS proxy.

Starlette built it from the request's scheme, http behind nginx, so a client that asked
for https://host/api/v1/ml was sent to http://host/api/v1/ml/. Through the whole app.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

pytestmark = pytest.mark.asyncio


async def _get(path: str, **headers: str):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://staging.example") as client:
        return await client.get(path, headers=headers)


async def test_a_slashless_path_redirects_to_a_path_not_to_http():
    response = await _get("/api/v1/ml", **{"X-Forwarded-Proto": "https"})

    assert response.status_code == 307
    assert response.headers["location"] == "/api/v1/ml/"
    assert "http://" not in response.headers["location"]


async def test_the_query_string_is_kept():
    response = await _get("/api/v1/ml?dataset_id=d1")

    assert response.headers["location"] == "/api/v1/ml/?dataset_id=d1"


async def test_a_redirect_to_another_host_is_left_alone():
    from app.middleware.relative_redirects import RelativeRedirectMiddleware

    async def elsewhere(scope, receive, send):
        await send({"type": "http.response.start", "status": 302,
                    "headers": [(b"location", b"https://stripe.example/checkout")]})
        await send({"type": "http.response.body", "body": b""})

    async with AsyncClient(
        transport=ASGITransport(app=RelativeRedirectMiddleware(elsewhere)), base_url="http://staging.example"
    ) as client:
        response = await client.get("/go")

    assert response.headers["location"] == "https://stripe.example/checkout"
