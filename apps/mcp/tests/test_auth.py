import pytest
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from mcp.auth import BearerAuthMiddleware, require_api_key, verify_bearer_token


def test_require_api_key_returns_configured_key():
    assert require_api_key("secret") == "secret"


def test_require_api_key_fails_closed_when_missing():
    """No token must abort startup, not silently run unauthenticated."""
    with pytest.raises(RuntimeError):
        require_api_key(None)
    with pytest.raises(RuntimeError):
        require_api_key("")


def test_verify_rejects_when_no_expected_token():
    """Fail closed: an unconfigured token rejects everything."""
    assert verify_bearer_token("Bearer anything", None) is False
    assert verify_bearer_token("Bearer anything", "") is False


def test_verify_requires_bearer_prefix():
    assert verify_bearer_token("secret", "secret") is False
    assert verify_bearer_token("Basic secret", "secret") is False


def test_verify_matches_correct_token():
    assert verify_bearer_token("Bearer secret", "secret") is True


def test_verify_rejects_wrong_token():
    assert verify_bearer_token("Bearer nope", "secret") is False


def _wrapped_app(token):
    async def ok(request):
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/", ok)])
    return TestClient(BearerAuthMiddleware(app, token))


def test_middleware_401_without_token():
    client = _wrapped_app("secret")
    assert client.get("/").status_code == 401


def test_middleware_401_with_wrong_token():
    client = _wrapped_app("secret")
    resp = client.get("/", headers={"Authorization": "Bearer wrong"})
    assert resp.status_code == 401


def test_middleware_allows_valid_token():
    client = _wrapped_app("secret")
    resp = client.get("/", headers={"Authorization": "Bearer secret"})
    assert resp.status_code == 200
    assert resp.text == "ok"
