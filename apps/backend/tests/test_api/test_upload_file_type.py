"""The legacy upload route must set UserData.file_type (issue #79 demo finding).

Model training routes on user_data.file_type ("csv"/"xls"/"xlsx"/"parquet");
the legacy /api/v1/upload/ route created UserData without it, so every model
trained from a legacy upload failed with "Unsupported file type: None".
"""

import io
from unittest.mock import patch

import pytest

from app.models.user_data import UserData

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_upload_sets_file_type_from_extension(async_authorized_client):
    csv_content = b"a,b\n1,2\n3,4\n"
    files = {"file": ("typed_test.csv", io.BytesIO(csv_content), "text/csv")}

    with patch(
        "app.api.routes.upload.upload_file_to_s3",
        return_value=(True, "s3://bucket/typed_test.csv"),
    ):
        response = await async_authorized_client.post("/api/v1/upload/", files=files)

    assert response.status_code == 200
    doc_id = response.json()["id"]
    user_data = await UserData.get(doc_id)
    assert user_data is not None
    assert user_data.file_type == "csv"
