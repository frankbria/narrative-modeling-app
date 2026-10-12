"""#858: a transformation on a JSON or Excel dataset reads the dataset, not junk.

The transformation reader passed no file type and tried CSV first. `read_csv` does not
fail on JSON: it returns one junk column per comma, and the apply then wrote that frame
back over the dataset on both twins. An Excel upload could not be transformed at all.
Real uploads, real S3 (LocalStack), the real routes.
"""
import io

import pandas as pd
import pytest

from tests.test_integration import (
    test_transformation_first_apply_localstack as first_apply,
)
from tests.test_integration import (
    test_transformation_history_localstack as history,
)

client = first_apply.client
real_s3_env = first_apply.real_s3_env
USER = first_apply.USER

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

# No PII-shaped columns, so /upload/secure stores the file instead of asking for consent.
ROWS = pd.DataFrame({"id": [1, 2, 3, 3], "color": [" red ", "blue", "green", "green"], "score": [10, 20, 30, 30]})
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


async def _dedupe(client, dataset_id: str) -> None:
    applied = await client.post(
        "/api/v1/transformations/apply",
        json={"dataset_id": dataset_id, "transformation_type": "remove_duplicates", "parameters": {}},
    )
    assert applied.status_code == 200 and applied.json()["success"] is True, applied.text


async def _current_frame(user_data_filter) -> pd.DataFrame:
    """The dataset's current file, read the way a training stage reads it."""
    from app.models.user_data import UserData

    upload = await UserData.find_one(user_data_filter)
    return await history._read_as_a_training_stage_does(upload)


async def test_a_json_dataset_keeps_its_columns_through_a_transformation(client, real_s3_env):
    from app.models.dataset import DatasetMetadata
    from app.models.user_data import UserData

    body = ROWS.to_json(orient="records").encode()
    upload = await client.post(
        "/api/v1/datasets/upload", files={"file": ("colors.json", io.BytesIO(body), "application/json")}
    )
    assert upload.status_code in (200, 201), upload.text
    dataset_id = upload.json()["dataset_id"]

    await _dedupe(client, dataset_id)

    meta = await DatasetMetadata.find_one(DatasetMetadata.dataset_id == dataset_id)
    frame = await _current_frame({"user_id": USER, "s3_url": meta.s3_url})
    assert list(frame.columns) == ["id", "color", "score"]
    assert list(frame["id"]) == [1, 2, 3], "the duplicate row is gone and nothing else changed"
    assert meta.file_type == "parquet" and await UserData.find({"user_id": USER, "file_type": "parquet"}).count() == 1


async def test_an_excel_upload_from_the_upload_page_can_be_transformed(client, real_s3_env):
    from bson import ObjectId

    workbook = io.BytesIO()
    ROWS.to_excel(workbook, index=False)
    upload = await client.post(
        "/api/v1/upload/secure", files={"file": ("colors.xlsx", io.BytesIO(workbook.getvalue()), XLSX)}
    )
    assert upload.status_code == 200, upload.text
    upload_id = upload.json()["file_id"]

    preview = await client.post("/api/v1/transformations/preview", json={
        "dataset_id": upload_id,
        "transformation_steps": [{"transformation_type": "trim_whitespace", "parameters": {"columns": ["color"]}}],
    })
    assert preview.status_code == 200 and preview.json()["success"] is True, preview.text

    await _dedupe(client, upload_id)

    frame = await _current_frame({"_id": ObjectId(upload_id)})
    assert list(frame.columns) == ["id", "color", "score"] and list(frame["id"]) == [1, 2, 3]
