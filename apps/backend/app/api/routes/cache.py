"""Cache management API endpoints.

Only the caller's own cache is addressable. Before issue #452 this router also
exposed Redis server stats, arbitrary key delete/probe and a glob-backed
dataset purge, so any authenticated user could evict any key in the shared
Redis — including the ``ratelimit:`` buckets, which made it a limiter bypass.
None of those routes had a caller anywhere in the product.
"""
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.auth.nextauth_auth import get_current_user_id
from app.services.redis_cache import cache_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.delete("/me")
async def purge_own_cache(
    current_user: str = Depends(get_current_user_id)
) -> dict[str, Any]:
    """Purge the calling user's own cache entries.

    The identity comes from the token, not the path, so there is no segment a
    caller could point at another tenant or expand into a glob.
    """
    if cache_service.redis_client is None:
        raise HTTPException(status_code=503, detail="Cache service unavailable")

    try:
        deleted_count = await cache_service.invalidate_user_cache(current_user)
    except Exception as e:
        logger.error(f"Failed to purge cache for user {current_user}: {e}")
        raise HTTPException(status_code=500, detail="Failed to purge cache")

    return {
        "success": True,
        "deleted_entries": deleted_count,
    }
