"""
Request/response schemas for the workflow persistence API (issue #87).

Mirrors the frontend workflow state shape in
`apps/frontend/lib/contexts/WorkflowContext.tsx` (completedStages serialized
as a string array; stage values are the lowercase WorkflowStage enum values).
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

# stage_data is user-controlled and snapshotted into up to 50 history entries
# per document; cap its serialized size so a workflow document can never
# approach MongoDB's 16MB limit (50 × 256KB = 12.8MB worst case).
MAX_STAGE_DATA_BYTES = 256 * 1024


def _check_stage_data_size(v: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if v is not None and len(json.dumps(v, default=str)) > MAX_STAGE_DATA_BYTES:
        raise ValueError(
            f"stage_data exceeds {MAX_STAGE_DATA_BYTES} bytes when serialized"
        )
    return v


class WorkflowCreateRequest(BaseModel):
    """Body for POST /workflows/{dataset_id}."""

    current_stage: str = Field(..., description="Stage the user is currently on")
    completed_stages: List[str] = Field(
        default_factory=list, description="Stages the user has completed"
    )
    stage_data: Dict[str, Any] = Field(
        default_factory=dict, description="Key selections per stage"
    )
    model_id: Optional[str] = Field(None, description="Trained model id, if any")
    deployment_id: Optional[str] = Field(None, description="Deployment id, if any")

    model_config = {"populate_by_name": True}

    @field_validator("stage_data")
    @classmethod
    def check_stage_data_size(
        cls, v: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        return _check_stage_data_size(v)


class WorkflowUpdateRequest(BaseModel):
    """Body for PUT /workflows/{dataset_id} — all fields optional (partial update)."""

    current_stage: Optional[str] = None
    completed_stages: Optional[List[str]] = None
    stage_data: Optional[Dict[str, Any]] = None
    model_id: Optional[str] = Field(
        None,
        description="Trained model id. Explicit null is a no-op (cannot unset); "
        "workflow progress is forward-only in beta.",
    )
    deployment_id: Optional[str] = Field(
        None,
        description="Deployment id. Explicit null is a no-op (cannot unset); "
        "workflow progress is forward-only in beta.",
    )

    model_config = {"populate_by_name": True}

    @field_validator("stage_data")
    @classmethod
    def check_stage_data_size(
        cls, v: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        return _check_stage_data_size(v)


class WorkflowResponse(BaseModel):
    """Full workflow state."""

    workflow_id: str
    dataset_id: str
    current_stage: str
    completed_stages: List[str]
    stage_data: Dict[str, Any]
    model_id: Optional[str] = None
    deployment_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"populate_by_name": True, "from_attributes": True}


class StateHistoryEntryResponse(BaseModel):
    """One full-state snapshot in the version history."""

    version: int
    current_stage: str
    completed_stages: List[str]
    stage_data: Dict[str, Any]
    model_id: Optional[str] = None
    deployment_id: Optional[str] = None
    timestamp: datetime

    model_config = {"populate_by_name": True}


class WorkflowHistoryResponse(BaseModel):
    """Version history for recovery/audit.

    History is capped server-side (latest 50 snapshots kept), so
    `total_versions` counts the returned entries while `latest_version`
    is the lifetime version counter — when they diverge, older entries
    have been dropped.
    """

    dataset_id: str
    total_versions: int
    latest_version: int = Field(
        0, description="Lifetime version counter (0 when history is empty)"
    )
    entries: List[StateHistoryEntryResponse]

    model_config = {"populate_by_name": True}
