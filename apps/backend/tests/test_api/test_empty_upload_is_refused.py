"""A file with a header and no data rows is refused at every dataset-creating route (#1062).

It used to be stored as a 0-row dataset that every later stage choked on (training
failed, the explore page showed empty profiles). Each route is driven for real:
a real Mongo document check, the exact status and sentence, the `uploads` unit back,
and no S3 put.

The refusal has to come before the S3 put (a 4xx would delete an unowned object, but
never writing one is the stronger guarantee), so the S3 stand-ins record their calls.
The routes this file does not cover create no empty dataset: the onboarding sample
loader reads files shipped in the image, and feature-apply derives from an existing one.
"""

import io

import pandas as pd
import pytest

from app.api.routes import datasets as datasets_module
from app.api.routes import secure_upload as secure_upload_module
from app.billing import metering
from app.models.dataset import DatasetMetadata
from app.models.user_data import UserData
from app.services.security.upload_handler import ChunkedUploadHandler

pytestmark = pytest.mark.asyncio

TEST_USER = "test_user_123"
HEADER_ONLY = b"id,name,score\n"
SENTENCE = "no data rows"


@pytest.fixture
def s3_puts(monkeypatch, tmp_path):
    """Replace the S3 writer in every route module, recording the keys it is given."""
    puts: list[str] = []

    def fake_upload(file_content, s3_filename, content_type=None):
        puts.append(s3_filename)
        return True, f"s3://test-bucket/{s3_filename}"

    for module in (datasets_module, secure_upload_module):
        monkeypatch.setattr(module, "upload_file_to_s3", fake_upload)
    monkeypatch.setenv("AWS_S3_BUCKET", "test-bucket")
    monkeypatch.setattr(
        secure_upload_module,
        "upload_handler",
        ChunkedUploadHandler(temp_dir=str(tmp_path / "uploads")),
    )
    return puts


async def _chunked_complete(client, filename: str, content: bytes):
    init = await client.post(
        "/api/v1/upload/chunked/init",
        data={"filename": filename, "file_size": str(len(content))},
    )
    session_id = init.json()["session_id"]
    await client.post(
        f"/api/v1/upload/chunked/{session_id}/chunk/0",
        files={"file": ("chunk0", io.BytesIO(content), "application/octet-stream")},
    )
    return await client.post(f"/api/v1/upload/chunked/{session_id}/complete")


async def _multipart(client, route: str, filename: str, content: bytes, mime: str):
    return await client.post(route, files={"file": (filename, content, mime)})


_MULTIPART_ROUTES = [
    "/api/v1/upload/secure",
    "/api/v1/upload/confirm-pii-upload",
    "/api/v1/datasets/upload",
]


async def _nothing_was_created() -> None:
    assert await UserData.find().count() == 0
    assert await DatasetMetadata.find().count() == 0


class TestAHeaderOnlyFileIsRefused:
    @pytest.mark.parametrize("route", _MULTIPART_ROUTES)
    async def test_header_only_csv_is_a_400_that_costs_nothing(
        self, async_authorized_client, setup_database, s3_puts, route
    ):
        response = await _multipart(
            async_authorized_client, route, "empty.csv", HEADER_ONLY, "text/csv"
        )

        assert response.status_code == 400, f"{route}: {response.text}"
        assert SENTENCE in response.json()["detail"]
        assert await metering.usage_for(TEST_USER, "uploads") == 0, route
        assert s3_puts == [], route
        await _nothing_was_created()

    async def test_header_only_csv_on_chunked_complete(
        self, async_authorized_client, setup_database, s3_puts
    ):
        response = await _chunked_complete(async_authorized_client, "empty.csv", HEADER_ONLY)

        assert response.status_code == 400, response.text
        assert SENTENCE in response.json()["detail"]
        assert await metering.usage_for(TEST_USER, "uploads") == 0
        assert s3_puts == []
        await _nothing_was_created()

    @pytest.mark.parametrize(
        "route", ["/api/v1/upload/secure", "/api/v1/datasets/upload"]
    )
    async def test_header_only_workbook_is_refused_too(
        self, async_authorized_client, setup_database, s3_puts, route
    ):
        buffer = io.BytesIO()
        pd.DataFrame(columns=["id", "name"]).to_excel(buffer, index=False)

        response = await _multipart(
            async_authorized_client,
            route,
            "empty.xlsx",
            buffer.getvalue(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        assert response.status_code == 400, f"{route}: {response.text}"
        assert SENTENCE in response.json()["detail"]
        assert await metering.usage_for(TEST_USER, "uploads") == 0
        assert s3_puts == []


class TestAFileWithRowsIsUnchanged:
    @pytest.mark.parametrize("route", _MULTIPART_ROUTES)
    async def test_one_row_is_stored_and_charged(
        self, async_authorized_client, setup_database, s3_puts, route
    ):
        response = await _multipart(
            async_authorized_client, route, "one.csv", HEADER_ONLY + b"1,alice,10\n", "text/csv"
        )

        assert response.status_code == 200, f"{route}: {response.text}"
        assert await metering.usage_for(TEST_USER, "uploads") == 1
        assert len(s3_puts) == 1
