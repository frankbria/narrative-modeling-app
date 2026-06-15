"""
In-app feedback collection API route (issue #152).

A single authenticated endpoint that persists beta feedback (rating, category,
message, page context) to MongoDB for later review.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.nextauth_auth import get_current_user_id
from app.models.feedback import Feedback
from app.schemas.feedback import FeedbackRequest, FeedbackResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_feedback(
    payload: FeedbackRequest,
    user_id: str = Depends(get_current_user_id),
) -> FeedbackResponse:
    """Store a piece of user feedback and return the persisted record."""
    feedback = Feedback(
        feedback_id=f"fb_{uuid.uuid4().hex[:12]}",
        user_id=user_id,
        rating=payload.rating,
        category=payload.category.value,
        message=payload.message,
        page_context=payload.page_context,
    )

    try:
        await feedback.insert()
    except Exception:  # pragma: no cover - defensive
        # Log internals (stack trace only — no user identifier in log sinks);
        # return an opaque message so storage/driver errors (which can embed
        # connection strings) never reach the client.
        logger.exception("Failed to store feedback")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store feedback. Please try again.",
        )

    return FeedbackResponse(
        feedback_id=feedback.feedback_id,
        user_id=feedback.user_id,
        rating=feedback.rating,
        category=payload.category,
        message=feedback.message,
        page_context=feedback.page_context,
        created_at=feedback.created_at.isoformat(),
    )
