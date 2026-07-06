"""API-layer tests for the erasure endpoints (issue #259).

Exercises POST /datasets/{id}/erase and POST /users/me/erase through the HTTP
stack: response shape, the erasure_id that correlates to the append-only audit
log, and the ownership no-op for a dataset the caller does not own. The
authorized client authenticates as ``test_user_123``.
"""

import pytest

from app.models.erasure_audit import ErasureAuditLog
from app.services.dataset_service import DatasetService
from app.services.erasure_service import dataset_erasure_service

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

AUTH_USER = "test_user_123"


@pytest.fixture(autouse=True)
def _hermetic_s3():
    """Keep erase off real AWS (create_dataset/erase would otherwise hit S3)."""
    svcs = [dataset_erasure_service.s3_service, dataset_erasure_service.model_storage.s3_service]
    saved = [s.is_mock_mode for s in svcs]
    for s in svcs:
        s.is_mock_mode = True
    try:
        yield
    finally:
        for s, was in zip(svcs, saved, strict=True):
            s.is_mock_mode = was


async def _make_dataset(owner: str, dataset_id: str):
    await DatasetService().create_dataset(
        user_id=owner, dataset_id=dataset_id, filename="e.csv", original_filename="e.csv",
        file_type="csv", file_path=f"datasets/{owner}/{dataset_id}_e.csv",
        s3_url=f"s3://b/datasets/{owner}/{dataset_id}_e.csv", num_rows=5, num_columns=1,
        columns=["a"], data_schema=[],
    )


async def test_erase_dataset_endpoint_returns_manifest_and_correlatable_audit_id(
    async_authorized_client, setup_database
):
    await _make_dataset(AUTH_USER, "erase_api_1")

    resp = await async_authorized_client.post(
        "/api/v1/datasets/erase_api_1/erase", json={"reason": "gdpr_request"}
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert body["manifest"]["documents_deleted"].get("dataset_metadata") == 1
    # The returned erasure_id MUST identify the persisted audit entry.
    assert body["erasure_id"]
    audit = await ErasureAuditLog.find(ErasureAuditLog.erasure_id == body["erasure_id"]).to_list()
    assert len(audit) == 1
    assert audit[0].reason == "gdpr_request"
    assert audit[0].subject_user_id == AUTH_USER
    # Dataset is actually gone.
    assert (await async_authorized_client.get("/api/v1/datasets/erase_api_1")).status_code == 404


async def test_erase_dataset_endpoint_foreign_is_noop_and_writes_no_audit(
    async_authorized_client, setup_database
):
    await _make_dataset("someone_else", "erase_api_foreign")

    resp = await async_authorized_client.post("/api/v1/datasets/erase_api_foreign/erase")

    assert resp.status_code == 200
    body = resp.json()
    assert body["manifest"]["idempotent_noop"] is True
    assert body["erasure_id"] is None  # no erasure -> no audit id
    assert await ErasureAuditLog.find().count() == 0  # attacker can't spam the log
    # Victim's dataset survives.
    ds = await DatasetService().get_dataset("erase_api_foreign", check_ownership=False)
    assert ds is not None


async def test_erase_current_user_endpoint_sweeps_owned_data(
    async_authorized_client, setup_database
):
    await _make_dataset(AUTH_USER, "erase_api_me1")
    await _make_dataset(AUTH_USER, "erase_api_me2")

    resp = await async_authorized_client.post("/api/v1/users/me/erase", json={"reason": "account"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["manifest"]["target_type"] == "user"
    assert body["erasure_id"]
    assert (await async_authorized_client.get("/api/v1/datasets/erase_api_me1")).status_code == 404
    assert (await async_authorized_client.get("/api/v1/datasets/erase_api_me2")).status_code == 404
