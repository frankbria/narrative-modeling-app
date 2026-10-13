"""#983: three writers of one dataset document, each keeping to its own fields.

After an upload a background task waits for the model and stores the AI summary, while
the Explore page has `POST /data/process` store the schema, statistics and quality
report. Each read the document, awaited, and saved its whole copy, so whichever finished
last put the other's fields back to what they were before: processing undone, or the
summary dropped. `test_ai_summary.py` patched `UserData.save` and could not see it.

Each test here runs one writer for real against a real document and lets another
writer's result land while the first is waiting.
"""
import pandas as pd
import pytest

from app.api.routes import data_processing, secure_upload
from app.models.user_data import AISummary, UserData
from app.utils import ai_summary

TEST_USER = "test_user_123"
CSV = b"plan,spend\nbasic,10\npro,20\nbasic,12\n"
PROCESSED = {
    "schema": {"row_count": 3, "column_count": 2},
    "statistics": {"row_count": 3},
    "quality_report": {"overall_quality_score": 0.9},
    "is_processed": True,
}
SUMMARY = AISummary(overview="Three rows.", issues=[], relationships=[], suggestions=[], rawMarkdown="# ok")


async def _uploaded() -> UserData:
    doc = UserData(
        user_id=TEST_USER, filename="plans.csv", original_filename="plans.csv",
        file_path=f"datasets/{TEST_USER}/plans.csv", s3_url=f"s3://test-bucket/datasets/{TEST_USER}/plans.csv",
        num_rows=3, num_columns=2, data_schema=[], file_type="csv",
    )
    await doc.insert()
    return doc


def _model_call_during_which_the_dataset_is_processed(doc: UserData):
    async def call(_prompt):
        await UserData.get_motor_collection().update_one({"_id": doc.id}, {"$set": PROCESSED})
        return SUMMARY

    return call


async def _assert_processed_and_summarised(doc: UserData) -> None:
    stored = await UserData.get(doc.id)
    assert stored.is_processed is True
    assert stored.schema == PROCESSED["schema"]
    assert stored.statistics == PROCESSED["statistics"]
    assert stored.quality_report == PROCESSED["quality_report"]
    assert stored.aiSummary.overview == "Three rows."


@pytest.mark.asyncio
async def test_the_upload_summary_does_not_undo_processing(setup_database, monkeypatch):
    doc = await _uploaded()
    monkeypatch.setattr(ai_summary, "call_openai_api", _model_call_during_which_the_dataset_is_processed(doc))

    result = await ai_summary.generate_dataset_summary(str(doc.id))

    assert result.overview == "Three rows."
    await _assert_processed_and_summarised(doc)


@pytest.mark.asyncio
async def test_the_masked_upload_summary_does_not_undo_processing(setup_database, monkeypatch):
    """The path the PII-confirmed and chunked uploads take (#490)."""
    doc = await _uploaded()
    monkeypatch.setattr(ai_summary, "call_openai_api", _model_call_during_which_the_dataset_is_processed(doc))

    await secure_upload.generate_ai_summary_safe(str(doc.id), pd.DataFrame({"plan": ["basic"], "spend": [10]}))

    await _assert_processed_and_summarised(doc)


@pytest.mark.asyncio
async def test_processing_does_not_drop_a_summary_written_while_it_ran(
    setup_database, async_authorized_client, monkeypatch
):
    doc = await _uploaded()

    async def download_during_which_the_summary_lands(_key):
        await UserData.get_motor_collection().update_one(
            {"_id": doc.id}, {"$set": {"aiSummary": SUMMARY.model_dump()}}
        )
        return CSV

    # Through the shared service's own dict, which is cleaned up on undo. A setattr
    # on the instance leaves the original behind as an instance attribute, and every
    # later test that patches the class is then bypassed (tasks/lessons.md, #683).
    monkeypatch.setitem(
        vars(data_processing.s3_service), "download_file_bytes", download_during_which_the_summary_lands
    )

    response = await async_authorized_client.post("/api/v1/data/process", json={"file_id": str(doc.id)})

    assert response.status_code == 200, response.text
    stored = await UserData.get(doc.id)
    assert stored.aiSummary.overview == "Three rows."
    assert stored.is_processed is True and stored.processed_at is not None
    assert stored.schema["row_count"] == 3 and stored.schema == response.json()["schema"]
    assert stored.statistics["row_count"] == 3
    assert stored.quality_report["overall_quality_score"] == response.json()["quality_report"]["overall_quality_score"]


@pytest.mark.asyncio
async def test_processing_someone_elses_or_no_dataset_is_not_found(setup_database, async_authorized_client):
    other = UserData(
        user_id="someone-else", filename="a.csv", original_filename="a.csv", file_path="datasets/x/a.csv",
        s3_url="s3://test-bucket/datasets/x/a.csv", num_rows=1, num_columns=1, data_schema=[],
    )
    await other.insert()

    for file_id in (str(other.id), "not-an-object-id"):
        response = await async_authorized_client.post("/api/v1/data/process", json={"file_id": file_id})
        assert response.status_code == 404, response.text


def test_these_writers_never_save_the_whole_document():
    """A guard for the three modules above, which run concurrently with one another by
    design. It reads source text: it does not see a save reached through a helper in
    another module, and it says nothing about the dataset's other writers."""
    from pathlib import Path

    app_dir = Path(__file__).resolve().parents[2] / "app"
    saving = [
        name
        for name in ("utils/ai_summary.py", "api/routes/data_processing.py", "api/routes/secure_upload.py")
        if ".save(" in (app_dir / name).read_text()
    ]

    assert saving == []


@pytest.mark.asyncio
async def test_a_stored_location_that_cannot_be_read_is_a_sanitised_500(setup_database, async_authorized_client):
    """A stored URL can be a presigned one; its query string must not reach the client."""
    doc = UserData(
        user_id=TEST_USER, filename="a.csv", original_filename="a.csv", file_path="datasets/u/a.csv",
        s3_url="gopher://nowhere/a.csv?X-Amz-Signature=secret-signature", num_rows=1, num_columns=1, data_schema=[],
    )
    await doc.insert()

    response = await async_authorized_client.post("/api/v1/data/process", json={"file_id": str(doc.id)})

    assert response.status_code == 500
    assert "secret-signature" not in response.text
    assert (await UserData.get(doc.id)).is_processed is False
