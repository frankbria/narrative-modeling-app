"""A PII-confirmed upload is stored with the type of the bytes it wrote (#937).

`/upload/confirm-pii-upload` stored no `file_type`, so training refused the dataset
(`Unsupported file type: None`), and a masked workbook was CSV under an `.xlsx` key.
The real route runs against the real test database; only the S3 write is substituted,
and it keeps the bytes so each reader is given exactly what was stored.
"""

import io

import pandas as pd
import pytest
from bson import ObjectId

from app.api.routes import secure_upload
from app.api.routes.model_training import _parse_dataset
from app.models.user_data import UserData
from app.services.data_processing.data_processor import DataProcessor
from app.services.dataset_link import file_type_of

pytestmark = pytest.mark.asyncio

PEOPLE = pd.DataFrame({"id": [1, 2], "email": ["alice@example.com", "bob@example.com"]})
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _csv() -> bytes:
    return PEOPLE.to_csv(index=False).encode()


def _xlsx() -> bytes:
    buffer = io.BytesIO()
    PEOPLE.to_excel(buffer, index=False)
    return buffer.getvalue()


@pytest.fixture
def stored(monkeypatch) -> dict[str, bytes]:
    """The objects the route wrote, by key."""
    objects: dict[str, bytes] = {}

    def fake_upload(content, key, content_type=None):
        objects[key] = content
        return True, f"s3://test-bucket/{key}"

    async def no_summary(*args, **kwargs):
        return None

    monkeypatch.setattr(secure_upload, "upload_file_to_s3", fake_upload)
    monkeypatch.setattr(secure_upload, "generate_ai_summary_safe", no_summary)
    return objects


@pytest.mark.parametrize(
    "name,body,content_type,mask,file_type",
    [
        ("people.csv", _csv, "text/csv", "false", "csv"),
        ("people.csv", _csv, "text/csv", "true", "csv"),
        ("people.xlsx", _xlsx, XLSX, "false", "xlsx"),
        ("people.xlsx", _xlsx, XLSX, "true", "csv"),
    ],
)
async def test_the_stored_type_is_the_type_of_the_bytes_written(
    async_authorized_client, stored, name, body, content_type, mask, file_type
):
    response = await async_authorized_client.post(
        "/api/v1/upload/confirm-pii-upload",
        files={"file": (name, io.BytesIO(body()), content_type)},
        params={"mask_pii": mask},
    )

    assert response.status_code == 200, response.text
    ((key, written),) = stored.items()
    row = await UserData.get(ObjectId(response.json()["file_id"]))
    assert row.file_type == file_type
    assert key.endswith(f".{file_type}")
    # Training's reader, then the explore page's, on the bytes that were stored.
    assert list(_parse_dataset(written, row.file_type).columns) == ["id", "email"]
    processed = await DataProcessor().process_bytes(written, row.original_filename, file_type=row.file_type)
    assert len(processed.dataframe) == 2


@pytest.mark.parametrize("body", [_csv, _xlsx])
async def test_training_reads_a_row_with_no_declared_type_by_its_bytes(body):
    """Rows this route stored before it wrote a type."""
    assert list(_parse_dataset(body(), None).columns) == ["id", "email"]


async def test_a_masked_object_is_csv_whatever_its_name_says():
    """Until #937 a masked workbook was CSV under the upload's own extension."""
    assert file_type_of("s3://bucket/datasets/u/masked_0f1e.xlsx?X-Amz-Signature=1") == "csv"
    assert file_type_of("s3://bucket/datasets/u/0f1e.xlsx") == "xlsx"
