"""#940: the preview and export readers go by the stored type, and by the bytes when
there is none, never by the upload's filename first.

Two rows the filename misled: a transformed dataset (Parquet bytes, the upload's .csv
name), whose preview fell back to the stored rows, and a masked workbook stored before
#937 (CSV bytes, no type, an .xlsx name), which both readers tried to open as Excel.
Real documents; only the S3 transfer is stubbed.
"""

import io
from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest

from app.models.user_data import UserData

pytestmark = pytest.mark.asyncio

TEST_USER = "test_user_123"  # the identity async_authorized_client authenticates as
FRAME = pd.DataFrame({"id": [1, 2, 3], "label": ["a", "b", "c"]})


def _parquet() -> bytes:
    held = io.BytesIO()
    FRAME.to_parquet(held, index=False)
    return held.getvalue()


ROWS = [
    # stored type, filename, the bytes the object holds
    ("parquet", "visits.csv", _parquet()),  # a dataset a transformation moved
    (None, "visits.xlsx", FRAME.to_csv(index=False).encode()),  # masked before #937
]


async def _row(file_type: str | None, filename: str) -> UserData:
    doc = await UserData(
        user_id=TEST_USER, filename=filename, original_filename=filename,
        s3_url=f"https://test-bucket.s3.amazonaws.com/datasets/{TEST_USER}/stored", file_path=f"datasets/{TEST_USER}/stored",
        num_rows=3, num_columns=2, data_schema=[], file_type=file_type or "csv", is_processed=True,
        columns=["id", "label"], row_count=3,
    ).insert()
    if file_type is None:  # how a row written before #937 is stored
        await UserData.get_motor_collection().update_one({"_id": doc.id}, {"$unset": {"file_type": ""}})
    return doc


@pytest.fixture(autouse=True)
def _clear_preview_cache():
    from app.api.routes.data_processing import _preview_cache

    _preview_cache.clear()
    yield
    _preview_cache.clear()


@pytest.mark.parametrize("file_type, filename, stored", ROWS, ids=["parquet under .csv", "no type, csv under .xlsx"])
async def test_the_preview_reads_the_file(setup_database, async_authorized_client, file_type, filename, stored):
    doc = await _row(file_type, filename)

    with patch("app.services.s3_service.s3_service.download_file_bytes", AsyncMock(return_value=stored)):
        response = await async_authorized_client.get(f"/api/v1/data/{doc.id}/preview?rows=5")

    assert response.status_code == 200, response.text
    body = response.json()
    assert "warning" not in body, "read from the file, not the stored rows"
    assert [row["label"] for row in body["data"]] == ["a", "b", "c"]


@pytest.mark.parametrize("file_type, filename, stored", ROWS, ids=["parquet under .csv", "no type, csv under .xlsx"])
async def test_the_export_reads_the_file(setup_database, async_authorized_client, file_type, filename, stored):
    doc = await _row(file_type, filename)

    with patch("app.services.s3_service.s3_service.download_file_bytes", AsyncMock(return_value=stored)), \
         patch("app.services.s3_service.s3_service.upload_file_obj", new_callable=AsyncMock) as upload, \
         patch("app.services.s3_service.s3_service.generate_presigned_url", return_value="https://signed"):
        response = await async_authorized_client.post(f"/api/v1/data/{doc.id}/export?format=csv")

    assert response.status_code == 200, response.text
    exported = pd.read_csv(upload.await_args.args[0])
    assert exported["label"].tolist() == ["a", "b", "c"]
