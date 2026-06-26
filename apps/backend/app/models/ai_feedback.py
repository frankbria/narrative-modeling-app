"""AI recommendation feedback persistence (issue #89).

Stores user reactions to AI orchestration recommendations so the engine can make
context-aware, personalized suggestions over time. Separate collection (mirrors
how DataIssueRecord is separate from DatasetMetadata) so feedback can be queried
across datasets per tool type.
"""

from datetime import UTC, datetime
from typing import Annotated, Any

from beanie import Document, Indexed, PydanticObjectId
from pydantic import Field


def get_current_time() -> datetime:
    """Get current UTC time for default timestamps."""
    return datetime.now(UTC)


class AIRecommendationFeedback(Document):
    """A single piece of feedback on an AI recommendation."""

    feedback_id: Annotated[str, Indexed()] = Field(..., description="Unique feedback id (UUID)")
    user_id: Annotated[str, Indexed()] = Field(..., description="User who gave the feedback")
    recommendation_id: str = Field(..., description="Recommendation this feedback refers to")
    tool_type: Annotated[str, Indexed()] = Field(..., description="Tool the recommendation was for")
    action: Annotated[str, Indexed()] = Field(
        ..., description="accepted | rejected | modified"
    )
    dataset_id: str | None = None
    rating: int | None = Field(None, ge=1, le=5)
    comment: str | None = None
    modification: dict[str, Any] | None = Field(
        None, description="User's edits when action is 'modified'"
    )
    context: dict[str, Any] | None = Field(
        None, description="Snapshot of the recommendation/profile at feedback time"
    )
    created_at: datetime = Field(default_factory=get_current_time)

    class Settings:
        name = "ai_recommendation_feedback"
        indexes = [
            "feedback_id",
            "user_id",
            "tool_type",
            "action",
            [("user_id", 1), ("tool_type", 1)],
        ]

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {
            PydanticObjectId: str,
            datetime: lambda dt: dt.isoformat(),
        },
    }
