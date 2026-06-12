"""
TDD tests for Workflow persistence API routes (issue #87).

Endpoints under test:
- POST /api/v1/workflows/{dataset_id}   create workflow state (201, 409 dup)
- GET  /api/v1/workflows/{dataset_id}   fetch workflow state (200, 404)
- PUT  /api/v1/workflows/{dataset_id}   update + append history (200, 404)
- GET  /api/v1/workflows/{dataset_id}/history   version history for recovery

Auth fixture maps to user "test_user_123".
"""

import pytest


DATASET_ID = "dataset_wf_api_1"

CREATE_PAYLOAD = {
    "current_stage": "data_profiling",
    "completed_stages": ["data_loading"],
    "stage_data": {"data_loading": {"datasetId": DATASET_ID}},
}


@pytest.mark.integration
class TestCreateWorkflow:
    @pytest.mark.asyncio
    async def test_create_returns_201_with_state(
        self, async_authorized_client, setup_database
    ):
        response = await async_authorized_client.post(
            f"/api/v1/workflows/{DATASET_ID}", json=CREATE_PAYLOAD
        )

        assert response.status_code == 201
        data = response.json()
        assert data["workflow_id"]
        assert data["dataset_id"] == DATASET_ID
        assert data["current_stage"] == "data_profiling"
        assert data["completed_stages"] == ["data_loading"]
        assert data["stage_data"] == CREATE_PAYLOAD["stage_data"]
        assert "created_at" in data and "updated_at" in data

    @pytest.mark.asyncio
    async def test_duplicate_create_returns_409(
        self, async_authorized_client, setup_database
    ):
        first = await async_authorized_client.post(
            f"/api/v1/workflows/{DATASET_ID}", json=CREATE_PAYLOAD
        )
        assert first.status_code == 201

        duplicate = await async_authorized_client.post(
            f"/api/v1/workflows/{DATASET_ID}", json=CREATE_PAYLOAD
        )
        assert duplicate.status_code == 409

    @pytest.mark.asyncio
    async def test_create_requires_auth(self, async_test_client, setup_database):
        response = await async_test_client.post(
            f"/api/v1/workflows/{DATASET_ID}", json=CREATE_PAYLOAD
        )
        assert response.status_code in (401, 403)


@pytest.mark.integration
class TestGetWorkflow:
    @pytest.mark.asyncio
    async def test_get_returns_workflow_state(
        self, async_authorized_client, setup_database
    ):
        await async_authorized_client.post(
            f"/api/v1/workflows/{DATASET_ID}", json=CREATE_PAYLOAD
        )

        response = await async_authorized_client.get(f"/api/v1/workflows/{DATASET_ID}")

        assert response.status_code == 200
        data = response.json()
        assert data["dataset_id"] == DATASET_ID
        assert data["current_stage"] == "data_profiling"
        assert data["completed_stages"] == ["data_loading"]

    @pytest.mark.asyncio
    async def test_get_missing_returns_404(
        self, async_authorized_client, setup_database
    ):
        response = await async_authorized_client.get(
            "/api/v1/workflows/no_such_dataset"
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_other_users_workflow_returns_404(
        self, async_authorized_client, setup_database
    ):
        """Lookups are user-scoped: another user's workflow is not found (no
        existence leak), rather than 403."""
        from app.services.workflow_service import WorkflowService

        await WorkflowService().create_workflow(
            user_id="other_user_456",
            dataset_id=DATASET_ID,
            current_stage="data_loading",
            completed_stages=[],
            stage_data={},
        )

        response = await async_authorized_client.get(f"/api/v1/workflows/{DATASET_ID}")
        assert response.status_code == 404


@pytest.mark.integration
class TestUpdateWorkflow:
    @pytest.mark.asyncio
    async def test_put_updates_state_and_appends_history(
        self, async_authorized_client, setup_database
    ):
        await async_authorized_client.post(
            f"/api/v1/workflows/{DATASET_ID}", json=CREATE_PAYLOAD
        )

        response = await async_authorized_client.put(
            f"/api/v1/workflows/{DATASET_ID}",
            json={
                "current_stage": "data_preparation",
                "completed_stages": ["data_loading", "data_profiling"],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["current_stage"] == "data_preparation"
        assert data["completed_stages"] == ["data_loading", "data_profiling"]
        # Partial update preserves untouched fields
        assert data["stage_data"] == CREATE_PAYLOAD["stage_data"]

        history = await async_authorized_client.get(
            f"/api/v1/workflows/{DATASET_ID}/history"
        )
        assert history.json()["total_versions"] == 2

    @pytest.mark.asyncio
    async def test_put_missing_returns_404(
        self, async_authorized_client, setup_database
    ):
        response = await async_authorized_client.put(
            f"/api/v1/workflows/{DATASET_ID}", json={"current_stage": "deployment"}
        )
        assert response.status_code == 404


@pytest.mark.integration
class TestWorkflowHistory:
    @pytest.mark.asyncio
    async def test_history_returns_versioned_entries(
        self, async_authorized_client, setup_database
    ):
        await async_authorized_client.post(
            f"/api/v1/workflows/{DATASET_ID}", json=CREATE_PAYLOAD
        )
        for stage in ["data_preparation", "feature_engineering"]:
            await async_authorized_client.put(
                f"/api/v1/workflows/{DATASET_ID}", json={"current_stage": stage}
            )

        response = await async_authorized_client.get(
            f"/api/v1/workflows/{DATASET_ID}/history"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["dataset_id"] == DATASET_ID
        assert data["total_versions"] == 3
        versions = [entry["version"] for entry in data["entries"]]
        assert versions == [1, 2, 3]
        assert data["entries"][-1]["current_stage"] == "feature_engineering"

    @pytest.mark.asyncio
    async def test_history_missing_returns_404(
        self, async_authorized_client, setup_database
    ):
        response = await async_authorized_client.get(
            "/api/v1/workflows/no_such_dataset/history"
        )
        assert response.status_code == 404


@pytest.mark.integration
class TestRecoveryScenarios:
    """Acceptance criterion: automatic recovery after crash/refresh mid-stage."""

    @pytest.mark.asyncio
    async def test_state_survives_new_client_session(self, setup_database):
        """Simulate a crash: save state, open a brand-new client, GET restores it."""
        from httpx import AsyncClient, ASGITransport
        from asgi_lifespan import LifespanManager
        from app.main import app
        from app.auth.nextauth_auth import get_current_user_id

        async def override_get_current_user_id() -> str:
            return "test_user_123"

        app.dependency_overrides[get_current_user_id] = override_get_current_user_id
        try:
            async with LifespanManager(app):
                transport = ASGITransport(app=app)

                # Session 1: user works mid-workflow, state saved at boundary
                async with AsyncClient(
                    transport=transport, base_url="http://test"
                ) as c1:
                    await c1.post(
                        f"/api/v1/workflows/{DATASET_ID}", json=CREATE_PAYLOAD
                    )
                    await c1.put(
                        f"/api/v1/workflows/{DATASET_ID}",
                        json={
                            "current_stage": "model_training",
                            "completed_stages": [
                                "data_loading",
                                "data_profiling",
                                "data_preparation",
                                "feature_engineering",
                            ],
                        },
                    )

                # "Crash" — session 1 gone. Session 2: fresh client recovers state.
                async with AsyncClient(
                    transport=transport, base_url="http://test"
                ) as c2:
                    response = await c2.get(f"/api/v1/workflows/{DATASET_ID}")

                assert response.status_code == 200
                data = response.json()
                assert data["current_stage"] == "model_training"
                assert "feature_engineering" in data["completed_stages"]
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_history_checkpoints_allow_full_reconstruction(
        self, async_authorized_client, setup_database
    ):
        await async_authorized_client.post(
            f"/api/v1/workflows/{DATASET_ID}", json=CREATE_PAYLOAD
        )
        await async_authorized_client.put(
            f"/api/v1/workflows/{DATASET_ID}",
            json={
                "current_stage": "model_training",
                "completed_stages": ["data_loading", "data_profiling"],
                "stage_data": {"features": {"selected": ["a"]}},
                "model_id": "model_1",
            },
        )

        response = await async_authorized_client.get(
            f"/api/v1/workflows/{DATASET_ID}/history"
        )
        entries = response.json()["entries"]

        # Every checkpoint carries the complete reconstructable state
        for entry in entries:
            assert set(entry) >= {
                "version",
                "current_stage",
                "completed_stages",
                "stage_data",
                "model_id",
                "deployment_id",
                "timestamp",
            }
        assert entries[-1]["model_id"] == "model_1"
        assert entries[-1]["stage_data"] == {"features": {"selected": ["a"]}}
