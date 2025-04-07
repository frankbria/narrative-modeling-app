# backend/app/api/routes/user_data.py

from fastapi import APIRouter, HTTPException, Depends
from beanie import PydanticObjectId
from typing import List
from models.user_data import UserData
from auth.clerk_auth import get_current_user_id

router = APIRouter()


@router.post("/", response_model=UserData)
async def create_user_data(
    user_data: UserData, user_id: str = Depends(get_current_user_id)
):
    user_data.userId = user_id
    await user_data.insert()
    return user_data


@router.get("/", response_model=List[UserData])
async def get_user_data_for_user(user_id: str = Depends(get_current_user_id)):
    return await UserData.find(UserData.userId == user_id).to_list()


@router.get("/{id}", response_model=UserData)
async def get_user_data(
    id: PydanticObjectId, user_id: str = Depends(get_current_user_id)
):
    doc = await UserData.get(id)
    if not doc or doc.userId != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return doc


@router.put("/{id}", response_model=UserData)
async def update_user_data(
    id: PydanticObjectId, updated: UserData, user_id: str = Depends(get_current_user_id)
):
    doc = await UserData.get(id)
    if not doc or doc.userId != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    updated.id = id
    updated.userId = user_id  # ensure this isn't overwritten
    await updated.save()
    return updated


@router.delete("/{id}")
async def delete_user_data(
    id: PydanticObjectId, user_id: str = Depends(get_current_user_id)
):
    doc = await UserData.get(id)
    if not doc or doc.userId != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    await doc.delete()
    return {"success": True}
