"""Owner lookup for datasets, backed by the shared `user_data` collection.

The MCP server resolves a `dataset_id` to its owning `user_id` here so tools can
verify ownership before touching S3. Beanie is initialized lazily on first use so
importing this module never opens a DB connection (keeps unit tests hermetic).
"""

import logging
import os

from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from models.user_data import UserData

logger = logging.getLogger(__name__)

_initialized = False


async def _ensure_initialized() -> None:
    global _initialized
    if _initialized:
        return
    client = AsyncIOMotorClient(os.getenv("MONGODB_URI"))
    await init_beanie(database=client.get_default_database(), document_models=[UserData])
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
