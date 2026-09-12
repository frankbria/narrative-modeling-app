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


class TestDetectMetering:
    """#461 on the newly reachable route: the unit stays only when a model request was sent."""

    async def test_ai_off_costs_nothing(self, async_authorized_client, setup_database, s3_frame):
        from app.billing import metering

        ds = await _dataset()
        response = await async_authorized_client.post(f"{BASE}/detect", json=_detect_body(str(ds.id)))
        assert response.status_code == 200 and response.json()["summary"]["ai_analysis_used"] is False
        assert await metering.usage_for(TEST_USER, "ai_calls") == 0

    async def test_a_swallowed_failure_hands_the_unit_back(self, async_authorized_client, setup_database, s3_frame):
        """codex: the handler reports failures as 200 {success: false}, which the refund middleware
        never sees — the handler must release the reservation itself."""
        from app.billing import metering

        ds = await _dataset()
        with patch("app.api.routes.data_issues.DataIssueDetectionService.detect_issues",
                   new_callable=AsyncMock, side_effect=RuntimeError("s3 down")):
            response = await async_authorized_client.post(
                f"{BASE}/detect", json={"dataset_id": str(ds.id), "options": {"include_ai_analysis": True}}
            )
        assert response.status_code == 200 and response.json()["success"] is False
        assert await metering.usage_for(TEST_USER, "ai_calls") == 0

    async def test_breaker_fallback_is_not_a_paid_call(self, async_authorized_client, setup_database, s3_frame):
        """codex: a key exists but the analyzer's request never went out (breaker open) — the
        analyzer counts requests actually sent, so nothing is charged."""
        from app.billing import metering
        from app.utils import ai_issue_analyzer as mod

        ds = await _dataset()
        with patch.object(mod.AIIssueAnalyzer, "_initialize_client", return_value=object()), \
             patch.object(mod.AIIssueAnalyzer, "_call_openai_analysis", new_callable=AsyncMock, return_value=None):
            response = await async_authorized_client.post(
                f"{BASE}/detect", json={"dataset_id": str(ds.id), "options": {"include_ai_analysis": True}}
            )
        assert response.status_code == 200, response.text
        assert response.json()["summary"]["ai_analysis_used"] is False
        assert await metering.usage_for(TEST_USER, "ai_calls") == 0

    async def test_a_sent_request_is_charged(self, async_authorized_client, setup_database, s3_frame):
        from app.billing import metering
        from app.utils import ai_issue_analyzer as mod

        async def sent(self, *a, **k):
            self.calls_made += 1
            return []

        ds = await _dataset()
        with patch.object(mod.AIIssueAnalyzer, "_initialize_client", return_value=object()), \
             patch.object(mod.AIIssueAnalyzer, "analyze_data_patterns", sent):
            response = await async_authorized_client.post(
                f"{BASE}/detect", json={"dataset_id": str(ds.id), "options": {"include_ai_analysis": True}}
            )
        assert response.status_code == 200, response.text
        assert response.json()["summary"]["ai_analysis_used"] is True
        assert await metering.usage_for(TEST_USER, "ai_calls") == 1

    async def test_ai_off_is_not_gated_by_an_exhausted_ai_quota(self, async_authorized_client, setup_database, s3_frame):
        """codex: a route dependency would have 402'd a rule-based-only run for a tenant out of
        AI quota; the reservation happens inside the handler only when AI is asked for."""
        from app.billing import metering
        from app.billing.plans import PLAN_LIMITS
        from app.models.subscription import PlanTier
        from app.models.usage import UsageRecord

        ds = await _dataset()
        limit = PLAN_LIMITS[PlanTier.FREE].ai_calls
        await UsageRecord(user_id=TEST_USER, period_key=metering.period_key_for(), metric="ai_calls", units=limit).insert()
        off = await async_authorized_client.post(f"{BASE}/detect", json=_detect_body(str(ds.id)))
        assert off.status_code == 200, off.text
        on = await async_authorized_client.post(
            f"{BASE}/detect", json={"dataset_id": str(ds.id), "options": {"include_ai_analysis": True}}
        )
        assert on.status_code == 402, on.text

    async def test_a_sent_request_stays_charged_when_a_later_step_fails(self, async_authorized_client, setup_database, s3_frame):
        """codex: the model was called; storing the result then failed — the unit is owed."""
        from app.billing import metering
        from app.utils import ai_issue_analyzer as mod

        async def sent(self, *a, **k):
            self.calls_made += 1
            return []

        ds = await _dataset()
        with patch.object(mod.AIIssueAnalyzer, "_initialize_client", return_value=object()), \
             patch.object(mod.AIIssueAnalyzer, "analyze_data_patterns", sent), \
             patch("app.api.routes.data_issues.DataIssueDetectionService.store_detection_results",
                   new_callable=AsyncMock, side_effect=RuntimeError("mongo down")):
            response = await async_authorized_client.post(
                f"{BASE}/detect", json={"dataset_id": str(ds.id), "options": {"include_ai_analysis": True}}
            )
        assert response.status_code == 200 and response.json()["success"] is False
        assert await metering.usage_for(TEST_USER, "ai_calls") == 1

    async def test_stored_summary_reads_back_whether_ai_ran(self, async_authorized_client, setup_database, s3_frame):
        from app.utils import ai_issue_analyzer as mod

        async def sent(self, *a, **k):
            self.calls_made += 1
            return []

        ds = await _dataset()
        with patch.object(mod.AIIssueAnalyzer, "_initialize_client", return_value=object()), \
             patch.object(mod.AIIssueAnalyzer, "analyze_data_patterns", sent):
            await async_authorized_client.post(
                f"{BASE}/detect", json={"dataset_id": str(ds.id), "options": {"include_ai_analysis": True}}
            )
        issues = await async_authorized_client.get(f"{BASE}/{ds.id}/issues")
        assert issues.status_code == 200 and issues.json()["summary"]["ai_analysis_used"] is True
