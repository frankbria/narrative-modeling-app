"""#735: a request that fails after writing an S3 object deletes what nothing owns.

The middleware and the recorder with real documents; only the S3 calls are stubbed (the
LocalStack suite covers the real routes against a real bucket).
"""
import logging
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from app.middleware import upload_cleanup
from app.middleware.upload_cleanup import UnownedUploadCleanupMiddleware
from app.models.bulk_transformation import BulkTransformationJob
from app.models.dataset import DatasetMetadata
from app.models.transformation import TransformationConfig
from app.models.user_data import UserData
from app.utils.s3 import _recorded

pytestmark = pytest.mark.asyncio

KEY = "datasets/tenant-735/0b0f6c1e.csv"
URL = f"https://bucket.s3.amazonaws.com/{KEY}"
OTHER_KEY = "datasets/tenant-735/9d4e7a22.csv"


@_recorded
def put(file_content: bytes, s3_filename: str, content_type: str | None = None):
    """Stands in for the S3 put: succeeds unless the content is empty."""
    return (True, URL) if file_content else (False, None)


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(UnownedUploadCleanupMiddleware)

    @app.post("/fails-after-the-put")
    async def fails_after_the_put():
        put(b"rows", KEY)
        raise HTTPException(status_code=500, detail="schema inference failed")

    @app.post("/crashes-after-the-put")
    async def crashes_after_the_put():
        put(b"rows", KEY)
        raise RuntimeError("the database went away")

    @app.post("/fails-after-two-puts")
    async def fails_after_two_puts():
        put(b"rows", KEY)
        put(b"rows", OTHER_KEY)
        raise HTTPException(status_code=500, detail="the second write failed")

    @app.post("/succeeds")
    async def succeeds():
        put(b"rows", KEY)
        return {"status": "success"}

    @app.post("/put-itself-fails")
    async def put_itself_fails():
        put(b"", KEY)
        raise HTTPException(status_code=500, detail="Failed to upload file to S3")

    return app


@pytest.fixture
def deleted(monkeypatch) -> AsyncMock:
    delete = AsyncMock(return_value=True)
    monkeypatch.setattr(upload_cleanup.s3_service, "delete_file", delete)
    return delete


async def _post(path: str) -> int:
    transport = ASGITransport(app=_app(), raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return (await client.post(path)).status_code


@pytest.mark.parametrize("path", ["/fails-after-the-put", "/crashes-after-the-put"])
async def test_a_failed_request_deletes_the_object_it_wrote(setup_database, deleted, path, caplog):
    with caplog.at_level(logging.WARNING, logger="app.middleware.upload_cleanup"):
        assert await _post(path) == 500

    deleted.assert_awaited_once_with(KEY)
    assert KEY in caplog.text, "the log line is the only record of which object was deleted"


async def test_each_object_is_judged_on_its_own(setup_database, deleted):
    """Two puts in one failed request: the one a row names stays, the other goes."""
    await UserData(
        user_id="tenant-735", filename="d.csv", original_filename="d.csv",
        s3_url=URL, num_rows=1, num_columns=1, data_schema=[],
    ).insert()

    assert await _post("/fails-after-two-puts") == 500

    deleted.assert_awaited_once_with(OTHER_KEY)


async def test_a_successful_request_keeps_its_object(setup_database, deleted):
    assert await _post("/succeeds") == 200

    deleted.assert_not_awaited()


async def test_a_put_that_failed_wrote_nothing_to_delete(setup_database, deleted):
    assert await _post("/put-itself-fails") == 500

    deleted.assert_not_awaited()


@pytest.mark.parametrize("stored", [
    {"s3_url": URL},  # the insert landed, then the request failed
    {"s3_url": f"{URL}?X-Amz-Signature=abc"},  # /upload/ stores a presigned URL
    {"s3_url": "s3://bucket/datasets/tenant-735/later.parquet", "file_path": KEY},
    {"s3_url": "s3://bucket/datasets/tenant-735/later.parquet", "superseded_s3_urls": [URL]},
])
async def test_an_object_a_document_names_is_never_deleted(setup_database, deleted, stored):
    await UserData(
        user_id="tenant-735", filename="d.csv", original_filename="d.csv",
        num_rows=1, num_columns=1, data_schema=[], **stored,
    ).insert()

    assert await _post("/fails-after-the-put") == 500

    deleted.assert_not_awaited()


async def test_the_metadata_twin_alone_is_enough_to_keep_it(setup_database, deleted):
    """/datasets/upload writes DatasetMetadata first; if the twin write then fails, the
    object is the metadata row's file."""
    await DatasetMetadata(
        user_id="tenant-735", dataset_id="ds", filename="d.csv", original_filename="d.csv",
        file_type="csv", file_path=KEY, s3_url=URL, num_rows=1, num_columns=1,
    ).insert()

    assert await _post("/fails-after-the-put") == 500

    deleted.assert_not_awaited()


@pytest.mark.parametrize("model, field", [
    (TransformationConfig, "current_file_path"),  # written before the dataset moves
    (BulkTransformationJob, "output_file_path"),
])
async def test_a_transformation_record_naming_the_object_keeps_it(setup_database, deleted, model, field):
    await model.get_motor_collection().insert_one({"user_id": "tenant-735", field: URL})

    assert await _post("/fails-after-the-put") == 500

    deleted.assert_not_awaited()


async def test_a_presigned_url_that_percent_encodes_the_key_is_a_reference(
    setup_database, deleted, monkeypatch
):
    """/upload/ stores a presigned URL. A tenant id with a `|` or a space is encoded in
    it, so the raw key alone would miss the row and delete its file."""
    key = "datasets/auth0|tenant 735/0b0f6c1e.csv"
    monkeypatch.setattr("tests.test_middleware.test_upload_cleanup.KEY", key)
    await UserData(
        user_id="auth0|tenant 735", filename="d.csv", original_filename="d.csv",
        s3_url="https://bucket.s3.amazonaws.com/datasets/auth0%7Ctenant%20735/0b0f6c1e.csv?X-Amz-Signature=abc",
        num_rows=1, num_columns=1, data_schema=[],
    ).insert()

    assert await _post("/fails-after-the-put") == 500

    deleted.assert_not_awaited()


async def test_the_lookup_reads_only_the_keys_own_tenant(setup_database, deleted, monkeypatch):
    """Scoped to the tenant in the key so it uses the `user_id` index, not a scan of
    every tenant's rows on each failed upload."""
    seen: list[dict] = []
    real_find_one = UserData.find_one

    def recording(query, *args, **kwargs):
        seen.append(query)
        return real_find_one(query, *args, **kwargs)

    monkeypatch.setattr(UserData, "find_one", recording)

    assert await _post("/fails-after-the-put") == 500

    assert [q["user_id"] for q in seen] == ["tenant-735"]


async def test_a_key_with_no_tenant_segment_is_left(setup_database, deleted, monkeypatch, caplog):
    monkeypatch.setattr("tests.test_middleware.test_upload_cleanup.KEY", "0b0f6c1e.csv")

    with caplog.at_level(logging.ERROR, logger="app.middleware.upload_cleanup"):
        assert await _post("/fails-after-the-put") == 500

    deleted.assert_not_awaited()
    assert "may be orphaned: 0b0f6c1e.csv" in caplog.text


async def test_a_key_that_only_shares_a_prefix_is_not_a_reference(setup_database, deleted):
    await UserData(
        user_id="tenant-735", filename="d.csv", original_filename="d.csv",
        s3_url=f"{URL}.bak", num_rows=1, num_columns=1, data_schema=[],
    ).insert()

    assert await _post("/fails-after-the-put") == 500

    deleted.assert_awaited_once_with(KEY)


async def test_when_ownership_cannot_be_checked_the_object_is_left(
    setup_database, deleted, monkeypatch, caplog
):
    monkeypatch.setattr(UserData, "find_one", AsyncMock(side_effect=ConnectionError("no database")))

    with caplog.at_level(logging.ERROR, logger="app.middleware.upload_cleanup"):
        assert await _post("/fails-after-the-put") == 500

    deleted.assert_not_awaited()
    assert "may be orphaned" in caplog.text


async def test_a_delete_that_fails_does_not_change_the_response(setup_database, monkeypatch, caplog):
    monkeypatch.setattr(
        upload_cleanup.s3_service, "delete_file", AsyncMock(side_effect=RuntimeError("S3 is down"))
    )

    with caplog.at_level(logging.ERROR, logger="app.middleware.upload_cleanup"):
        assert await _post("/fails-after-the-put") == 500

    assert f"may be orphaned: {KEY}" in caplog.text


async def test_an_upload_outside_a_request_is_not_recorded():
    assert put(b"rows", KEY) == (True, URL)
