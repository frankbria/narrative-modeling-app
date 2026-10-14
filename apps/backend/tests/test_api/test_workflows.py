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

from app.models.dataset import DatasetMetadata
from app.models.user_data import UserData
from app.models.workflow import WorkflowState

DATASET_ID = "dataset_wf_api_1"
TEST_USER = "test_user_123"


@pytest.fixture(autouse=True)
async def _the_callers_dataset(setup_database):
    """A workflow is created only for a dataset its caller owns (#847)."""
    await _metadata(TEST_USER, DATASET_ID)


async def _upload(user_id: str) -> UserData:
    return await UserData(
        user_id=user_id,
        filename="visits.csv",
        original_filename="visits.csv",
        s3_url=f"s3://test-bucket/datasets/{user_id}/visits.csv",
        num_rows=2,
        num_columns=2,
        data_schema=[],
    ).insert()


async def _metadata(user_id: str, dataset_id: str) -> DatasetMetadata:
    return await DatasetMetadata(
        user_id=user_id,
        dataset_id=dataset_id,
        filename="visits.csv",
        original_filename="visits.csv",
        file_type="csv",
        file_path=f"datasets/{user_id}/{dataset_id}.csv",
        s3_url=f"s3://test-bucket/datasets/{user_id}/{dataset_id}.csv",
        file_size=10,
        num_rows=2,
        num_columns=2,
    ).insert()

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
    async def test_oversized_stage_data_is_rejected(
        self, async_authorized_client, setup_database
    ):
        """stage_data is user-controlled and snapshotted up to 50 times per
        document; unbounded payloads would brick saves at Mongo's 16MB doc
        limit, so the API rejects them at the boundary (422)."""
        from app.schemas.workflow import MAX_STAGE_DATA_BYTES

        oversized = {"blob": "x" * (MAX_STAGE_DATA_BYTES + 1)}
        response = await async_authorized_client.post(
            f"/api/v1/workflows/{DATASET_ID}",
            json={"current_stage": "data_loading", "stage_data": oversized},
        )
        assert response.status_code == 422

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
    async def test_put_with_explicit_null_preserves_model_id(
        self, async_authorized_client, setup_database
    ):
        """Documented contract: explicit null is a no-op (forward-only beta) —
        a full-state PUT including nulls must not clear stored ids."""
        await async_authorized_client.post(
            f"/api/v1/workflows/{DATASET_ID}", json=CREATE_PAYLOAD
        )
        await async_authorized_client.put(
            f"/api/v1/workflows/{DATASET_ID}", json={"model_id": "model_1"}
        )

        response = await async_authorized_client.put(
            f"/api/v1/workflows/{DATASET_ID}",
            json={"current_stage": "model_evaluation", "model_id": None},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["current_stage"] == "model_evaluation"
        assert data["model_id"] == "model_1"

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
        # latest_version lets clients detect cap truncation (kept entries vs
        # lifetime version counter)
        assert data["latest_version"] == 3
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
        from asgi_lifespan import LifespanManager
        from httpx import ASGITransport, AsyncClient

        from app.auth.nextauth_auth import get_current_user_id
        from app.main import app

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


class TestCreateNeedsADatasetTheCallerOwns:
    """A workflow is created only for a dataset the caller owns (#847).

    The route used to create a row for any id it was sent. Erasure finds a
    workflow through its dataset, so a row for an erased or invented dataset
    stayed for ever, and since #808 the frontend's PUT-then-POST fallback could
    recreate the workflow of a dataset erased in another tab.
    """

    async def test_the_owner_creates_one_for_an_upload_and_for_a_metadata_dataset(
        self, async_authorized_client, setup_database
    ):
        upload = await _upload(TEST_USER)
        metadata = await _metadata(TEST_USER, "ds_847_owned")

        for dataset_id in (str(upload.id), metadata.dataset_id):
            response = await async_authorized_client.post(
                f"/api/v1/workflows/{dataset_id}", json=CREATE_PAYLOAD
            )
            assert response.status_code == 201, response.text
            assert response.json()["dataset_id"] == dataset_id

    async def test_another_tenants_dataset_and_an_unknown_one_answer_alike(
        self, async_authorized_client, setup_database
    ):
        theirs = await _upload("someone_else")
        their_metadata = await _metadata("someone_else", "ds_847_theirs")
        unknown = "66f0c0ffee0000000000dead"

        answers = []
        for dataset_id in (str(theirs.id), their_metadata.dataset_id, unknown, "never_existed"):
            response = await async_authorized_client.post(
                f"/api/v1/workflows/{dataset_id}", json=CREATE_PAYLOAD
            )
            assert response.status_code == 404, response.text
            answers.append(response.json()["detail"].replace(dataset_id, "<id>"))

        assert len(set(answers)) == 1, "a foreign id must not be told apart from an unknown one"
        assert await WorkflowState.find_all().count() == 0
