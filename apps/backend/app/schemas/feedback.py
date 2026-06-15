"""
Pydantic schemas for the in-app feedback collection endpoint (issue #152).
"""

from enum import Enum

from pydantic import BaseModel, Field
from typing import Optional


class FeedbackCategory(str, Enum):
    """Allowed feedback categories (mirrors the frontend widget dropdown)."""

    BUG = "bug"
    FEATURE_REQUEST = "feature_request"
    GENERAL = "general"
    ONBOARDING = "onboarding"


class FeedbackRequest(BaseModel):
    """Payload for submitting user feedback."""

    rating: int = Field(..., ge=1, le=5, description="Star rating, 1-5")
    category: FeedbackCategory = Field(
        FeedbackCategory.GENERAL, description="Feedback category"
    )
    message: str = Field(
        ..., min_length=1, max_length=2000, description="Free-text feedback message"
    )
    page_context: Optional[str] = Field(
        None, max_length=500, description="Path/URL the user was on when submitting"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "rating": 4,
                "category": "general",
                "message": "The onboarding flow was clear and easy to follow.",
                "page_context": "/onboarding",
            }
        }
    }


class FeedbackResponse(BaseModel):
    """Response returned after a feedback submission is stored."""

    feedback_id: str
    user_id: str
    rating: int
    category: FeedbackCategory
    message: str
    page_context: Optional[str] = None
    created_at: str  # ISO 8601
