import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from beanie import PydanticObjectId
from app.models.user_data import UserData, AISummary, SchemaField
from app.utils.ai_summary import (
    generate_dataset_summary,
    prepare_dataset_summary,
    call_openai_api,
    initialize_openai_client)


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
        createdAt=datetime.now(timezone.utc))


@pytest.mark.asyncio
async def test_generate_dataset_summary_success(mock_user_data, mock_ai_summary):
    """Test successful generation of dataset summary."""
    with patch("app.models.user_data.UserData.get") as mock_get, patch(
        "app.utils.ai_summary.call_openai_api"
    ) as mock_call_api, patch("app.models.user_data.UserData.save") as mock_save:

        mock_get.return_value = mock_user_data
        mock_call_api.return_value = mock_ai_summary
        mock_save.return_value = None

        result = await generate_dataset_summary(str(mock_user_data.id))

        assert result == mock_ai_summary
        mock_get.assert_called_once_with(mock_user_data.id)
        mock_call_api.assert_called_once()
        mock_save.assert_called_once()


@pytest.mark.asyncio
async def test_generate_dataset_summary_existing(mock_user_data, mock_ai_summary):
    """Test when AI summary already exists."""
    mock_user_data.aiSummary = mock_ai_summary

    with patch("app.models.user_data.UserData.get") as mock_get, patch(
        "app.utils.ai_summary.call_openai_api"
    ) as mock_call_api:

        mock_get.return_value = mock_user_data


        assert result == mock_ai_summary
        mock_get.assert_called_once_with(mock_user_data.id)
        mock_call_api.assert_not_called()


@pytest.mark.asyncio
async def test_generate_dataset_summary_not_found():
    """Test when UserData document is not found."""
    with patch("app.models.user_data.UserData.get") as mock_get:
        mock_get.return_value = None


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


        assert result is None
        mock_get.assert_called_once_with(mock_user_data.id)
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
        assert result is None


@pytest.mark.asyncio
async def test_call_openai_api_invalid_json():
    """Test when OpenAI returns invalid JSON."""
    mock_response.choices = [MagicMock(message=MagicMock(content="Invalid JSON"))]

    with patch("app.utils.ai_summary.client") as mock_client:
        mock_client.chat.completions.create.return_value = mock_response

        assert result is None


@pytest.mark.asyncio
async def test_call_openai_api_exception():
    """Test when OpenAI API call raises an exception."""
    with patch("app.utils.ai_summary.client") as mock_client:
        mock_client.chat.completions.create.side_effect = Exception("API Error")

        assert result is None


def test_initialize_openai_client():
    """Test OpenAI client initialization."""
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test_key"}), patch(
        "openai.OpenAI"
    ) as mock_openai:

        initialize_openai_client()
        mock_openai.assert_called_once_with(api_key="test_key")


def test_initialize_openai_client_no_key():
    """Test OpenAI client initialization without API key."""
    with patch.dict("os.environ", {}, clear=True), patch(
        "openai.OpenAI"
    ) as mock_openai:

        initialize_openai_client()
        mock_openai.assert_not_called()
