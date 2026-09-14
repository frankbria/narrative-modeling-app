"""Owner lookup for datasets, backed by the shared `user_data` collection.

The MCP server resolves a `dataset_id` to its owning `user_id` here so tools can
verify ownership before touching S3. Beanie is initialized lazily on first use so
importing this module never opens a DB connection (keeps unit tests hermetic).
"""

import asyncio
import logging
import os

from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from models.user_data import UserData

logger = logging.getLogger(__name__)

_initialized = False
_init_lock = asyncio.Lock()


def require_db_name() -> str:
    """The Mongo database name, read explicitly from MONGODB_DB (#540).

    The backend selects its database with ``client[MONGODB_DB]`` and MONGODB_URI is
    bare (no default database — the normal Atlas SRV shape). The MCP server used
    ``get_default_database()``, which on such a URI resolves to a DIFFERENT database
    (the driver's ``test`` fallback), so it looked up owner records in a database
    that never contains them and answered "access denied" for legitimate requests —
    a config error wearing an authorization error's clothes. Fail fast with a clear
    message instead of silently falling back.
    """
    db_name = (os.getenv("MONGODB_DB") or "").strip()
    if not db_name:
        raise RuntimeError(
            "MONGODB_DB is not set. The MCP server selects its Mongo database "
            "explicitly (like the backend); set MONGODB_DB to the same value the "
            "backend uses, or owner lookups will hit the wrong database (#540)."
        )
    return db_name


async def _ensure_initialized() -> None:
    global _initialized
    if _initialized:
        return
    # Double-checked under a lock: concurrent first calls must not each build a
    # Motor client / re-run init_beanie (check-then-act straddles the await).
    async with _init_lock:
        if _initialized:
            return
        db_name = require_db_name()
        client = AsyncIOMotorClient(os.getenv("MONGODB_URI"))
        await init_beanie(database=client[db_name], document_models=[UserData])
        _initialized = True


async def get_user_data_by_id(dataset_id: str) -> UserData | None:
    """Return the UserData record for a dataset, or None if missing/invalid.

    A malformed id or DB error yields None (never raises) so callers surface a
    single generic "not found or access denied" response.
    """
    try:
        await _ensure_initialized()
        return await UserData.get(dataset_id)
    except Exception:
        logger.warning("Failed to load UserData for dataset_id", exc_info=True)
        return None
