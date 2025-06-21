"""
Onboarding API routes for guiding new users through the platform
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.api.deps import get_current_user_id
from app.services.onboarding_service import OnboardingService
from app.schemas.onboarding import (
    OnboardingStatusResponse,
    OnboardingStepResponse, 
    CompleteStepRequest,
    TutorialProgressResponse,
    SampleDatasetResponse
)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.get("/status", response_model=OnboardingStatusResponse)
async def get_onboarding_status(
    user_id: str = Depends(get_current_user_id)
):
    """Get user's onboarding progress and status"""
    
    service = OnboardingService()
    status = await service.get_user_onboarding_status(user_id)
    
    return OnboardingStatusResponse(**status)


@router.get("/steps", response_model=List[OnboardingStepResponse])
async def get_onboarding_steps(
    user_id: str = Depends(get_current_user_id)
):
    """Get all onboarding steps with current progress"""
    
    service = OnboardingService()
    steps = await service.get_onboarding_steps(user_id)
    
    return [OnboardingStepResponse(**step) for step in steps]


@router.get("/steps/{step_id}", response_model=OnboardingStepResponse)
async def get_onboarding_step(
    step_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """Get detailed information about a specific onboarding step"""
    
    service = OnboardingService()
    step = await service.get_onboarding_step(user_id, step_id)
    
    if not step:
        raise HTTPException(status_code=404, detail="Onboarding step not found")
    
    return OnboardingStepResponse(**step)


@router.post("/steps/{step_id}/complete")
async def complete_onboarding_step(
    step_id: str,
    request: CompleteStepRequest,
    user_id: str = Depends(get_current_user_id)
):
    """Mark an onboarding step as completed"""
    
    service = OnboardingService()
    
    try:
        result = await service.complete_step(
            user_id=user_id,
            step_id=step_id,
            completion_data=request.completion_data
        )
        
        return {
            "success": True,
            "message": "Step completed successfully",
            "next_step": result.get("next_step"),
            "progress_percentage": result.get("progress_percentage"),
            "achievements": result.get("achievements", [])
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/skip-step/{step_id}")
async def skip_onboarding_step(
    step_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """Skip an onboarding step (if skippable)"""
    
    service = OnboardingService()
    
    try:
        result = await service.skip_step(user_id, step_id)
        
        return {
            "success": True,
            "message": "Step skipped",
            "next_step": result.get("next_step"),
            "progress_percentage": result.get("progress_percentage")
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/tutorial-progress", response_model=TutorialProgressResponse)
async def get_tutorial_progress(
    user_id: str = Depends(get_current_user_id)
):
    """Get detailed tutorial progress with metrics"""
    
    service = OnboardingService()
    progress = await service.get_tutorial_progress(user_id)
    
    return TutorialProgressResponse(**progress)


@router.get("/sample-datasets", response_model=List[SampleDatasetResponse])
async def get_sample_datasets(
    user_id: str = Depends(get_current_user_id)
):
    """Get available sample datasets for onboarding"""
    
    service = OnboardingService()
    datasets = await service.get_sample_datasets()
    
    return [SampleDatasetResponse(**dataset) for dataset in datasets]


@router.post("/sample-datasets/{dataset_id}/load")
async def load_sample_dataset(
    dataset_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """Load a sample dataset for the user to practice with"""
    
    service = OnboardingService()
    
    try:
        result = await service.load_sample_dataset(user_id, dataset_id)
        
        return {
            "success": True,
            "dataset_id": result["dataset_id"],
            "upload_id": result["upload_id"],
            "message": "Sample dataset loaded successfully",
            "suggested_next_steps": result.get("suggested_next_steps", [])
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/reset")
async def reset_onboarding(
    user_id: str = Depends(get_current_user_id)
):
    """Reset user's onboarding progress (start over)"""
    
    service = OnboardingService()
    
    try:
        await service.reset_onboarding_progress(user_id)
        
        return {
            "success": True,
            "message": "Onboarding progress reset successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to reset onboarding progress")


@router.get("/achievements")
async def get_user_achievements(
    user_id: str = Depends(get_current_user_id)
):
    """Get user's onboarding achievements and badges"""
    
    service = OnboardingService()
    achievements = await service.get_user_achievements(user_id)
    
    return {
        "achievements": achievements,
        "total_points": sum(a.get("points", 0) for a in achievements),
        "badges_earned": [a for a in achievements if a.get("type") == "badge"],
        "milestones_reached": [a for a in achievements if a.get("type") == "milestone"]
    }


@router.get("/help-tips")
async def get_contextual_help(
    current_step: Optional[str] = None,
    user_id: str = Depends(get_current_user_id)
):
    """Get contextual help tips based on current step"""
    
    service = OnboardingService()
    tips = await service.get_contextual_help(user_id, current_step)
    
    return {
        "tips": tips,
        "help_articles": service.get_help_articles(),
        "video_tutorials": service.get_video_tutorials(),
        "support_contact": {
            "email": "support@narrativemodeling.ai",
            "docs": "https://docs.narrativemodeling.ai",
            "chat": "/support/chat"
        }
    }