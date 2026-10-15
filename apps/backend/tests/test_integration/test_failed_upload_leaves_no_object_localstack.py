"""#735: every upload route writes the S3 object before the document that owns it.

When anything after the put failed (schema inference, validation, the insert), the
request answered an error and refunded the quota, but the object stayed in the bucket
with nothing pointing at it. Erasure walks documents, so it could never reach it.
Only a real bucket can show this: the object either is there afterwards or is not.
"""
import io
from unittest.mock import patch

import pytest

from tests.test_integration import (
    test_transformation_first_apply_localstack as first_apply,
)

client = first_apply.client
real_s3_env = first_apply.real_s3_env
USER = first_apply.USER

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

CSV = b"id,name,score\n1,alice,10\n2,bob,20\n3,carol,30\n"


def _objects(s3_client, bucket: str) -> set[str]:
    """Every object this tenant has in the bucket."""
    listed = s3_client.list_objects_v2(Bucket=bucket, Prefix=f"datasets/{USER}/")
    return {o["Key"] for o in listed.get("Contents", [])}


async def _status(request) -> int:
    """The response status; an exception the app re-raises after answering is a 500."""
    try:
        return (await request).status_code
    except RuntimeError:
        return 500


def _file(content: bytes = CSV, name: str = "people.csv") -> dict:
    return {"file": (name, io.BytesIO(content), "text/csv")}


async def test_secure_upload_whose_insert_fails_leaves_no_object(client, s3_client, real_s3_env):
    from app.models.user_data import UserData

    with patch.object(UserData, "insert", side_effect=RuntimeError("the database went away")):
        status = await _status(client.post("/api/v1/upload/secure", files=_file()))

    assert status == 500
    assert _objects(s3_client, real_s3_env) == set()


async def test_pii_confirmed_upload_that_fails_after_the_put_leaves_no_object(
    client, s3_client, real_s3_env
):
    with patch("app.api.routes.secure_upload.infer_schema", side_effect=RuntimeError("bad frame")):
        status = await _status(
            client.post("/api/v1/upload/confirm-pii-upload?mask_pii=false", files=_file())
        )

    assert status == 500
    assert _objects(s3_client, real_s3_env) == set()


async def test_chunked_complete_that_fails_after_the_put_leaves_no_object(
    client, s3_client, real_s3_env
):
    init = await client.post(
        "/api/v1/upload/chunked/init", data={"filename": "people.csv", "file_size": str(len(CSV))}
    )
    assert init.status_code == 200, init.text
    session_id = init.json()["session_id"]
    chunk = await client.post(
        f"/api/v1/upload/chunked/{session_id}/chunk/0",
        files={"file": ("chunk0", io.BytesIO(CSV), "application/octet-stream")},
    )
    assert chunk.status_code == 200, chunk.text

    with patch("app.api.routes.secure_upload.infer_schema", side_effect=RuntimeError("bad frame")):
        status = await _status(client.post(f"/api/v1/upload/chunked/{session_id}/complete"))

    assert status == 500
    assert _objects(s3_client, real_s3_env) == set()


async def test_a_dataset_upload_that_cannot_be_read_is_never_stored(
    client, s3_client, real_s3_env
):
    """#899: /datasets/upload parses before the put, so a file it cannot read is the
    caller's 400 and never reaches the bucket: not written and then cleaned up."""
    from unittest.mock import MagicMock

    from app.api.routes import datasets

    unparseable = b"\x00\xff\x00\xff" * 64
    put = MagicMock(wraps=datasets.upload_file_to_s3)

    with patch("app.api.routes.datasets.upload_file_to_s3", put):
        upload = await client.post("/api/v1/datasets/upload", files=_file(unparseable))

    assert upload.status_code == 400, upload.text
    assert upload.json()["detail"].startswith("Could not read the file as .csv")
    put.assert_not_called()
    assert _objects(s3_client, real_s3_env) == set()


async def test_a_successful_upload_keeps_its_object(client, s3_client, real_s3_env):
    from app.models.user_data import UserData

    upload = await client.post("/api/v1/upload/secure", files=_file())

    assert upload.status_code == 200, upload.text
    row = await UserData.get(upload.json()["file_id"])
    assert len(_objects(s3_client, real_s3_env)) == 1
    assert next(iter(_objects(s3_client, real_s3_env))) in row.s3_url


async def test_an_object_a_document_points_at_survives_a_failed_request(
    client, s3_client, real_s3_env
):
    """The insert lands and the request fails afterwards: the row is the only record of
    the object, so deleting it would lose the customer's file."""
    from app.models.user_data import UserData

    real_insert = UserData.insert

    async def insert_then_fail(self, *args, **kwargs):
        await real_insert(self, *args, **kwargs)
        raise RuntimeError("the reply was lost")

    with patch.object(UserData, "insert", insert_then_fail):
        status = await _status(client.post("/api/v1/upload/secure", files=_file()))

    assert status == 500
    row = await UserData.find_one(UserData.user_id == USER)
    assert row is not None, "precondition: the insert landed"
    assert len(_objects(s3_client, real_s3_env)) == 1


# #898: the apply routes write the new file first and report a later failure in a 200
# body, which the status-based cleanup above never saw.

MESSY = b"id,color,score\n1, red ,10\n2,blue,\n2,blue,\n4,green,\n5,red,45\n6,red,45\n"
T = "/api/v1/transformations"
# The move is the last write before the apply succeeds (#1060).
STEP = "app.services.transformation_service.record_new_file"


def _transformed(s3_client, bucket: str) -> set[str]:
    """Every transformed file this tenant has in the bucket."""
    listed = s3_client.list_objects_v2(Bucket=bucket, Prefix=f"transformed/{USER}/")
    return {o["Key"] for o in listed.get("Contents", [])}


async def _dataset(client) -> tuple[str, str]:
    """A dataset with duplicates and gaps: its dataset id, and its upload record's id."""
    from app.models.user_data import UserData

    upload = await client.post("/api/v1/datasets/upload", files=_file(MESSY, "messy.csv"))
    assert upload.status_code in (200, 201), upload.text
    twin = await UserData.find_one(UserData.user_id == USER, UserData.original_filename == "messy.csv")
    return upload.json()["dataset_id"], str(twin.id)


def _the_database_goes_away(what: str):
    from unittest.mock import AsyncMock

    return patch(what, new_callable=AsyncMock, side_effect=RuntimeError("the database went away"))


@pytest.mark.parametrize("path, body", [
    ("/apply", {"transformation_type": "remove_duplicates", "parameters": {}}),
    ("/pipeline/apply", {"transformations": [{"type": "trim_whitespace", "parameters": {}},
                                             {"type": "remove_duplicates", "parameters": {}}]}),
], ids=["apply", "pipeline"])
async def test_a_transformation_that_fails_after_the_put_leaves_no_object(client, s3_client, real_s3_env, path, body):
    dataset_id, _ = await _dataset(client)

    with _the_database_goes_away(STEP):
        response = await client.post(f"{T}{path}", json={"dataset_id": dataset_id, **body})

    assert response.status_code == 200 and response.json()["success"] is False, response.text
    assert _transformed(s3_client, real_s3_env) == set()


async def test_a_transformation_that_works_keeps_its_file(client, s3_client, real_s3_env):
    from app.models.dataset import DatasetMetadata

    dataset_id, _ = await _dataset(client)

    response = await client.post(f"{T}/apply", json={
        "dataset_id": dataset_id, "transformation_type": "remove_duplicates", "parameters": {}})

    assert response.json()["success"] is True, response.text
    kept = _transformed(s3_client, real_s3_env)
    assert len(kept) == 1
    assert (await DatasetMetadata.find_one(DatasetMetadata.dataset_id == dataset_id)).s3_url.endswith(kept.pop())


@pytest.mark.parametrize("route", ["apply-fix", "batch-fix"])
async def test_a_data_issue_fix_that_fails_after_the_put_leaves_no_object(client, s3_client, real_s3_env, route):
    _, upload_id = await _dataset(client)
    detected = await client.post("/api/v1/data-issues/detect", json={
        "dataset_id": upload_id, "options": {"include_ai_analysis": False}})
    assert detected.status_code == 200, detected.text
    fixable = [i["issue_id"] for i in detected.json()["issues"] if i["suggested_fixes"]]
    assert fixable, "precondition: the file has an issue with a suggested fix"
    body = {"issue_id": fixable[0]} if route == "apply-fix" else {"issue_ids": fixable}

    with _the_database_goes_away(STEP):
        response = await client.post(f"/api/v1/data-issues/{route}", json={
            "dataset_id": upload_id, "preview_mode": False, **body})

    assert response.status_code == 200 and response.json()["success"] is False, response.text
    assert _transformed(s3_client, real_s3_env) == set()


async def test_a_bulk_job_that_fails_after_the_put_leaves_no_object(client, s3_client, real_s3_env):
    import asyncio

    dataset_id, _ = await _dataset(client)
    base = f"{T}/datasets/{dataset_id}"

    with _the_database_goes_away(STEP):
        job = await client.post(f"{base}/bulk-apply", json={
            "selected_columns": ["score"], "transformation_type": "fill_missing",
            "global_parameters": {"method": "mean"}})
        assert job.status_code == 200, job.text
        for _ in range(200):
            status = (await client.get(f"{base}/bulk-jobs/{job.json()['job_id']}")).json()["status"]
            if status not in ("pending", "running"):
                break
            await asyncio.sleep(0.05)

    assert status == "failed"
    assert _transformed(s3_client, real_s3_env) == set()


async def test_a_move_that_fails_records_no_step(client, s3_client, real_s3_env):
    """#1060: the steps used to be recorded before the move, so a failed move left a
    history naming a file the dataset was never on, and that file was kept as owned."""
    from app.models.transformation import TransformationConfig

    dataset_id, _ = await _dataset(client)

    with _the_database_goes_away(STEP):
        response = await client.post(f"{T}/apply", json={
            "dataset_id": dataset_id, "transformation_type": "remove_duplicates", "parameters": {}})

    assert response.json()["success"] is False, response.text
    configs = await TransformationConfig.find(TransformationConfig.user_id == USER).to_list()
    # The history keeps the file it started on: the upload, not the file never moved to.
    assert configs and all(not c.transformation_steps and "/transformed/" not in (c.current_file_path or "") for c in configs)
    assert _transformed(s3_client, real_s3_env) == set()


async def test_steps_that_fail_after_the_move_are_reported_and_close_the_history(client, s3_client, real_s3_env):
    """The dataset is on the new file, so the apply succeeded; it says the change cannot
    be undone, and nothing earlier can be restored over it."""
    from app.models.dataset import DatasetMetadata

    dataset_id, _ = await _dataset(client)
    first = await client.post(f"{T}/apply", json={
        "dataset_id": dataset_id, "transformation_type": "trim_whitespace", "parameters": {}})
    assert first.json()["success"] is True, first.text

    with _the_database_goes_away(
        "app.services.transformation_service.TransformationService.add_transformation_step"
    ):
        response = await client.post(f"{T}/apply", json={
            "dataset_id": dataset_id, "transformation_type": "remove_duplicates", "parameters": {}})

    body = response.json()
    assert body["success"] is True, response.text
    assert any("cannot be undone" in w for w in body["warnings"])
    moved = await DatasetMetadata.find_one(DatasetMetadata.dataset_id == dataset_id)
    assert moved.s3_url.endswith(max(_transformed(s3_client, real_s3_env)))
    undo = await client.post(f"{T}/datasets/{dataset_id}/history/undo")
    assert undo.status_code == 400, undo.text
