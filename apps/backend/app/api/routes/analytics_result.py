# backend/app/api/routes/analytics_result.py

from fastapi import APIRouter, HTTPException, Depends, Body
from typing import List
from beanie import PydanticObjectId
from app.models.analytics_result import AnalyticsResult
from app.schemas.analytics_result_in import AnalyticsResultIn
from app.schemas.analytics_result_out import AnalyticsResultOut
from app.auth.nextauth_auth import get_current_user_id

router = APIRouter()


@router.post("/", response_model=AnalyticsResultOut)
async def create_result(
    result_in: AnalyticsResultIn = Body(...),
    user_id: str = Depends(get_current_user_id),
):
    # Build the persistence model from the validated input data
    result = AnalyticsResult(**result_in.model_dump(), userId=user_id)
    await result.insert()
    # Convert the persistence model to the output schema before returning
    return AnalyticsResultOut.model_validate(result.model_dump())


@router.get("/", response_model=List[AnalyticsResultOut])
async def get_results_for_user(user_id: str = Depends(get_current_user_id)):
    results = await AnalyticsResult.find(AnalyticsResult.userId == user_id).to_list()
    return [
        AnalyticsResultOut.model_validate(result.model_dump()) for result in results
    ]


@router.get("/{id}", response_model=AnalyticsResultOut)
async def get_result(id: PydanticObjectId, user_id: str = Depends(get_current_user_id)):
    result = await AnalyticsResult.get(id)
    if not result or result.userId != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return AnalyticsResultOut.model_validate(result.model_dump())


@router.put("/{id}", response_model=AnalyticsResultOut)
async def update_result(
    id: PydanticObjectId,
    updated_in: AnalyticsResultIn = Body(...),
    user_id: str = Depends(get_current_user_id),
):
    existing = await AnalyticsResult.get(id)
    if not existing or existing.userId != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    # Build the updated persistence model from validated input data
    updated = AnalyticsResult(**updated_in.model_dump(), id=id, userId=user_id)
    await updated.save()
    return AnalyticsResultOut.model_validate(updated.model_dump())


@router.delete("/{id}")
async def delete_result(
    id: PydanticObjectId, user_id: str = Depends(get_current_user_id)
):
    result = await AnalyticsResult.get(id)
    if not result or result.userId != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    await result.delete()
    return {"success": True}
