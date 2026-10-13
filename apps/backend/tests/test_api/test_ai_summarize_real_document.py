"""#981: POST /ai/summarize against a real stored dataset, through to what is stored.

`test_ai_analysis.py` gave this route a `MagicMock` dataset with `save = AsyncMock()` and
a stubbed summarizer returning a shape the route never returns, so nothing saw that the
summary failed for any dataset with fewer than two numeric columns, showed the exception,
and saved the failure over the dataset's summary. Here the dataset is a real document
carrying what POST /data/process really stores (captured from the API, #808), and no
model key is set, so the summarizer takes its real rule-based path. Nothing is stubbed
except where a test says so.
"""
import copy
import json
from pathlib import Path

import pytest

from app.billing import metering
from app.models.user_data import AISummary, UserData
from app.services.dataset_summarization import dataset_summarization_service

TEST_USER = "test_user_123"
PROCESSED = json.loads(
    (Path(__file__).resolve().parents[4] / "apps/frontend/__tests__/fixtures/dataProcessResponse.json").read_text()
)
PARTS = ("schema", "statistics", "quality_report")
#: Patched on the class: the service is one shared object, and restoring a patched
#: instance attribute leaves one behind that bypasses later patches of the class.
SUMMARIZER = type(dataset_summarization_service)


async def _dataset(**fields) -> UserData:
    doc = UserData(
        **{
            "user_id": TEST_USER,
            "filename": "churn.csv",
            "original_filename": "churn.csv",
            "file_path": f"datasets/{TEST_USER}/churn.csv",
            "s3_url": "s3://test-bucket/churn.csv",
            "num_rows": 5,
            "num_columns": 3,
            "data_schema": [],
            "is_processed": True,
            "data_preview": [{"age": 41, "churned": 0}, {"age": 22, "churned": 1}],
            **{part: copy.deepcopy(PROCESSED[part]) for part in PARTS},
            **fields,
        }
    )
    await doc.insert()
    return doc


def _with_null(path: str) -> dict:
    """The captured processing result with one stored key set to null."""
    part, _, key = path.partition(".")
    if not key:
        return {part: None}
    value = copy.deepcopy(PROCESSED[part])
    value[key] = None
    return {part: value}


@pytest.mark.asyncio
async def test_a_dataset_with_no_correlations_gets_a_real_summary(setup_database, async_authorized_client):
    """The captured dataset has fewer than two numeric columns, so processing stored
    `correlation_matrix: null`. That alone used to turn the summary into the error card."""
    assert PROCESSED["statistics"]["correlation_matrix"] is None
    doc = await _dataset()

    response = await async_authorized_client.post(f"/api/v1/ai/summarize/{doc.id}")

    body = response.json()
    assert response.status_code == 200, response.text
    assert body["model_used"] == "fallback"
    assert body["overview"].startswith("Dataset contains 5 rows and 3 columns")
    stored = await UserData.get(doc.id)
    assert stored.aiSummary.overview == body["overview"]
    assert await metering.usage_for(TEST_USER, "ai_calls") == 0  # no model ran


@pytest.mark.parametrize(
    "path",
    [
        "schema", "statistics", "quality_report",
        "schema.columns", "schema.row_count", "schema.column_count", "schema.file_type",
        "statistics.correlation_matrix", "statistics.column_statistics", "statistics.missing_value_summary",
        "quality_report.overall_quality_score", "quality_report.critical_issues", "quality_report.warnings",
        "quality_report.recommendations", "quality_report.dimension_scores",
    ],
)
@pytest.mark.asyncio
async def test_a_stored_null_is_read_like_a_missing_key(setup_database, async_authorized_client, path):
    doc = await _dataset(**_with_null(path))

    response = await async_authorized_client.post(f"/api/v1/ai/summarize/{doc.id}")

    assert response.status_code == 200, response.text
    assert response.json()["model_used"] == "fallback", response.json()["issues"]


@pytest.mark.asyncio
async def test_a_failed_summary_says_so_without_the_exception_and_is_not_saved(
    setup_database, async_authorized_client, monkeypatch
):
    earlier = AISummary(overview="Written at upload.", issues=[], relationships=[], suggestions=[], rawMarkdown="# ok")
    doc = await _dataset(aiSummary=earlier)

    def exploding(_service, _context):
        raise RuntimeError("s3://narrative-prod/datasets/u/secret.csv unreadable")

    monkeypatch.setattr(SUMMARIZER, "_generate_fallback_summary", exploding)

    response = await async_authorized_client.post(f"/api/v1/ai/summarize/{doc.id}")

    body = response.json()
    assert response.status_code == 200, response.text
    assert body["model_used"] == "error"
    assert "secret.csv" not in response.text and "RuntimeError" not in response.text
    assert "reference" in body["issues"][0]
    assert (await UserData.get(doc.id)).aiSummary.overview == "Written at upload."
    assert await metering.usage_for(TEST_USER, "ai_calls") == 0


@pytest.mark.asyncio
async def test_saving_the_summary_keeps_what_was_written_while_it_was_made(
    setup_database, async_authorized_client, monkeypatch
):
    """The route read the dataset, waited for the summary, then saved its whole copy."""
    doc = await _dataset()
    real = dataset_summarization_service.generate_comprehensive_summary

    async def slow(_service, request):
        await UserData.get_motor_collection().update_one({"_id": doc.id}, {"$set": {"num_rows": 999}})
        return await real(request)

    monkeypatch.setattr(SUMMARIZER, "generate_comprehensive_summary", slow)

    response = await async_authorized_client.post(f"/api/v1/ai/summarize/{doc.id}")

    assert response.status_code == 200, response.text
    stored = await UserData.get(doc.id)
    assert stored.num_rows == 999
    assert stored.aiSummary is not None
