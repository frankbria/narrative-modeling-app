"""Append-only erasure audit log (issue #259).

One immutable document per erasure operation (dataset or whole-user), recording
who requested it, what was targeted, and the resulting deletion manifest. The
service only ever *inserts* these — nothing updates or deletes them — so the log
is an auditable, tamper-evident record supporting GDPR/CCPA right-to-erasure.
"""

from datetime import UTC, datetime
from typing import Annotated, Any

from beanie import Document, Indexed, PydanticObjectId
from pydantic import Field


def get_current_time() -> datetime:
    """Get current UTC time for default timestamps."""
    return datetime.now(UTC)


class ErasureAuditLog(Document):
    """Immutable record of a completed erasure operation."""

    erasure_id: Annotated[str, Indexed()] = Field(..., description="Unique erasure operation id (UUID)")
    actor_id: Annotated[str, Indexed()] = Field(..., description="User who requested the erasure")
    subject_user_id: Annotated[str, Indexed()] = Field(..., description="Owner of the erased data")
    target_type: str = Field(..., description="'dataset' or 'user'")
    target_id: str = Field(..., description="dataset_id / UserData id, or the user id for a full-user erasure")
    reason: str | None = Field(None, description="Optional caller-supplied reason (e.g. 'gdpr_request')")
    manifest: dict[str, Any] = Field(..., description="Serialized DeletionManifest snapshot")
    status: str = Field(..., description="'completed' or 'completed_with_residuals'")
    created_at: datetime = Field(default_factory=get_current_time)

    class Settings:
        name = "erasure_audit_log"
        indexes = [
            "erasure_id",
            "actor_id",
            "subject_user_id",
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
