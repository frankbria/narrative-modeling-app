# backend/app/api/routes/plot.py

from fastapi import APIRouter, HTTPException, Depends
from typing import List
from beanie import PydanticObjectId
from models.plot import Plot
from auth.clerk_auth import get_current_user_id

router = APIRouter()


@router.post("/", response_model=Plot)
async def create_plot(plot: Plot, user_id: str = Depends(get_current_user_id)):
    plot.userId = user_id
    await plot.insert()
    return plot


@router.get("/", response_model=List[Plot])
async def get_plots_for_user(user_id: str = Depends(get_current_user_id)):
    return await Plot.find(Plot.userId == user_id).to_list()


@router.get("/{id}", response_model=Plot)
async def get_plot(id: PydanticObjectId, user_id: str = Depends(get_current_user_id)):
    plot = await Plot.get(id)
    if not plot or plot.userId != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return plot


@router.put("/{id}", response_model=Plot)
async def update_plot(
    id: PydanticObjectId, updated: Plot, user_id: str = Depends(get_current_user_id)
):
    existing = await Plot.get(id)
    if not existing or existing.userId != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    updated.id = id
    updated.userId = user_id
    await updated.save()
    return updated


@router.delete("/{id}")
async def delete_plot(
    id: PydanticObjectId, user_id: str = Depends(get_current_user_id)
):
    plot = await Plot.get(id)
    if not plot or plot.userId != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    await plot.delete()
    return {"success": True}
