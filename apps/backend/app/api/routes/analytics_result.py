# backend/app/api/routes/analytics_result.py

from fastapi import APIRouter, HTTPException, Depends
from typing import List
from beanie import PydanticObjectId
from app.models.analytics_result import AnalyticsResult
from app.auth.clerk_auth import get_current_user_id

router = APIRouter()


@router.post("/", response_model=AnalyticsResult)
async def create_result(
    result: AnalyticsResult, user_id: str = Depends(get_current_user_id)
):
    result.userId = user_id
    await result.insert()
    return result


@router.get("/", response_model=List[AnalyticsResult])
async def get_results_for_user(user_id: str = Depends(get_current_user_id)):
    return await AnalyticsResult.find(AnalyticsResult.userId == user_id).to_list()


@router.get("/{id}", response_model=AnalyticsResult)
async def get_result(id: PydanticObjectId, user_id: str = Depends(get_current_user_id)):
    result = await AnalyticsResult.get(id)
    if not result or result.userId != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return result


@router.put("/{id}", response_model=AnalyticsResult)
async def update_result(
    id: PydanticObjectId,
    updated: AnalyticsResult,
    user_id: str = Depends(get_current_user_id),
):
    existing = await AnalyticsResult.get(id)
    if not existing or existing.userId != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    updated.id = id
    updated.userId = user_id
    await updated.save()
    return updated


@router.delete("/{id}")
async def delete_result(
    id: PydanticObjectId, user_id: str = Depends(get_current_user_id)
):
    result = await AnalyticsResult.get(id)
    if not result or result.userId != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    await result.delete()
    return {"success": True}
