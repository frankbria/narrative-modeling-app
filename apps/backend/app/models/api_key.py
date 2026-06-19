"""
API Key model for production model serving
"""

import hashlib
import secrets
import string
from datetime import datetime, timezone
from typing import Annotated, List, Optional

from beanie import Document, Indexed
from pydantic import Field


class APIKey(Document):
    """API Key for accessing production model endpoints"""

    key_id: Annotated[str, Indexed()] = Field(description="Unique API key identifier")
    key_hash: str = Field(description="Hashed API key for security")
    name: str = Field(description="Friendly name for the API key")
    description: Optional[str] = Field(None, description="Description of key usage")

    user_id: Annotated[str, Indexed()] = Field(description="Owner user ID")

    # Permissions
    model_ids: List[str] = Field(default_factory=list, description="Allowed model IDs")
    rate_limit: int = Field(default=1000, description="Requests per hour")

    # Usage tracking
    total_requests: int = Field(default=0, description="Total requests made")
    last_used_at: Optional[datetime] = Field(None, description="Last usage timestamp")

    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = Field(None, description="Expiration date")
    is_active: bool = Field(default=True)

    class Settings:
        name = "api_keys"
        indexes = ["key_id", "user_id", "is_active"]

    @staticmethod
    def generate_key() -> str:
        """Generate a secure API key"""
        # Format: sk_live_<32 random characters>
        alphabet = string.ascii_letters + string.digits
        random_part = "".join(secrets.choice(alphabet) for _ in range(32))
        return f"sk_live_{random_part}"

    @staticmethod
    def hash_key(raw_key: str) -> str:
        """Hash a raw API key for secure storage and lookup.

        Single source of truth for the hashing scheme so the production routes
        and the rate-limit middleware (#151) never drift apart.
        """
        return hashlib.sha256(raw_key.encode()).hexdigest()

    def is_valid(self) -> bool:
        """Check if the API key is valid"""
        if not self.is_active:
            return False

        if self.expires_at:
            # Get current time as timezone-aware UTC datetime
            now = datetime.now(timezone.utc)

            # Normalize expires_at to UTC-aware datetime
            if self.expires_at.tzinfo is None:
                # Treat naive datetime as UTC
                expires_at_utc = self.expires_at.replace(tzinfo=timezone.utc)
            else:
                # Convert to UTC
                expires_at_utc = self.expires_at.astimezone(timezone.utc)

            if now > expires_at_utc:
                return False

        return True

    def has_model_access(self, model_id: str) -> bool:
        """Check if the API key has access to a specific model"""
        # Empty model_ids means access to all user's models
        if not self.model_ids:
            return True
        return model_id in self.model_ids
