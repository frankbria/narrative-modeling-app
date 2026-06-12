"""
Request/response schemas for the workflow persistence API (issue #87).

Mirrors the frontend workflow state shape in
`apps/frontend/lib/contexts/WorkflowContext.tsx` (completedStages serialized
as a string array; stage values are the lowercase WorkflowStage enum values).
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


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


class WorkflowUpdateRequest(BaseModel):
    """Body for PUT /workflows/{dataset_id} — all fields optional (partial update)."""

    current_stage: Optional[str] = None
    completed_stages: Optional[List[str]] = None
    stage_data: Optional[Dict[str, Any]] = None
    model_id: Optional[str] = None
    deployment_id: Optional[str] = None

    model_config = {"populate_by_name": True}


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

    model_config = {"populate_by_name": True}


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
    """Version history for recovery/audit."""

    dataset_id: str
    total_versions: int
    entries: List[StateHistoryEntryResponse]

    model_config = {"populate_by_name": True}
