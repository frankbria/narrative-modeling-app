"""Every endpoint that looks a UserData up by an id from the request must find a real
document (#465).

`UserData.id` is a `PydanticObjectId`. Comparing it to the raw string from a path or body
(`UserData.id == file_id`, or `{"_id": request.dataset_id}` in a raw dict) builds
`{"_id": "<string>"}`, which can never match — so ten endpoints answered a permanent 404
(or, in `transformations.py`, a 200 `{success: false}` / 500 wrapped around that 404),
and passed CI because their tests patched `find_one` to return a mock. These tests seed
real documents and never patch the lookup; only S3 is stubbed.
"""
import os
import shutil
import tempfile
from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest
from bson import ObjectId

from app.models.user_data import UserData

pytestmark = pytest.mark.asyncio

TEST_USER = "test_user_123"  # what async_authorized_client authenticates as
MALFORMED = "not-an-object-id"

_QUALITY = {
    "overall_quality_score": 0.86, "score_0_100": 86.0,
    "dimension_scores": {"completeness": 0.9, "validity": 0.8},
    "component_scores": {"completeness": 90.0, "validity": 80.0, "consistency": 95.0,
                         "uniqueness": 100.0, "accuracy": 80.0},
    "recommendations": [], "actionable_recommendations": [], "critical_issues": [], "warnings": [],
}


def _frame() -> pd.DataFrame:
    return pd.DataFrame({
        "id": [1, 2, 3, 4, 5], "name": [" a", "b ", "c", "d", "e"], "age": [25, 30, None, 40, 45],
        "email": [f"{c}@x.test" for c in "abcde"],
    })


async def seed(user_id: str = TEST_USER) -> UserData:
    url = f"https://test-bucket.s3.amazonaws.com/datasets/{user_id}/t.parquet"
    doc = UserData(
        user_id=user_id, filename="t.csv", original_filename="t.csv", s3_url=url, file_path=url,
        num_rows=5, num_columns=4, data_schema=[], file_type="csv", is_processed=True,
        schema={"row_count": 5, "column_count": 4, "columns": []},
        statistics={"columns": {"age": {"mean": 35.0}}}, quality_report=_QUALITY,
    )
    await doc.insert()
    return doc


@pytest.fixture
def s3_stubbed():
    """Only storage is stubbed — the document lookup is the thing under test."""
    frame = _frame()
    fd, path = tempfile.mkstemp(suffix=".parquet")
    os.close(fd)
    frame.to_parquet(path)

    def download(_url):  # data_utils reads and unlinks, so hand out a fresh copy each time
        fd2, copy = tempfile.mkstemp(suffix=".parquet")
        os.close(fd2)
        shutil.copy2(path, copy)
        return copy

    uploaded = (True, "https://test-bucket.s3.amazonaws.com/transformed/x.parquet")
    with patch("app.services.s3_service.download_file_from_s3", side_effect=download), \
         patch("app.utils.s3.upload_file_to_s3", return_value=uploaded), \
         patch("app.services.transformation_engine.data_utils.upload_file_to_s3", return_value=uploaded), \
         patch("app.services.s3_service.s3_service.download_file_bytes", new_callable=AsyncMock,
               return_value=frame.to_csv(index=False).encode()), \
         patch("app.services.s3_service.s3_service.get_file_size", new_callable=AsyncMock, return_value=10), \
         patch("app.services.s3_service.s3_service.upload_file_obj", new_callable=AsyncMock), \
         patch("app.services.s3_service.s3_service.generate_presigned_url", return_value="https://x"):
        yield
    os.unlink(path)


def _pipeline(dataset_id: str) -> dict:
    return {"dataset_id": dataset_id,
            "transformations": [{"type": "trim_whitespace", "parameters": {"columns": ["name"]}}]}


def _validate(dataset_id: str) -> dict:
    return {"dataset_id": dataset_id,
            "transformations": [{"type": "remove_duplicates", "parameters": {"columns": ["id"], "keep": "first"}}]}


#: (label, method, path template, body builder). `{id}` is the document id.
ENDPOINTS = [
    ("data/schema", "GET", "/api/v1/data/{id}/schema", None),
    ("data/statistics", "GET", "/api/v1/data/{id}/statistics", None),
    ("data/quality", "GET", "/api/v1/data/{id}/quality", None),
    ("data/quality-report", "GET", "/api/v1/data/{id}/quality-report", None),
    ("data/preview", "GET", "/api/v1/data/{id}/preview?rows=3", None),
    ("data/export", "POST", "/api/v1/data/{id}/export?format=csv", None),
    ("transformations/pipeline", "POST", "/api/v1/transformations/pipeline/apply", _pipeline),
    ("transformations/validate", "POST", "/api/v1/transformations/validate", _validate),
    ("transformations/auto-clean", "POST", "/api/v1/transformations/auto-clean", lambda i: {"dataset_id": i}),
    ("transformations/suggestions", "GET", "/api/v1/transformations/suggestions/{id}", None),
]
IDS = [e[0] for e in ENDPOINTS]


async def _call(client, method, path, body, doc_id):
    url = path.replace("{id}", doc_id)
    json = body(doc_id) if body else None
    return await client.request(method, url, json=json)


class TestObjectIdLookups:
    @pytest.mark.parametrize("label, method, path, body", ENDPOINTS, ids=IDS)
    async def test_finds_a_real_document(self, async_authorized_client, setup_database, s3_stubbed,
                                         label, method, path, body):
        doc = await seed()
        response = await _call(async_authorized_client, method, path, body, str(doc.id))
        assert response.status_code == 200, f"{label}: {response.text}"
        if label == "transformations/pipeline":
            assert response.json()["success"] is True, response.text
        if label == "transformations/validate":
            assert "is_valid" in response.json()

    @pytest.mark.parametrize("label, method, path, body", ENDPOINTS, ids=IDS)
    async def test_malformed_id_is_400(self, async_authorized_client, setup_database, s3_stubbed,
                                       label, method, path, body):
        await seed()
        response = await _call(async_authorized_client, method, path, body, MALFORMED)
        assert response.status_code == 400, f"{label}: {response.status_code} {response.text}"

    @pytest.mark.parametrize("label, method, path, body", ENDPOINTS, ids=IDS)
    async def test_unknown_id_is_404(self, async_authorized_client, setup_database, s3_stubbed,
                                     label, method, path, body):
        await seed()
        response = await _call(async_authorized_client, method, path, body, str(ObjectId()))
        assert response.status_code == 404, f"{label}: {response.status_code} {response.text}"

    @pytest.mark.parametrize("label, method, path, body", ENDPOINTS, ids=IDS)
    async def test_foreign_document_is_404(self, async_authorized_client, setup_database, s3_stubbed,
                                           label, method, path, body):
        foreign = await seed(user_id="someone-else")
        response = await _call(async_authorized_client, method, path, body, str(foreign.id))
        assert response.status_code == 404, f"{label}: {response.status_code} {response.text}"
