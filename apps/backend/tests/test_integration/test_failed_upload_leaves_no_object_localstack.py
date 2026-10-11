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


async def test_a_dataset_upload_that_cannot_be_processed_leaves_no_object(
    client, s3_client, real_s3_env
):
    """No fault injected: /datasets/upload stores the file, then parses it."""
    unparseable = b"\x00\xff\x00\xff" * 64

    upload = await client.post("/api/v1/datasets/upload", files=_file(unparseable))

    assert upload.status_code >= 400, upload.text
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
