"""POST /ai/analyze against a real stored dataset (#683, #508).

The analysis is rule-based: it is computed from the dataset's stored schema and
quality report and calls no model, so it is not metered. The MCP server it once
asked first was never deployed and was removed (#508), along with its probe.
"""
import copy
import json
from pathlib import Path

import pytest

from app.billing import metering
from app.billing.plans import PlanTier, limits_for
from app.models.usage import UsageRecord
from app.models.user_data import UserData

TEST_USER = "test_user_123"
PROCESSED = json.loads(
    (Path(__file__).resolve().parents[4] / "apps/frontend/__tests__/fixtures/dataProcessResponse.json").read_text()
)


async def _dataset(user_id: str = TEST_USER, **fields) -> UserData:
    doc = UserData(
        **{
            "user_id": user_id,
            "filename": "churn.csv",
            "original_filename": "churn.csv",
            "file_path": f"datasets/{user_id}/churn.csv",
            "s3_url": f"s3://test-bucket/datasets/{user_id}/churn.csv",
            "num_rows": 5,
            "num_columns": 3,
            "data_schema": [],
            "is_processed": True,
            "data_preview": [{"age": 41, "churned": 0}],
            **{part: copy.deepcopy(PROCESSED[part]) for part in ("schema", "statistics", "quality_report")},
            **fields,
        }
    )
    await doc.insert()
    return doc


@pytest.mark.asyncio
async def test_the_analysis_is_rule_based_and_free(setup_database, async_authorized_client):
    doc = await _dataset()

    response = await async_authorized_client.post(
        f"/api/v1/ai/analyze/{doc.id}", json={"file_id": str(doc.id), "analysis_type": "quality"}
    )

    body = response.json()
    assert response.status_code == 200, response.text
    assert body["metadata"] == {"ai_used": False}
    assert body["analysis_type"] == "quality"
    assert "5 rows, 3 columns" in body["summary"]
    assert [insight["type"] for insight in body["insights"]] == ["data_overview", "data_quality"]
    assert await metering.usage_for(TEST_USER, "ai_calls") == 0


@pytest.mark.asyncio
async def test_a_low_quality_score_recommends_cleaning(setup_database, async_authorized_client):
    quality_report = {**PROCESSED["quality_report"], "overall_quality_score": 0.5, "recommendations": []}
    doc = await _dataset(quality_report=quality_report)

    response = await async_authorized_client.post(f"/api/v1/ai/analyze/{doc.id}")

    assert response.status_code == 200, response.text
    assert response.json()["recommendations"] == ["Consider data cleaning to improve overall quality score"]


@pytest.mark.asyncio
async def test_a_tenant_at_the_ai_limit_still_gets_the_analysis(setup_database, async_authorized_client):
    await UsageRecord(
        user_id=TEST_USER, period_key=metering.period_key_for(), metric="ai_calls",
        units=limits_for(PlanTier.FREE).ai_calls,
    ).insert()
    doc = await _dataset()

    response = await async_authorized_client.post(f"/api/v1/ai/analyze/{doc.id}")

    assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_an_unprocessed_dataset_is_refused(setup_database, async_authorized_client):
    doc = await _dataset(is_processed=False)

    response = await async_authorized_client.post(f"/api/v1/ai/analyze/{doc.id}")

    assert response.status_code == 400
    assert "must be processed" in response.json()["detail"]


@pytest.mark.asyncio
async def test_someone_elses_dataset_is_not_found(setup_database, async_authorized_client):
    theirs = await _dataset(user_id="someone-else")

    for file_id in (str(theirs.id), "test-file-123"):
        response = await async_authorized_client.post(f"/api/v1/ai/analyze/{file_id}")
        assert response.status_code == 404, response.text
        assert response.json()["detail"] == "File not found"


@pytest.mark.asyncio
async def test_the_mcp_probe_is_gone(setup_database, async_authorized_client):
    response = await async_authorized_client.get("/api/v1/ai/health")

    assert response.status_code == 404
