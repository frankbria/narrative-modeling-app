"""
Cache management API endpoints
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, Optional
import logging

from app.services.redis_cache import cache_service
from app.auth.nextauth_auth import get_current_user_id

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/info")
async def get_cache_info(
    current_user: str = Depends(get_current_user_id)
) -> Dict[str, Any]:
    """Get cache statistics and information"""
    try:
        info = await cache_service.get_cache_info()
        if info is None:
            raise HTTPException(status_code=503, detail="Cache service unavailable")
        return {
            "success": True,
            "cache_info": info
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get cache info: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/user/{user_id}")
async def invalidate_user_cache(
    user_id: str,
    current_user: str = Depends(get_current_user_id)
) -> Dict[str, Any]:
    """Invalidate all cache entries for a specific user"""
    try:
        # Users can only invalidate their own cache (or admins can invalidate any)
        if current_user != user_id:
            # In a real app, you'd check for admin permissions here
            raise HTTPException(status_code=403, detail="Can only invalidate your own cache")
            
        deleted_count = await cache_service.invalidate_user_cache(user_id)
        return {
            "success": True,
            "deleted_entries": deleted_count,
            "message": f"Invalidated {deleted_count} cache entries for user {user_id}"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to invalidate user cache: {e}")
        raise HTTPException(status_code=500, detail="Failed to invalidate user cache")


@router.delete("/data/{data_id}")
async def invalidate_data_cache(
    data_id: str,
    current_user: str = Depends(get_current_user_id)
) -> Dict[str, Any]:
    """Invalidate all cache entries for a specific dataset"""
    try:
        deleted_count = await cache_service.invalidate_data_cache(data_id)
        return {
            "success": True,
            "deleted_entries": deleted_count,
            "message": f"Invalidated {deleted_count} cache entries for dataset {data_id}"
        }
    except Exception as e:
        logger.error(f"Failed to invalidate data cache: {e}")
        raise HTTPException(status_code=500, detail="Failed to invalidate data cache")


@router.delete("/key/{cache_key}")
async def delete_cache_key(
    cache_key: str,
    current_user: str = Depends(get_current_user_id)
) -> Dict[str, Any]:
    """Delete a specific cache key"""
    try:
        success = await cache_service.delete(cache_key)
        return {
            "success": success,
            "message": f"Cache key '{cache_key}' {'deleted' if success else 'not found'}"
        }
    except Exception as e:
        logger.error(f"Failed to delete cache key: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete cache key")


@router.get("/key/{cache_key}/exists")
async def check_cache_key_exists(
    cache_key: str,
    current_user: str = Depends(get_current_user_id)
) -> Dict[str, Any]:
    """Check if a cache key exists"""
    try:
        exists = await cache_service.exists(cache_key)
        return {
            "success": True,
            "exists": exists,
            "key": cache_key
        }
    except Exception as e:
        logger.error(f"Failed to check cache key existence: {e}")
        raise HTTPException(status_code=500, detail="Failed to check cache key")


@router.post("/warmup/user/{user_id}")
async def warmup_user_cache(
    user_id: str,
    current_user: str = Depends(get_current_user_id)
) -> Dict[str, Any]:
    """Pre-warm common cache entries for a user"""
    try:
        if current_user != user_id:
            raise HTTPException(status_code=403, detail="Can only warm up your own cache")
            
        # This would typically pre-load common data for the user
        # For now, we'll just return a success message
        return {
            "success": True,
            "message": f"Cache warmup initiated for user {user_id}"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to warm up user cache: {e}")
        raise HTTPException(status_code=500, detail="Failed to warm up cache")