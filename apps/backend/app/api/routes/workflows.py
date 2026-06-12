"""
Workflow persistence API routes (issue #87).

Endpoints (registered under {API_V1_STR}):
- POST /workflows/{dataset_id}          create workflow state (409 if exists)
- GET  /workflows/{dataset_id}          fetch workflow state (404 if missing)
- PUT  /workflows/{dataset_id}          partial update, appends history snapshot
- GET  /workflows/{dataset_id}/history  version history for recovery/audit

All lookups are scoped by the authenticated user, so another user's workflow
for the same dataset is a 404 (no existence leak), not a 403.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.nextauth_auth import get_current_user_id
from app.models.workflow import WorkflowState
from app.schemas.workflow import (
    StateHistoryEntryResponse,
    WorkflowCreateRequest,
    WorkflowHistoryResponse,
    WorkflowResponse,
    WorkflowUpdateRequest,
)
from app.services.exceptions import ConflictError, NotFoundError
from app.services.workflow_service import WorkflowService

logger = logging.getLogger(__name__)

router = APIRouter()


def _to_response(workflow: WorkflowState) -> WorkflowResponse:
    return WorkflowResponse.model_validate(workflow)


@router.post(
    "/workflows/{dataset_id}",
    response_model=WorkflowResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_workflow(
    dataset_id: str,
    request: WorkflowCreateRequest,
    current_user_id: str = Depends(get_current_user_id),
):
    """Create the workflow state for a dataset (one per user/dataset)."""
    try:
        logger.info(
            f"Creating workflow for user {current_user_id} dataset {dataset_id}"
        )
        service = WorkflowService()
        workflow = await service.create_workflow(
            user_id=current_user_id,
            dataset_id=dataset_id,
            current_stage=request.current_stage,
            completed_stages=request.completed_stages,
            stage_data=request.stage_data,
            model_id=request.model_id,
            deployment_id=request.deployment_id,
        )
        return _to_response(workflow)
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error creating workflow for user {current_user_id} dataset {dataset_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating the workflow",
        )


@router.get("/workflows/{dataset_id}", response_model=WorkflowResponse)
async def get_workflow(
    dataset_id: str,
    current_user_id: str = Depends(get_current_user_id),
):
    """Fetch the workflow state for a dataset."""
    try:
        service = WorkflowService()
        workflow = await service.get_by_dataset(current_user_id, dataset_id)
        return _to_response(workflow)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error fetching workflow for user {current_user_id} dataset {dataset_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching the workflow",
        )


@router.put("/workflows/{dataset_id}", response_model=WorkflowResponse)
async def update_workflow(
    dataset_id: str,
    request: WorkflowUpdateRequest,
    current_user_id: str = Depends(get_current_user_id),
):
    """Partially update the workflow state; appends a version history snapshot."""
    try:
        logger.info(
            f"Updating workflow for user {current_user_id} dataset {dataset_id}"
        )
        service = WorkflowService()
        workflow = await service.update_workflow(
            current_user_id,
            dataset_id,
            request.model_dump(exclude_unset=True),
        )
        return _to_response(workflow)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error updating workflow for user {current_user_id} dataset {dataset_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while updating the workflow",
        )


@router.get("/workflows/{dataset_id}/history", response_model=WorkflowHistoryResponse)
async def get_workflow_history(
    dataset_id: str,
    current_user_id: str = Depends(get_current_user_id),
):
    """Fetch the workflow version history for recovery/audit."""
    try:
        service = WorkflowService()
        history = await service.get_history(current_user_id, dataset_id)
        return WorkflowHistoryResponse(
            dataset_id=dataset_id,
            total_versions=len(history),
            latest_version=history[-1].version if history else 0,
            entries=[
                StateHistoryEntryResponse(
                    version=entry.version,
                    current_stage=entry.current_stage,
                    completed_stages=entry.completed_stages,
                    stage_data=entry.stage_data,
                    model_id=entry.model_id,
                    deployment_id=entry.deployment_id,
                    timestamp=entry.timestamp,
                )
                for entry in history
            ],
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error fetching workflow history for user {current_user_id} "
            f"dataset {dataset_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching the workflow history",
        )
