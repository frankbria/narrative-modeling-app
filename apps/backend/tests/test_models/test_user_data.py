import pytest
from datetime import datetime, timezone
from beanie import PydanticObjectId
from app.models.user_data import UserData, SchemaField, AISummary, get_current_time


def test_get_current_time():
    """Test the get_current_time function."""
    current_time = get_current_time()
    assert isinstance(current_time, datetime)
    assert current_time.tzinfo == timezone.utc


def test_schema_field_creation():
    """Test creating a SchemaField instance."""
    schema_field = SchemaField(
        field_name="test_column",
        field_type="numeric",
        data_type="float",
        inferred_dtype="float64",
        unique_values=100,
        missing_values=5,
        example_values=[1.0, 2.0, 3.0],
        is_constant=False,
        is_high_cardinality=True)

    assert schema_field.field_name == "test_column"
    assert schema_field.field_type == "numeric"
    assert schema_field.data_type == "float"
    assert schema_field.inferred_dtype == "float64"
    assert schema_field.unique_values == 100
    assert schema_field.missing_values == 5
    assert schema_field.example_values == [1.0, 2.0, 3.0]
    assert schema_field.is_constant is False
    assert schema_field.is_high_cardinality is True


def test_schema_field_validation():
    """Test SchemaField validation."""
    # Test with invalid field type
    with pytest.raises(ValueError):
        SchemaField(
            field_name="test_column",
            field_type="invalid_type",  # Invalid field type
            data_type="float",
            inferred_dtype="float64",
            unique_values=100,
            missing_values=5,
            example_values=[1.0, 2.0, 3.0],
            is_constant=False,
            is_high_cardinality=True)


def test_ai_summary_creation():
    """Test creating an AISummary instance."""
    current_time = get_current_time()
    ai_summary = AISummary(
        overview="Test overview",
        issues=["Issue 1", "Issue 2"],
        relationships=["Relationship 1", "Relationship 2"],
        suggestions=["Suggestion 1", "Suggestion 2"],
        rawMarkdown="# Test Analysis\n\nThis is a test analysis.",
        createdAt=current_time)

    assert ai_summary.overview == "Test overview"
    assert ai_summary.issues == ["Issue 1", "Issue 2"]
    assert ai_summary.relationships == ["Relationship 1", "Relationship 2"]
    assert ai_summary.suggestions == ["Suggestion 1", "Suggestion 2"]
    assert ai_summary.rawMarkdown == "# Test Analysis\n\nThis is a test analysis."
    assert ai_summary.createdAt == current_time


def test_user_data_creation():
    """Test creating a UserData instance."""
    current_time = get_current_time()
    schema_field = SchemaField(
        field_name="test_column",
        field_type="numeric",
        data_type="float",
        inferred_dtype="float64",
        unique_values=100,
        missing_values=5,
        example_values=[1.0, 2.0, 3.0],
        is_constant=False,
        is_high_cardinality=True
    )
    ai_summary = AISummary(
        overview="Test overview",
        issues=["Issue 1", "Issue 2"],
        relationships=["Relationship 1", "Relationship 2"],
        suggestions=["Suggestion 1", "Suggestion 2"],
        rawMarkdown="# Test Analysis\n\nThis is a test analysis.",
        createdAt=current_time
    )

    user_data = UserData(
        user_id="test_user_123",
        filename="test.csv",
        s3_url="https://example.com/test.csv",
        num_rows=100,
        num_columns=1,
        data_schema=[schema_field],
        created_at=current_time,
        updated_at=current_time,
        aiSummary=ai_summary,
        original_filename="test.csv"
    )

    assert user_data.user_id == "test_user_123"
    assert user_data.filename == "test.csv"
    assert user_data.s3_url == "https://example.com/test.csv"
    assert user_data.num_rows == 100
    assert user_data.num_columns == 1
    assert len(user_data.data_schema) == 1
    assert user_data.data_schema[0].field_name == "test_column"
    assert user_data.created_at == current_time
    assert user_data.updated_at == current_time
    assert user_data.aiSummary == ai_summary


def test_user_data_default_timestamps():
    """Test that UserData automatically sets timestamps."""
    user_data = UserData(
        user_id="test-user",
        filename="test.csv",
        original_filename="test.csv",
        num_rows=10,
        num_columns=2,
        s3_url="https://example.com/test.csv",
        data_schema=[],
    )

    assert isinstance(user_data.created_at, datetime)
    assert isinstance(user_data.updated_at, datetime)
    assert user_data.created_at.tzinfo == timezone.utc
    assert user_data.updated_at.tzinfo == timezone.utc


def test_user_data_optional_ai_summary():
    """Test that UserData can be created without an AI summary."""
    user_data = UserData(
        user_id="test_user",
        filename="test.csv",
        original_filename="test.csv",
        num_rows=100,
        num_columns=1,
        s3_url="https://example.com/test.csv",
        data_schema=[],
    )

    assert user_data.aiSummary is None


def test_user_data_model_settings():
    """Test UserData model settings."""
    assert UserData.Settings.name == "user_data"
    assert "user_id" in UserData.Settings.indexes
    assert "created_at" in UserData.Settings.indexes


def test_user_data_model_config():
    """Test UserData model configuration."""
    assert UserData.model_config["populate_by_name"] is True
    assert UserData.model_config["arbitrary_types_allowed"] is True


def test_schema_field_with_different_data_types():
    """Test SchemaField with different data types."""
    # Test with numeric data
    numeric_field = SchemaField(
        field_name="numeric",
        field_type="numeric",
        data_type="float",
        inferred_dtype="float64",
        unique_values=10,
        missing_values=0,
        example_values=[1.0, 2.0],
        is_constant=False,
        is_high_cardinality=False
    )
    assert numeric_field.field_type == "numeric"

    # Test with categorical data
    categorical_field = SchemaField(
        field_name="category",
        field_type="categorical",
        data_type="string",
        inferred_dtype="object",
        unique_values=5,
        missing_values=0,
        example_values=["A", "B"],
        is_constant=False,
        is_high_cardinality=False
    )
    assert categorical_field.field_type == "categorical"

    # Test with datetime data
    datetime_field = SchemaField(
        field_name="date",
        field_type="datetime",
        data_type="datetime",
        inferred_dtype="datetime64[ns]",
        unique_values=30,
        missing_values=0,
        example_values=["2024-01-01"],
        is_constant=False,
        is_high_cardinality=True
    )
    assert datetime_field.field_type == "datetime"


def test_user_data_validation():
    """Test UserData validation."""
    # Test with invalid user_id
    with pytest.raises(ValueError):
        UserData(
        user_id="",  # Empty user_id
            filename="test.csv",
        s3_url="https://example.com/test.csv",
        data_schema=[],
    )

    # Test with invalid s3_url
    with pytest.raises(ValueError):
        UserData(
        user_id="test_user",
        filename="test.csv",
        original_filename="test.csv",
        s3_url="invalid_url",  # Invalid URL
            num_rows=100,
        data_schema=[],
    )

    # Test with negative num_rows
    with pytest.raises(ValueError):
        UserData(
        user_id="test_user",
        filename="test.csv",
        original_filename="test.csv",
        s3_url="https://example.com/test.csv",
        num_rows=-1,  # Negative number of rows
            num_columns=1,
        data_schema=[],
    )
