"""Account-scoped settings of the signed-in user (#494)."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from app.auth.nextauth_auth import get_current_user_id
from app.services import job_notifications

router = APIRouter()


class NotificationPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_emails: bool = Field(
        description="Email the account when a training or batch prediction job ends"
    )


@router.get("/me/notification-preferences", response_model=NotificationPreferences)
async def get_notification_preferences(
    current_user_id: str = Depends(get_current_user_id),
) -> NotificationPreferences:
    """Whether the caller is emailed when a job ends. On until turned off."""
    return NotificationPreferences(
        job_emails=await job_notifications.wants_job_emails(current_user_id)
    )


@router.put("/me/notification-preferences", response_model=NotificationPreferences)
async def update_notification_preferences(
    preferences: NotificationPreferences,
    current_user_id: str = Depends(get_current_user_id),
) -> NotificationPreferences:
    """Turn the caller's job emails on or off."""
    await job_notifications.set_job_emails(current_user_id, preferences.job_emails)
    return preferences
