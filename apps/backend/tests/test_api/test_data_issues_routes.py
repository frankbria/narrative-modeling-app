"""First route tests for the data-issues router (#471).

The router was mounted only on a dead aggregator, so every endpoint 404'd and no test
existed to notice. These go through the full app with real `UserData` and
`DataIssueRecord` documents; only the S3 dataframe load is stubbed.
"""
from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest
from bson import ObjectId

from app.models.data_issue import DataIssueRecord
from app.models.user_data import UserData

pytestmark = pytest.mark.asyncio

TEST_USER = "test_user_123"  # what async_authorized_client authenticates as
BASE = "/api/v1/data-issues"


def _frame() -> pd.DataFrame:
    return pd.DataFrame({
        "id": [1, 2, 2, 4, 5, 6], "age": [25, None, 30, None, 45, 45],
        "email": ["a@x.test", "b@x.test", "b@x.test", "not-an-email", "e@x.test", "f@x.test"],
    })


async def _dataset(owner: str = TEST_USER) -> UserData:
    return await UserData(
        user_id=owner, filename="d.csv", original_filename="d.csv",
        s3_url=f"https://test-bucket.s3.amazonaws.com/datasets/{owner}/d.csv", num_rows=6, num_columns=3,
        data_schema=[], file_type="csv", is_processed=True,
    ).insert()


@pytest.fixture
def s3_frame():
    with patch("app.api.routes.data_issues.get_dataframe_from_s3", new_callable=AsyncMock, return_value=_frame()):
        yield


def _detect_body(dataset_id: str) -> dict:
    return {"dataset_id": dataset_id, "options": {"include_ai_analysis": False}}


class TestDataIssuesRoutes:
    async def test_detect_finds_the_issues_in_the_frame(self, async_authorized_client, setup_database, s3_frame):
        ds = await _dataset()
        response = await async_authorized_client.post(f"{BASE}/detect", json=_detect_body(str(ds.id)))
        assert response.status_code == 200, response.text
        body = response.json()
        types = {i["issue_type"] for i in body["issues"]}
        assert types & {"missing_values", "duplicates"}, types
        assert body["summary"]["total_issues"] >= 2
        assert await DataIssueRecord.find(DataIssueRecord.dataset_id == str(ds.id)).count() == 1

    async def test_issues_and_history_read_back(self, async_authorized_client, setup_database, s3_frame):
        ds = await _dataset()
        await async_authorized_client.post(f"{BASE}/detect", json=_detect_body(str(ds.id)))
        issues = await async_authorized_client.get(f"{BASE}/{ds.id}/issues")
        assert issues.status_code == 200 and issues.json()["summary"]["total_issues"] >= 2
        history = await async_authorized_client.get(f"{BASE}/{ds.id}/history")
        assert history.status_code == 200 and history.json()["total"] >= 1

    async def test_preview_apply_and_batch_fix(self, async_authorized_client, setup_database, s3_frame):
        ds = await _dataset()
        detected = (await async_authorized_client.post(f"{BASE}/detect", json=_detect_body(str(ds.id)))).json()
        fixable = next(i for i in detected["issues"] if i["suggested_fixes"])
        issue_id = fixable["issue_id"]

        preview = await async_authorized_client.post(f"{BASE}/preview-fix", json={"dataset_id": str(ds.id), "issue_id": issue_id})
        assert preview.status_code == 200, preview.text

        with patch("app.api.routes.data_issues.upload_dataframe_to_s3", new_callable=AsyncMock,
                   return_value=f"s3://test-bucket/transformed/{TEST_USER}/d_fixed.parquet"):
            applied = await async_authorized_client.post(
                f"{BASE}/apply-fix", json={"dataset_id": str(ds.id), "issue_id": issue_id, "preview_mode": False}
            )
            assert applied.status_code == 200, applied.text
            assert applied.json()["success"] is True
            others = [i["issue_id"] for i in detected["issues"] if i["suggested_fixes"] and i["issue_id"] != issue_id]
            if others:
                batch = await async_authorized_client.post(
                    f"{BASE}/batch-fix", json={"dataset_id": str(ds.id), "issue_ids": others, "preview_mode": False}
                )
                assert batch.status_code == 200, batch.text

    @pytest.mark.parametrize("method, path, body", [
        ("POST", "/detect", lambda i: _detect_body(i)),
        ("GET", "/{id}/issues", None),
        ("POST", "/preview-fix", lambda i: {"dataset_id": i, "issue_id": "x"}),
        ("POST", "/apply-fix", lambda i: {"dataset_id": i, "issue_id": "x"}),
        ("POST", "/batch-fix", lambda i: {"dataset_id": i, "issue_ids": ["x"]}),
    ], ids=["detect", "issues", "preview-fix", "apply-fix", "batch-fix"])
    async def test_another_tenants_dataset_is_404(self, async_authorized_client, setup_database, s3_frame, method, path, body):
        foreign = await _dataset(owner="someone-else")
        fid = str(foreign.id)
        await DataIssueRecord(dataset_id=fid, user_id="someone-else", issues=[], detection_options={}).insert()
        response = await async_authorized_client.request(
            method, f"{BASE}{path.replace('{id}', fid)}", json=body(fid) if body else None
        )
        assert response.status_code == 404, f"{method} {path}: {response.status_code} {response.text}"

    async def test_history_of_another_tenants_dataset_is_an_empty_page(self, async_authorized_client, setup_database):
        """History is a list scoped to the caller: another tenant's dataset and an unknown one
        both answer an empty page — identical, so neither reveals that the other exists."""
        foreign = await _dataset(owner="someone-else")
        await DataIssueRecord(dataset_id=str(foreign.id), user_id="someone-else", issues=[], detection_options={}).insert()
        theirs = await async_authorized_client.get(f"{BASE}/{foreign.id}/history")
        unknown = await async_authorized_client.get(f"{BASE}/{ObjectId()}/history")
        assert theirs.status_code == unknown.status_code == 200
        assert theirs.json()["total"] == unknown.json()["total"] == 0
        assert theirs.json()["records"] == []

    async def test_unknown_dataset_is_404(self, async_authorized_client, setup_database, s3_frame):
        response = await async_authorized_client.post(f"{BASE}/detect", json=_detect_body(str(ObjectId())))
        assert response.status_code == 404
