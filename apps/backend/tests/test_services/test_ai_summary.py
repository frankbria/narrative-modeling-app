import logging
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from beanie import PydanticObjectId

from app.models.user_data import AISummary, SchemaField, UserData
from app.utils.ai_summary import (
    call_openai_api,
    generate_dataset_summary,
    initialize_openai_client,
    prepare_dataset_summary,
)

# Document construction requires Beanie model registration (no DB IO needed)
pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("beanie_models_initialized")]


@pytest.fixture
def mock_user_data():
    """Create a mock UserData object for testing."""
    return UserData(
        id=PydanticObjectId(),
        s3_url="s3://test-bucket/test-file.csv",
        filename="test.csv",
        original_filename="test.csv",
        num_rows=100,
        num_columns=5,
        user_id="test_user_123",
        data_schema=[
            SchemaField(
                field_name="column1",
                field_type="numeric",
                data_type="float",
                inferred_dtype="float64",
                unique_values=50,
                missing_values=5,
                is_constant=False,
                is_high_cardinality=False,
                example_values=[1.0, 2.0, 3.0]),
            SchemaField(
                field_name="categorical_col",
                field_type="categorical",
                data_type="string",
                inferred_dtype="object",
                missing_values=0,
                is_constant=False,
                is_high_cardinality=False,
                unique_values=3,
                example_values=["A", "B", "C"])
        ])


@pytest.fixture
def mock_ai_summary():
    """Create a mock AISummary object for testing."""
    return AISummary(
        overview="Test dataset overview",
        issues=["Issue 1", "Issue 2"],
        relationships=["Relationship 1", "Relationship 2"],
        suggestions=["Suggestion 1", "Suggestion 2"],
        rawMarkdown="# Test Dataset Analysis\n\nThis is a test analysis.",
        createdAt=datetime.now(UTC))


# The success path, through to what is stored, is tested against a real document in
# tests/test_api/test_dataset_writers_keep_each_others_fields.py (#983). It was tested here
# with UserData.save patched out, which is the write that did the damage.


@pytest.mark.asyncio
async def test_generate_dataset_summary_existing(mock_user_data, mock_ai_summary):
    """Test when AI summary already exists."""
    mock_user_data.aiSummary = mock_ai_summary

    with patch("app.models.user_data.UserData.get") as mock_get, patch(
        "app.utils.ai_summary.call_openai_api"
    ) as mock_call_api:

        mock_get.return_value = mock_user_data

        result = await generate_dataset_summary(str(mock_user_data.id))

        assert result == mock_ai_summary
        mock_get.assert_called_once_with(str(mock_user_data.id))
        mock_call_api.assert_not_called()


@pytest.mark.asyncio
async def test_generate_dataset_summary_not_found():
    """Test when UserData document is not found."""
    with patch("app.models.user_data.UserData.get") as mock_get:
        mock_get.return_value = None

        result = await generate_dataset_summary("507f1f77bcf86cd799439011")

        assert result is None
        mock_get.assert_called_once()


@pytest.mark.asyncio
async def test_generate_dataset_summary_api_error(mock_user_data):
    """Test when OpenAI API call fails."""
    with patch("app.models.user_data.UserData.get") as mock_get, patch(
        "app.utils.ai_summary.call_openai_api"
    ) as mock_call_api:

        mock_get.return_value = mock_user_data
        mock_call_api.return_value = None

        result = await generate_dataset_summary(str(mock_user_data.id))

        assert result is None
        mock_get.assert_called_once_with(str(mock_user_data.id))
        mock_call_api.assert_called_once()


def test_prepare_dataset_summary(mock_user_data):
    """Test preparation of dataset summary."""
    summary = prepare_dataset_summary(mock_user_data)

    assert summary["filename"] == mock_user_data.filename
    assert summary["num_rows"] == mock_user_data.num_rows
    assert summary["num_columns"] == mock_user_data.num_columns
    assert len(summary["columns"]) == len(mock_user_data.data_schema)

    # Check first column details
    first_column = summary["columns"][0]
    assert first_column["name"] == "column1"
    assert first_column["type"] == "numeric"
    assert first_column["data_type"] == "float"
    assert first_column["unique_values"] == 50
    assert first_column["missing_values"] == 5
    assert first_column["is_constant"] is False
    assert first_column["is_high_cardinality"] is False
    assert len(first_column["example_values"]) == 3


@pytest.mark.asyncio
async def test_call_openai_api_success():
    """Test successful OpenAI API call."""
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content="""{
                    "overview": "Test overview",
                    "issues": ["Issue 1"],
                    "relationships": ["Relationship 1"],
                    "suggestions": ["Suggestion 1"],
                    "rawMarkdown": "# Test Analysis"
                }"""
            )
        )
    ]

    with patch("app.utils.ai_summary.client") as mock_client:
        mock_client.chat.completions.create.return_value = mock_response

        result = await call_openai_api(
            {"filename": "test.csv", "num_rows": 100, "num_columns": 3, "columns": []}
        )

        assert isinstance(result, AISummary)
        assert result.overview == "Test overview"
        assert result.issues == ["Issue 1"]
        assert result.relationships == ["Relationship 1"]
        assert result.suggestions == ["Suggestion 1"]
        assert result.rawMarkdown == "# Test Analysis"


@pytest.mark.asyncio
async def test_call_openai_api_client_not_initialized():
    """Test when OpenAI client is not initialized."""
    with patch("app.utils.ai_summary.client", None):
        result = await call_openai_api({"filename": "test.csv", "columns": []})
        assert result is None


@pytest.mark.asyncio
async def test_call_openai_api_invalid_json():
    """Test when OpenAI returns invalid JSON."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="Invalid JSON"))]

    with patch("app.utils.ai_summary.client") as mock_client:
        mock_client.chat.completions.create.return_value = mock_response

        result = await call_openai_api({"filename": "test.csv", "columns": []})

        assert result is None


@pytest.mark.asyncio
async def test_call_openai_api_exception():
    """Test when OpenAI API call raises an exception."""
    with patch("app.utils.ai_summary.client") as mock_client:
        mock_client.chat.completions.create.side_effect = Exception("API Error")

        result = await call_openai_api({"filename": "test.csv", "columns": []})

        assert result is None


def test_initialize_openai_client():
    """Test OpenAI client initialization."""
    # Patch the reference imported into the module under test, and restore the
    # module-level `client` global afterwards so other tests are unaffected
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test_key"}), patch(
        "app.utils.ai_summary.build_openai_client"
    ) as mock_build, patch("app.utils.ai_summary.client", None):

        initialize_openai_client()
        # Constructed through the shared factory so the request timeout is set (#501)
        mock_build.assert_called_once_with("test_key")


def test_initialize_openai_client_no_key():
    """Test OpenAI client initialization without API key."""
    with patch.dict("os.environ", {}, clear=True), patch(
        "app.utils.ai_summary.build_openai_client"
    ) as mock_build, patch("app.utils.ai_summary.client", None):

        initialize_openai_client()
        mock_build.assert_not_called()


def _clean_user_data(user_id: str) -> UserData:
    return UserData(
        user_id=user_id,
        filename="keyless.csv",
        original_filename="keyless.csv",
        s3_url=f"s3://b/datasets/{user_id}/keyless.csv",
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
    )


def test_a_missing_key_is_one_warning(caplog):
    """#1256: running without a key is a supported mode, reported like the other
    services: once, at WARNING, never at ERROR."""
    with patch.dict("os.environ", {}, clear=True), patch(
        "app.utils.ai_summary.client", None
    ), caplog.at_level(logging.DEBUG):
        initialize_openai_client()

    warnings_or_worse = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert [r.levelno for r in warnings_or_worse] == [logging.WARNING]
    assert "OPENAI_API_KEY" in warnings_or_worse[0].getMessage()


@pytest.mark.asyncio
async def test_a_keyless_summary_logs_nothing_above_info(setup_database, caplog):
    """#1256: with no key the summary is skipped, which is the normal fallback, so
    nothing above INFO reaches the log (or Sentry)."""
    doc = await _clean_user_data("keyless-user").insert()

    with patch("app.utils.ai_summary.client", None), caplog.at_level(logging.DEBUG):
        result = await generate_dataset_summary(str(doc.id))

    assert result is None
    assert [r.getMessage() for r in caplog.records if r.levelno > logging.INFO] == []
    assert any(
        str(doc.id) in r.getMessage() and r.levelno == logging.INFO
        for r in caplog.records
    )


@pytest.mark.asyncio
async def test_with_a_key_a_missing_summary_is_still_an_error(setup_database, caplog):
    """The quiet path is only for a missing key: when a key is configured and
    OpenAI gives nothing back, it is still an ERROR naming the dataset."""
    doc = await _clean_user_data("keyed-user").insert()

    with patch("app.utils.ai_summary.client", MagicMock()), patch(
        "app.utils.ai_summary.call_openai_api", AsyncMock(return_value=None)
    ), caplog.at_level(logging.DEBUG):
        result = await generate_dataset_summary(str(doc.id))

    assert result is None
    assert any(
        str(doc.id) in r.getMessage() and r.levelno == logging.ERROR
        for r in caplog.records
    )
