"""Whether an account is mailed when one of its jobs ends (#494).

A row exists only once an account has chosen; no row means the default, mail on. It holds
no personal data (the address stays in the NextAuth `users` collection and is read when a
message is sent), and account erasure keeps it: deleting it would silently opt the account
back in.
"""

from datetime import datetime
from typing import Annotated

from beanie import Document, Indexed
from pydantic import Field

from app.utils.datetime import utcnow


class NotificationPreference(Document):
    user_id: Annotated[str, Indexed(unique=True)]
    job_emails: bool = True
    updated_at: datetime = Field(default_factory=utcnow)

    class Settings:
        name = "notification_preferences"
