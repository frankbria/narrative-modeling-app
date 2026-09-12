"""GET /api/v1/ai/health is an authenticated endpoint (#563).

Every sibling handler in the AI router carries the auth dependency; this one did
not, so an anonymous caller could read internal deployment state and drive an
outbound MCP health call per request.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.main import app

pytestmark = pytest.mark.asyncio

PATH = "/api/v1/ai/health"


async def test_anonymous_caller_is_refused(async_test_client):
    """async_test_client points the app at the test database and installs no auth
    override, so this is a real anonymous request."""
    saved = dict(app.dependency_overrides)
    app.dependency_overrides.clear()
    try:
        with patch("app.api.routes.ai_analysis.mcp_service.check_health", new_callable=AsyncMock) as probe:
            response = await async_test_client.get(PATH)
        assert response.status_code == 401, response.text
        assert "mcp_available" not in response.text
        probe.assert_not_awaited()  # no outbound work for an anonymous caller
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(saved)


@pytest.mark.parametrize("up", [True, False])
async def test_authenticated_caller_gets_the_probe(async_authorized_client, up):
    with patch("app.api.routes.ai_analysis.mcp_service.check_health", new_callable=AsyncMock, return_value=up):
        response = await async_authorized_client.get(PATH)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["mcp_available"] is up
    assert body["status"] == ("healthy" if up else "unavailable")
