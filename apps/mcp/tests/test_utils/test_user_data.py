import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import mcp.utils.user_data as user_data


async def test_ensure_initialized_runs_once_under_concurrency():
    """Concurrent first calls must init Beanie exactly once (no dup client)."""
    user_data._initialized = False
    with patch.object(user_data, "AsyncIOMotorClient", MagicMock()) as client, patch.object(
        user_data, "init_beanie", new=AsyncMock()
    ) as init:
        await asyncio.gather(*[user_data._ensure_initialized() for _ in range(5)])

    assert init.await_count == 1
    assert client.call_count == 1
    assert user_data._initialized is True


async def test_get_user_data_returns_none_on_bad_id():
    """A malformed id / lookup error yields None, never raises."""
    with patch.object(
        user_data, "_ensure_initialized", new=AsyncMock()
    ), patch.object(
        user_data.UserData, "get", new=AsyncMock(side_effect=Exception("bad id"))
    ):
        assert await user_data.get_user_data_by_id("not-an-objectid") is None
