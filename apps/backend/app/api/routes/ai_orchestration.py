"""AI orchestration / decision engine API (issue #89).

Endpoints (registered under /api/v1/ai):
- POST /recommend-tools     -> ranked tool recommendations + pipeline suggestion
- POST /optimize-parameters -> rule-based parameter suggestions for a tool
- POST /feedback            -> store feedback that personalizes future recommendations

All require auth and validate dataset ownership (404 for unknown/foreign datasets).
The recommend/optimize endpoints work fully without an OpenAI key (rule-based core).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.nextauth_auth import get_current_user_id
from app.schemas.ai_orchestration import (
    AIFeedbackRequest,
    AIFeedbackResponse,
    ParameterOptimizationRequest,
    ParameterOptimizationResponse,
    ToolRecommendationRequest,
    ToolRecommendationResponse,
)
from app.services.ai_orchestration_service import ai_orchestration_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/recommend-tools", response_model=ToolRecommendationResponse)
async def recommend_tools(
    request: ToolRecommendationRequest,
    user_id: str = Depends(get_current_user_id),
) -> ToolRecommendationResponse:
    """Recommend tools/transformations for a dataset and objective."""
    profile = await ai_orchestration_service.build_profile(request.dataset_id, user_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found",
        )
    return await ai_orchestration_service.recommend_tools(profile, request, user_id)


@router.post("/optimize-parameters", response_model=ParameterOptimizationResponse)
async def optimize_parameters(
    request: ParameterOptimizationRequest,
    user_id: str = Depends(get_current_user_id),
) -> ParameterOptimizationResponse:
    """Suggest optimized parameters for a tool given the dataset profile."""
    profile = await ai_orchestration_service.build_profile(request.dataset_id, user_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found",
        )
    return await ai_orchestration_service.optimize_parameters(profile, request)


@router.post(
    "/feedback",
    response_model=AIFeedbackResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_recommendation_feedback(
    request: AIFeedbackRequest,
    user_id: str = Depends(get_current_user_id),
) -> AIFeedbackResponse:
    """Store user feedback on an AI recommendation."""
    try:
        feedback = await ai_orchestration_service.record_feedback(request, user_id)
    except Exception:
        logger.exception("Failed to store recommendation feedback")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store feedback. Please try again.",
        )
    return AIFeedbackResponse(
        feedback_id=feedback.feedback_id,
        recommendation_id=feedback.recommendation_id,
        tool_type=feedback.tool_type,
        action=request.action,
        created_at=feedback.created_at.isoformat(),
    )
