"""
API Key model for production model serving
"""
from datetime import datetime
from typing import Optional, List
from beanie import Document, Indexed
from pydantic import Field
import secrets
import string


class APIKey(Document):
    """API Key for accessing production model endpoints"""
    
    key_id: Indexed(str) = Field(description="Unique API key identifier")
    key_hash: str = Field(description="Hashed API key for security")
    name: str = Field(description="Friendly name for the API key")
    description: Optional[str] = Field(None, description="Description of key usage")
    
    user_id: Indexed(str) = Field(description="Owner user ID")
    
    # Permissions
    model_ids: List[str] = Field(default_factory=list, description="Allowed model IDs")
    rate_limit: int = Field(default=1000, description="Requests per hour")
    
    # Usage tracking
    total_requests: int = Field(default=0, description="Total requests made")
    last_used_at: Optional[datetime] = Field(None, description="Last usage timestamp")
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = Field(None, description="Expiration date")
    is_active: bool = Field(default=True)
    
    class Settings:
        name = "api_keys"
        indexes = [
            "key_id",
            "user_id",
            "is_active"
        ]
    
    @staticmethod
    def generate_key() -> str:
        """Generate a secure API key"""
        # Format: sk_live_<32 random characters>
        alphabet = string.ascii_letters + string.digits
        random_part = ''.join(secrets.choice(alphabet) for _ in range(32))
        return f"sk_live_{random_part}"
    
    def is_valid(self) -> bool:
        """Check if the API key is valid"""
        if not self.is_active:
            return False
        
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return False
        
        return True
    
    def has_model_access(self, model_id: str) -> bool:
        """Check if the API key has access to a specific model"""
        # Empty model_ids means access to all user's models
        if not self.model_ids:
            return True
        return model_id in self.model_ids