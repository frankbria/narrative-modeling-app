"""generate_ai_summary_safe must actually produce a summary — from the SAFE frame
it is handed, without leaking PII to OpenAI (#490).

Before #490 the wrapper passed the DataFrame where a ``user_data_id: str`` was
expected, so every call raised inside ``generate_dataset_summary`` and was
swallowed — the summary stayed permanently null for the PII-confirmed and chunked
upload paths. The fix summarizes the masked frame directly; these tests assert a
summary IS produced and persisted, and that the values sent to OpenAI are the
masked ones (the chunked path stores a RAW schema, so reading the stored schema
would leak PII).
"""

from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest

import app.utils.ai_summary as ai_summary
from app.api.routes.secure_upload import generate_ai_summary_safe
from app.models.user_data import AISummary, SchemaField, UserData

pytestmark = [pytest.mark.usefixtures("beanie_models_initialized")]


def _fake_summary() -> AISummary:
    return AISummary(
        overview="ok", issues=[], relationships=[], suggestions=[], rawMarkdown="ok"
    )


@pytest.mark.unit
def test_prepare_summary_from_df_uses_frame_values():
    df = pd.DataFrame({"amount": [1, 2, 3], "label": ["a", "b", "a"]})
    out = ai_summary.prepare_dataset_summary_from_df(df, "sales.csv")
    assert out["filename"] == "sales.csv"
    assert out["num_rows"] == 3
    assert out["num_columns"] == 2
    names = {c["name"] for c in out["columns"]}
    assert names == {"amount", "label"}


@pytest.mark.asyncio
async def test_safe_summary_is_persisted(setup_database):
    """A PII-confirmed / chunked upload path yields a persisted summary (AC3)."""
    doc = await UserData(
        user_id="u1",
        filename="data.csv",
        original_filename="data.csv",
        s3_url="s3://b/datasets/u1/data.csv",
        num_rows=2,
        num_columns=1,
        data_schema=[
            SchemaField(
                field_name="col",
                field_type="numeric",
                inferred_dtype="int64",
                unique_values=2,
                missing_values=0,
                example_values=[1, 2],
                is_constant=False,
                is_high_cardinality=False,
            )
        ],
    ).insert()

    masked_df = pd.DataFrame({"col": [1, 2]})
    with patch.object(
        ai_summary, "call_openai_api", new=AsyncMock(return_value=_fake_summary())
    ):
        await generate_ai_summary_safe(str(doc.id), masked_df)

    refetched = await UserData.get(doc.id)
    assert refetched.aiSummary is not None
    assert refetched.aiSummary.overview == "ok"


@pytest.mark.asyncio
async def test_masked_frame_values_reach_openai_not_raw_stored_schema(setup_database):
    """Anti-leak (AC3): the chunked path stores a RAW schema but hands the task the
    MASKED frame. The summary must be built from the masked frame, so raw PII in
    the stored schema must never reach OpenAI."""
    raw_ssn = "123-45-6789"
    masked_ssn = "***-**-6789"
    doc = await UserData(
        user_id="u1",
        filename="people.csv",
        original_filename="people.csv",
        s3_url="s3://b/datasets/u1/people.csv",
        num_rows=1,
        num_columns=1,
        # Stored schema holds the RAW value (what the chunked complete path does).
        data_schema=[
            SchemaField(
                field_name="ssn",
                field_type="text",
                inferred_dtype="object",
                unique_values=1,
                missing_values=0,
                example_values=[raw_ssn],
                is_constant=True,
                is_high_cardinality=False,
            )
        ],
    ).insert()

    masked_df = pd.DataFrame({"ssn": [masked_ssn]})
    captured = {}

    async def _capture(summary_input):
        captured["input"] = summary_input
        return _fake_summary()

    with patch.object(ai_summary, "call_openai_api", new=_capture):
        await generate_ai_summary_safe(str(doc.id), masked_df)

    sent = str(captured["input"])
    assert masked_ssn in sent  # the masked value was summarized
    assert raw_ssn not in sent  # the raw stored value was NOT sent to OpenAI


@pytest.mark.asyncio
async def test_null_summary_is_logged_not_silent(setup_database, caplog):
    """AC2: a null result degrades visibly — logged at WARNING with the id."""
    doc = await UserData(
        user_id="u1",
        filename="d.csv",
        original_filename="d.csv",
        s3_url="s3://b/datasets/u1/d.csv",
        num_rows=1,
        num_columns=1,
        data_schema=[
            SchemaField(
                field_name="c",
                field_type="numeric",
                inferred_dtype="int64",
                unique_values=1,
                missing_values=0,
                example_values=[1],
                is_constant=True,
                is_high_cardinality=False,
            )
        ],
    ).insert()

    import logging

    with patch.object(ai_summary, "call_openai_api", new=AsyncMock(return_value=None)):
        with caplog.at_level(logging.WARNING):
            await generate_ai_summary_safe(str(doc.id), pd.DataFrame({"c": [1]}))

    refetched = await UserData.get(doc.id)
    assert refetched.aiSummary is None
    assert any(str(doc.id) in r.message and r.levelno == logging.WARNING for r in caplog.records)
