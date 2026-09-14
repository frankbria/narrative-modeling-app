"""Persistent onboarding progress, keyed by user (#541).

Progress used to be smuggled onto whatever `UserData.find_one({"user_id": ...})`
returned first — an *arbitrary* dataset document — and, for a user with no dataset
yet, the save path constructed a `UserData` with no `filename`/`s3_url`, which fails
validation and raised at the very first onboarding step. Progress is account-scoped
state, not dataset state, so it lives in its own collection.
"""

from datetime import datetime
from typing import Annotated, Any

from beanie import Document, Indexed
from pydantic import Field

from app.utils.datetime import utcnow


class OnboardingProgress(Document):
    """One onboarding-progress record per user.

    The full ``OnboardingUserProgress`` schema is stored as ``progress`` (a plain dict
    dump) so the schema can evolve without a migration; ``user_id`` is the unique key.
    """

    user_id: Annotated[str, Indexed(unique=True)]
    progress: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=utcnow)

    class Settings:
        name = "onboarding_progress"
