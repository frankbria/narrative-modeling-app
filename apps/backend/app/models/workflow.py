"""
Workflow state persistence model (issue #87).

Stores the per-user, per-dataset ML workflow state (current stage, completed
stages, stage selections) so progress survives refreshes, crashes, and device
switches. Each saved change is also appended to an embedded version history of
full state snapshots for recovery/audit.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pymongo
from beanie import Document, Indexed, PydanticObjectId
from pydantic import BaseModel, Field
from pymongo import IndexModel


def get_current_time() -> datetime:
    """Get current UTC time for default timestamps."""
    return datetime.now(timezone.utc)


class StateHistoryEntry(BaseModel):
    """Full snapshot of workflow state at one version (simple append log)."""

    version: int = Field(
        ..., ge=1, description="Monotonically increasing version number"
    )
    current_stage: str = Field(..., description="Workflow stage at this version")
    completed_stages: List[str] = Field(
        default_factory=list, description="Stages completed at this version"
    )
    stage_data: Dict[str, Any] = Field(
        default_factory=dict, description="Per-stage selections at this version"
    )
    model_id: Optional[str] = Field(None, description="Trained model id, if any")
    deployment_id: Optional[str] = Field(None, description="Deployment id, if any")
    timestamp: datetime = Field(default_factory=get_current_time)


class WorkflowState(Document):
    """
    Workflow state document — one per (user_id, dataset_id).

    The top-level fields hold the current state; `state_history` holds the
    capped append log of full snapshots (latest entries kept).
    """

    # Ownership and identification
    workflow_id: Indexed(str) = Field(
        ..., description="Unique workflow identifier (UUID)"
    )
    user_id: Indexed(str) = Field(..., description="User who owns this workflow")
    dataset_id: Indexed(str) = Field(
        ..., description="Dataset this workflow belongs to"
    )

    # Current state
    current_stage: str = Field(..., description="Stage the user is currently on")
    completed_stages: List[str] = Field(
        default_factory=list, description="Stages the user has completed"
    )
    stage_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Key selections per stage (target column, recipes, features, training config)",
    )
    model_id: Optional[str] = Field(None, description="Trained model id, if any")
    deployment_id: Optional[str] = Field(None, description="Deployment id, if any")

    # Version history (append log of full snapshots)
    state_history: List[StateHistoryEntry] = Field(default_factory=list)

    # Timestamps
    created_at: datetime = Field(default_factory=get_current_time)
    updated_at: datetime = Field(default_factory=get_current_time)

    class Settings:
        name = "workflow_states"
        indexes = [
            "workflow_id",
            "user_id",
            "dataset_id",
            IndexModel(
                [("user_id", pymongo.ASCENDING), ("dataset_id", pymongo.ASCENDING)],
                name="user_dataset_unique",
                unique=True,
            ),
        ]

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {
            PydanticObjectId: str,
            datetime: lambda dt: dt.isoformat(),
        },
    }

    def update_timestamp(self) -> None:
        """Update the updated_at timestamp to current time."""
        self.updated_at = get_current_time()

    def snapshot(self, version: int) -> StateHistoryEntry:
        """Create a history entry capturing the full current state."""
        return StateHistoryEntry(
            version=version,
            current_stage=self.current_stage,
            completed_stages=list(self.completed_stages),
            stage_data=dict(self.stage_data),
            model_id=self.model_id,
            deployment_id=self.deployment_id,
        )
