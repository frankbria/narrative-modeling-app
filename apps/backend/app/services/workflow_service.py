"""
Workflow state persistence service (issue #87).

CRUD for per-user/per-dataset workflow state with an automatic, capped
append-only version history of full state snapshots.
"""

import logging
import uuid
from typing import Any, Dict, List, Optional

from app.models.workflow import StateHistoryEntry, WorkflowState
from app.services.base_service import BaseService
from app.services.exceptions import ConflictError, NotFoundError

logger = logging.getLogger(__name__)

# Full-snapshot history entries live inside the document; cap them so the
# document can never grow toward MongoDB's 16MB limit. Latest entries are kept.
WORKFLOW_HISTORY_LIMIT = 50

# Fields a client may set on create/update (everything else is managed).
_UPDATABLE_FIELDS = (
    "current_stage",
    "completed_stages",
    "stage_data",
    "model_id",
    "deployment_id",
)


class WorkflowService(BaseService[WorkflowState]):
    """Service for workflow state persistence."""

    model_class = WorkflowState
    resource_name = "Workflow"

    def _get_id_field(self) -> str:
        return "workflow_id"

    async def get_by_dataset(self, user_id: str, dataset_id: str) -> WorkflowState:
        """Fetch the workflow for (user_id, dataset_id) or raise NotFoundError."""
        workflow = await WorkflowState.find_one(
            WorkflowState.user_id == user_id,
            WorkflowState.dataset_id == dataset_id,
        )
        if workflow is None:
            raise NotFoundError(
                resource_type=self.resource_name, resource_id=dataset_id
            )
        return workflow

    async def create_workflow(
        self,
        user_id: str,
        dataset_id: str,
        current_stage: str,
        completed_stages: Optional[List[str]] = None,
        stage_data: Optional[Dict[str, Any]] = None,
        model_id: Optional[str] = None,
        deployment_id: Optional[str] = None,
    ) -> WorkflowState:
        """Create the workflow for a dataset with its initial history entry.

        Raises ConflictError if one already exists for this user/dataset.
        The unique (user_id, dataset_id) index backs this check at the DB
        level; the explicit check keeps behavior consistent where indexes
        are skipped (mongomock unit tests).
        """
        existing = await WorkflowState.find_one(
            WorkflowState.user_id == user_id,
            WorkflowState.dataset_id == dataset_id,
        )
        if existing is not None:
            raise ConflictError(
                message=f"Workflow already exists for dataset '{dataset_id}'",
                existing_id=existing.workflow_id,
            )

        workflow = WorkflowState(
            workflow_id=str(uuid.uuid4()),
            user_id=user_id,
            dataset_id=dataset_id,
            current_stage=current_stage,
            completed_stages=completed_stages or [],
            stage_data=stage_data or {},
            model_id=model_id,
            deployment_id=deployment_id,
        )
        workflow.state_history = [workflow.snapshot(version=1)]
        await workflow.save()

        logger.info(
            "Created workflow %s for user %s dataset %s",
            workflow.workflow_id,
            user_id,
            dataset_id,
        )
        return workflow

    async def update_workflow(
        self, user_id: str, dataset_id: str, updates: Dict[str, Any]
    ) -> WorkflowState:
        """Apply a partial update and append a new history snapshot.

        Only keys in `updates` that are set (not None for optional scalars,
        present for collections) are applied; the snapshot captures the full
        post-update state with an incremented version.
        """
        workflow = await self.get_by_dataset(user_id, dataset_id)

        for field in _UPDATABLE_FIELDS:
            if field in updates and updates[field] is not None:
                setattr(workflow, field, updates[field])

        next_version = (
            workflow.state_history[-1].version + 1 if workflow.state_history else 1
        )
        workflow.state_history.append(workflow.snapshot(version=next_version))
        if len(workflow.state_history) > WORKFLOW_HISTORY_LIMIT:
            workflow.state_history = workflow.state_history[-WORKFLOW_HISTORY_LIMIT:]

        workflow.update_timestamp()
        await workflow.save()

        logger.info(
            "Updated workflow %s (version %d) for user %s dataset %s",
            workflow.workflow_id,
            next_version,
            user_id,
            dataset_id,
        )
        return workflow

    async def get_history(
        self, user_id: str, dataset_id: str
    ) -> List[StateHistoryEntry]:
        """Return the version history for recovery/audit."""
        workflow = await self.get_by_dataset(user_id, dataset_id)
        return workflow.state_history
