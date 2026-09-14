import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import mcp.utils.user_data as user_data


async def test_ensure_initialized_runs_once_under_concurrency(monkeypatch):
    """Concurrent first calls must init Beanie exactly once (no dup client)."""
    monkeypatch.setenv("MONGODB_DB", "narrative_modeling")
    user_data._initialized = False
    with patch.object(user_data, "AsyncIOMotorClient", MagicMock()) as client, patch.object(
        user_data, "init_beanie", new=AsyncMock()
    ) as init:
        await asyncio.gather(*[user_data._ensure_initialized() for _ in range(5)])

    assert init.await_count == 1
    assert client.call_count == 1
    assert user_data._initialized is True


def test_require_db_name_raises_when_unset(monkeypatch):
    """#540 AC2: an unset MONGODB_DB fails fast with a clear message (no silent fallback)."""
    monkeypatch.delenv("MONGODB_DB", raising=False)
    with pytest.raises(RuntimeError, match="MONGODB_DB is not set"):
        user_data.require_db_name()
    monkeypatch.setenv("MONGODB_DB", "   ")  # blank/whitespace also counts as unset
    with pytest.raises(RuntimeError):
        user_data.require_db_name()


def test_require_db_name_returns_configured_value(monkeypatch):
    monkeypatch.setenv("MONGODB_DB", "narrative_modeling")
    assert user_data.require_db_name() == "narrative_modeling"


async def test_ensure_initialized_selects_the_configured_database(monkeypatch):
    """#540 AC4: the DB Beanie is initialized against is MONGODB_DB (client[db_name]),
    NOT the driver's default database."""
    monkeypatch.setenv("MONGODB_DB", "narrative_modeling")
    monkeypatch.setenv("MONGODB_URI", "mongodb+srv://user:pw@cluster.example.net/")
    user_data._initialized = False
    client_cls = MagicMock()
    with patch.object(user_data, "AsyncIOMotorClient", client_cls), patch.object(
        user_data, "init_beanie", new=AsyncMock()
    ) as init:
        await user_data._ensure_initialized()

    client_instance = client_cls.return_value
    # Selected by name, and never via the default-database fallback (#540).
    client_instance.__getitem__.assert_called_once_with("narrative_modeling")
    client_instance.get_default_database.assert_not_called()
    assert init.await_args.kwargs["database"] is client_instance["narrative_modeling"]


async def test_get_user_data_returns_none_on_bad_id():
    """A malformed id / lookup error yields None, never raises."""
    with patch.object(
        user_data, "_ensure_initialized", new=AsyncMock()
    ), patch.object(
        user_data.UserData, "get", new=AsyncMock(side_effect=Exception("bad id"))
    ):
        assert await user_data.get_user_data_by_id("not-an-objectid") is None
