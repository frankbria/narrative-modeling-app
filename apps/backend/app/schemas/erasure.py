"""Schemas for dataset/user erasure (issue #259).

The DeletionManifest is the honest record of a best-effort cascade: it reports
exactly how many documents were removed from each collection, which S3 objects
and Redis keys were swept, and any failures that would need an idempotent
re-run. It is returned to the caller and snapshotted into the append-only
``ErasureAuditLog``.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(UTC)


class DeletionManifest(BaseModel):
    """What an erasure actually removed."""

    target_type: str = Field(..., description="'dataset' or 'user'")
    target_id: str = Field(..., description="dataset_id / UserData id, or user id")
    subject_user_id: str = Field(..., description="Owner of the erased data")

    documents_deleted: dict[str, int] = Field(
        default_factory=dict,
        description="Per-collection count of deleted documents (collection name -> count)",
    )
    s3_objects_deleted: list[str] = Field(
        default_factory=list, description="S3 keys removed (source files + model artifacts)"
    )
    redis_keys_evicted: int = Field(0, description="Number of Redis cache keys evicted")

    failures: list[str] = Field(
        default_factory=list,
        description="Human-readable descriptions of steps that failed (empty => clean erasure)",
    )
    idempotent_noop: bool = Field(
        False, description="True if the target was already fully erased (nothing to do)"
    )
    completed_at: datetime = Field(default_factory=_now)

    @property
    def total_documents_deleted(self) -> int:
        return sum(self.documents_deleted.values())

    @property
    def status(self) -> str:
        return "completed_with_residuals" if self.failures else "completed"


class EraseResponse(BaseModel):
    """API response for an erasure request."""

    erasure_id: str
    status: str
    manifest: DeletionManifest
