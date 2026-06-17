"""
Tests for WorkflowService (issue #87 — backend workflow persistence).

Integration tests against the real test MongoDB (no mocking), covering
create/update/get, version history accumulation, and the history cap.
"""

import pytest

from app.services.exceptions import ConflictError, NotFoundError

USER_ID = "test_user_123"
OTHER_USER_ID = "other_user_456"
DATASET_ID = "dataset_wf_1"


def _make_service():
    from app.services.workflow_service import WorkflowService

    return WorkflowService()


async def _create_default_workflow(service, user_id=USER_ID, dataset_id=DATASET_ID):
    return await service.create_workflow(
        user_id=user_id,
        dataset_id=dataset_id,
        current_stage="data_loading",
        completed_stages=[],
        stage_data={},
    )


@pytest.mark.integration
class TestWorkflowServiceCreate:
    @pytest.mark.asyncio
    async def test_create_workflow_generates_id_and_initial_history(
        self, setup_database
    ):
        service = _make_service()

        workflow = await _create_default_workflow(service)

        assert workflow.workflow_id
        assert workflow.user_id == USER_ID
        assert workflow.dataset_id == DATASET_ID
        assert workflow.current_stage == "data_loading"
        assert workflow.completed_stages == []
        assert len(workflow.state_history) == 1
        assert workflow.state_history[0].version == 1
        assert workflow.state_history[0].current_stage == "data_loading"

    @pytest.mark.asyncio
    async def test_create_duplicate_workflow_raises_conflict(self, setup_database):
        service = _make_service()
        await _create_default_workflow(service)

        with pytest.raises(ConflictError):
            await _create_default_workflow(service)

    @pytest.mark.asyncio
    async def test_concurrent_create_race_raises_conflict(self, setup_database):
        """When two creates race past the find_one check, the unique index
        rejects the loser; the resulting DuplicateKeyError must surface as
        ConflictError (409), not an unhandled 500.

        Both tasks await their duplicate-check I/O before either saves, so
        the loser always hits the index rather than the explicit check.
        """
        import asyncio

        from app.models.workflow import WorkflowState

        service = _make_service()

        results = await asyncio.gather(
            _create_default_workflow(service),
            _create_default_workflow(service),
            return_exceptions=True,
        )

        created = [r for r in results if isinstance(r, WorkflowState)]
        conflicts = [r for r in results if isinstance(r, ConflictError)]
        assert len(created) == 1, f"expected exactly one winner, got {results!r}"
        assert len(conflicts) == 1, (
            f"expected ConflictError for the loser, got {results!r}"
        )

    @pytest.mark.asyncio
    async def test_same_dataset_different_users_both_allowed(self, setup_database):
        service = _make_service()
        first = await _create_default_workflow(service)
        second = await _create_default_workflow(service, user_id=OTHER_USER_ID)

        assert first.workflow_id != second.workflow_id


@pytest.mark.integration
class TestWorkflowServiceGet:
    @pytest.mark.asyncio
    async def test_get_by_dataset_returns_workflow(self, setup_database):
        service = _make_service()
        created = await _create_default_workflow(service)

        fetched = await service.get_by_dataset(USER_ID, DATASET_ID)

        assert fetched.workflow_id == created.workflow_id

    @pytest.mark.asyncio
    async def test_get_by_dataset_missing_raises_not_found(self, setup_database):
        service = _make_service()

        with pytest.raises(NotFoundError):
            await service.get_by_dataset(USER_ID, "no_such_dataset")

    @pytest.mark.asyncio
    async def test_get_by_dataset_is_user_scoped(self, setup_database):
        service = _make_service()
        await _create_default_workflow(service)

        with pytest.raises(NotFoundError):
            await service.get_by_dataset(OTHER_USER_ID, DATASET_ID)


@pytest.mark.integration
class TestWorkflowServiceUpdate:
    @pytest.mark.asyncio
    async def test_update_appends_history_with_incremented_version(
        self, setup_database
    ):
        service = _make_service()
        created = await _create_default_workflow(service)

        updated = await service.update_workflow(
            USER_ID,
            DATASET_ID,
            {
                "current_stage": "data_profiling",
                "completed_stages": ["data_loading"],
                "stage_data": {"data_loading": {"datasetId": DATASET_ID}},
            },
        )

        assert updated.current_stage == "data_profiling"
        assert updated.completed_stages == ["data_loading"]
        assert len(updated.state_history) == 2
        assert updated.state_history[-1].version == 2
        assert updated.state_history[-1].current_stage == "data_profiling"
        assert updated.updated_at > created.updated_at

    @pytest.mark.asyncio
    async def test_update_is_partial(self, setup_database):
        service = _make_service()
        await _create_default_workflow(service)

        updated = await service.update_workflow(
            USER_ID, DATASET_ID, {"model_id": "model_abc"}
        )

        # Untouched fields are preserved
        assert updated.current_stage == "data_loading"
        assert updated.model_id == "model_abc"

    @pytest.mark.asyncio
    async def test_update_missing_workflow_raises_not_found(self, setup_database):
        service = _make_service()

        with pytest.raises(NotFoundError):
            await service.update_workflow(USER_ID, "no_such_dataset", {"model_id": "m"})

    @pytest.mark.asyncio
    async def test_history_accumulates_across_updates(self, setup_database):
        service = _make_service()
        await _create_default_workflow(service)

        stages = ["data_profiling", "data_preparation", "feature_engineering"]
        for stage in stages:
            await service.update_workflow(USER_ID, DATASET_ID, {"current_stage": stage})

        history = await service.get_history(USER_ID, DATASET_ID)

        assert [entry.version for entry in history] == [1, 2, 3, 4]
        assert [entry.current_stage for entry in history[1:]] == stages

    @pytest.mark.asyncio
    async def test_history_entry_snapshots_full_state(self, setup_database):
        """Each history entry must contain enough to reconstruct state fully."""
        service = _make_service()
        await _create_default_workflow(service)

        await service.update_workflow(
            USER_ID,
            DATASET_ID,
            {
                "current_stage": "model_training",
                "completed_stages": ["data_loading", "data_profiling"],
                "stage_data": {"features": {"selected": ["a", "b"]}},
                "model_id": "model_xyz",
                "deployment_id": "deploy_1",
            },
        )

        history = await service.get_history(USER_ID, DATASET_ID)
        latest = history[-1]

        assert latest.current_stage == "model_training"
        assert latest.completed_stages == ["data_loading", "data_profiling"]
        assert latest.stage_data == {"features": {"selected": ["a", "b"]}}
        assert latest.model_id == "model_xyz"
        assert latest.deployment_id == "deploy_1"
        assert latest.timestamp is not None

    @pytest.mark.asyncio
    async def test_history_is_capped_keeping_latest_entries(self, setup_database):
        from app.services.workflow_service import WORKFLOW_HISTORY_LIMIT

        service = _make_service()
        await _create_default_workflow(service)

        total_updates = WORKFLOW_HISTORY_LIMIT + 5
        for i in range(total_updates):
            await service.update_workflow(
                USER_ID, DATASET_ID, {"stage_data": {"step": {"i": i}}}
            )

        history = await service.get_history(USER_ID, DATASET_ID)

        assert len(history) == WORKFLOW_HISTORY_LIMIT
        # Versions keep incrementing past the cap; oldest entries are dropped
        expected_last_version = total_updates + 1  # +1 for the create entry
        assert history[-1].version == expected_last_version
        assert history[0].version == expected_last_version - WORKFLOW_HISTORY_LIMIT + 1
