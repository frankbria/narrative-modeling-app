"""
User feedback persistence model (issue #152).

Stores in-app beta feedback submitted through the floating feedback widget so
the team can collect launch-readiness signal (ratings, bug reports, feature
requests) tied to the page the user was on.
"""

from datetime import datetime, timezone

from beanie import Document, Indexed, PydanticObjectId
from pydantic import Field
from typing import Optional


def get_current_time() -> datetime:
    """Get current UTC time for default timestamps."""
    return datetime.now(timezone.utc)


class Feedback(Document):
    """A single piece of user feedback — one document per submission."""

    feedback_id: Indexed(str) = Field(
        ..., description="Unique feedback identifier (UUID)"
    )
    user_id: Indexed(str) = Field(..., description="User who submitted the feedback")
    rating: int = Field(..., ge=1, le=5, description="Star rating, 1 (worst) to 5 (best)")
    category: str = Field(
        ..., description="Feedback category (bug, feature_request, general, onboarding)"
    )
    message: str = Field(..., description="Free-text feedback message")
    page_context: Optional[str] = Field(
        None, description="Path/URL the user was on when submitting"
    )
    created_at: datetime = Field(default_factory=get_current_time)

    class Settings:
        name = "feedback"
        indexes = [
            "feedback_id",
            "user_id",
            "category",
            "created_at",
        ]

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {
            PydanticObjectId: str,
            datetime: lambda dt: dt.isoformat(),
        },
    }
