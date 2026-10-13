"""#683: POST /ai/analyze against a real stored dataset.

`test_ai_analysis.py` drove this route with a `MagicMock` dataset behind a patched
`UserData.find_one`, under an id ("test-file-123") no real lookup could match. The
route worked, but two things those tests could not see were wrong or unchecked: a
rule-based fallback was charged as an AI call, and nothing ran the lookup itself.
"""
import copy
import json
from pathlib import Path

import pytest

from app.billing import metering
from app.models.user_data import UserData
from app.services.mcp_integration import MCPAnalysisResponse, mcp_service

TEST_USER = "test_user_123"
PROCESSED = json.loads(
    (Path(__file__).resolve().parents[4] / "apps/frontend/__tests__/fixtures/dataProcessResponse.json").read_text()
)
#: Patched on the class: the service is one shared object (see tasks/lessons.md, #983).
MCP = type(mcp_service)


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


def _from_mcp(seen: dict):
    async def analyze_dataset(_service, **kwargs):
        seen.update(kwargs)
        return MCPAnalysisResponse(
            file_id=kwargs["dataset_id"], analysis_type=kwargs["analysis_type"], summary="Five rows, three columns.",
            insights=[{"type": "data_overview", "title": "Overview", "description": "5 rows"}],
            recommendations=["Collect more rows"], metadata={"mcp_available": True},
        )

    return analyze_dataset


@pytest.mark.asyncio
async def test_with_no_analysis_service_the_answer_is_rule_based_and_free(setup_database, async_authorized_client):
    """Nothing is stubbed: the MCP server is not running here, as it is not in any
    deployed environment (#508), so this is the answer every caller gets today."""
    doc = await _dataset()

    response = await async_authorized_client.post(f"/api/v1/ai/analyze/{doc.id}")

    body = response.json()
    assert response.status_code == 200, response.text
    assert body["metadata"] == {"mcp_available": False, "fallback_mode": True}
    assert "5 rows, 3 columns" in body["summary"]
    assert await metering.usage_for(TEST_USER, "ai_calls") == 0


@pytest.mark.asyncio
async def test_an_analysis_from_the_service_is_passed_on_and_charged(
    setup_database, async_authorized_client, monkeypatch
):
    doc = await _dataset()
    seen: dict = {}
    monkeypatch.setattr(MCP, "analyze_dataset", _from_mcp(seen))

    response = await async_authorized_client.post(
        f"/api/v1/ai/analyze/{doc.id}", json={"file_id": str(doc.id), "analysis_type": "quality"}
    )

    assert response.status_code == 200, response.text
    assert response.json()["summary"] == "Five rows, three columns."
    assert response.json()["analysis_type"] == "quality"
    assert seen["dataset_id"] == str(doc.id) and seen["user_id"] == TEST_USER
    assert seen["schema"] == PROCESSED["schema"] and seen["sample_data"] == [{"age": 41, "churned": 0}]
    assert await metering.usage_for(TEST_USER, "ai_calls") == 1


@pytest.mark.asyncio
async def test_an_unprocessed_dataset_is_refused_and_not_charged(setup_database, async_authorized_client):
    doc = await _dataset(is_processed=False)

    response = await async_authorized_client.post(f"/api/v1/ai/analyze/{doc.id}")

    assert response.status_code == 400
    assert "must be processed" in response.json()["detail"]
    assert await metering.usage_for(TEST_USER, "ai_calls") == 0


@pytest.mark.asyncio
async def test_someone_elses_dataset_is_not_found(setup_database, async_authorized_client):
    theirs = await _dataset(user_id="someone-else")

    for file_id in (str(theirs.id), "test-file-123"):
        response = await async_authorized_client.post(f"/api/v1/ai/analyze/{file_id}")
        assert response.status_code == 404, response.text
        assert response.json()["detail"] == "File not found"


@pytest.mark.asyncio
async def test_a_failing_analysis_service_is_a_sanitised_500_and_not_charged(
    setup_database, async_authorized_client, monkeypatch
):
    doc = await _dataset()

    async def broken(_service, **_kwargs):
        raise RuntimeError("MCP service unavailable at mcp.internal:8765")

    monkeypatch.setattr(MCP, "analyze_dataset", broken)

    response = await async_authorized_client.post(f"/api/v1/ai/analyze/{doc.id}")

    assert response.status_code == 500
    assert response.json()["detail"] == "Internal server error" and response.json()["request_id"]
    assert "mcp.internal" not in response.text
    assert await metering.usage_for(TEST_USER, "ai_calls") == 0
