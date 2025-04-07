# backend/app/api/routes/trained_model.py

from fastapi import APIRouter, HTTPException, Depends
from typing import List
from beanie import PydanticObjectId
from app.models.trained_model import TrainedModel
from app.auth.clerk_auth import get_current_user_id

router = APIRouter()


@router.post("/", response_model=TrainedModel)
async def create_model(
    model: TrainedModel, user_id: str = Depends(get_current_user_id)
):
    model.userId = user_id
    await model.insert()
    return model


@router.get("/", response_model=List[TrainedModel])
async def get_models_for_user(user_id: str = Depends(get_current_user_id)):
    return await TrainedModel.find(TrainedModel.userId == user_id).to_list()


@router.get("/{id}", response_model=TrainedModel)
async def get_model(id: PydanticObjectId, user_id: str = Depends(get_current_user_id)):
    model = await TrainedModel.get(id)
    if not model or model.userId != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return model


@router.put("/{id}", response_model=TrainedModel)
async def update_model(
    id: PydanticObjectId,
    updated: TrainedModel,
    user_id: str = Depends(get_current_user_id),
):
    existing = await TrainedModel.get(id)
    if not existing or existing.userId != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    updated.id = id
    updated.userId = user_id
    await updated.save()
    return updated


@router.delete("/{id}")
async def delete_model(
    id: PydanticObjectId, user_id: str = Depends(get_current_user_id)
):
    model = await TrainedModel.get(id)
    if not model or model.userId != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    await model.delete()
    return {"success": True}
