"""
Tests for DatasetMetadata model - Unit tests only (no database required).

Tests cover:
- Model creation and validation using dict validation
- SchemaField validation
- AISummary model
- PIIReport model
- Helper methods
- Edge cases and error conditions
"""

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError
from app.models.dataset import (
    DatasetMetadata,
    SchemaField,
    AISummary,
    PIIReport,
    get_current_time
)


class TestGetCurrentTime:
    """Tests for get_current_time utility function."""

    def test_get_current_time_returns_datetime(self):
        """Test that get_current_time returns a datetime object."""
        current_time = get_current_time()
        assert isinstance(current_time, datetime)

    def test_get_current_time_has_utc_timezone(self):
        """Test that returned datetime has UTC timezone."""
        current_time = get_current_time()
        assert current_time.tzinfo == timezone.utc


class TestSchemaField:
    """Tests for SchemaField model."""

    def test_create_schema_field_with_valid_data(self):
        """Test creating a SchemaField with all valid data."""
        field = SchemaField(
            field_name="test_column",
            field_type="numeric",
            data_type="ratio",
            inferred_dtype="float64",
            unique_values=100,
            missing_values=5,
            example_values=[1.0, 2.0, 3.0],
            is_constant=False,
            is_high_cardinality=True
        )

        assert field.field_name == "test_column"
        assert field.field_type == "numeric"
        assert field.data_type == "ratio"
        assert field.inferred_dtype == "float64"
        assert field.unique_values == 100
        assert field.missing_values == 5
        assert field.example_values == [1.0, 2.0, 3.0]
        assert field.is_constant is False
        assert field.is_high_cardinality is True

    def test_create_schema_field_with_optional_data_type(self):
        """Test creating SchemaField without data_type (optional field)."""
        field = SchemaField(
            field_name="test_column",
            field_type="text",
            inferred_dtype="object",
            unique_values=50,
            missing_values=0,
            example_values=["a", "b", "c"]
        )

        assert field.data_type is None
        assert field.field_name == "test_column"

    def test_schema_field_validates_field_type(self):
        """Test that invalid field_type raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SchemaField(
                field_name="test",
                field_type="invalid_type",
                inferred_dtype="object",
                unique_values=10,
                missing_values=0,
                example_values=[]
            )
        assert "field_type must be one of" in str(exc_info.value)

    def test_schema_field_validates_data_type(self):
        """Test that invalid data_type raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SchemaField(
                field_name="test",
                field_type="numeric",
                data_type="invalid_scale",
                inferred_dtype="float64",
                unique_values=10,
                missing_values=0,
                example_values=[]
            )
        assert "data_type must be one of" in str(exc_info.value)

    def test_schema_field_negative_counts_rejected(self):
        """Test that negative unique_values and missing_values are rejected."""
        with pytest.raises(ValidationError):
            SchemaField(
                field_name="test",
                field_type="numeric",
                inferred_dtype="int64",
                unique_values=-1,  # Invalid
                missing_values=0,
                example_values=[]
            )

        with pytest.raises(ValidationError):
            SchemaField(
                field_name="test",
                field_type="numeric",
                inferred_dtype="int64",
                unique_values=10,
                missing_values=-1,  # Invalid
                example_values=[]
            )

    def test_schema_field_all_types(self):
        """Test all valid field_type values."""
        valid_types = ['numeric', 'text', 'boolean', 'datetime', 'categorical']

        for field_type in valid_types:
            field = SchemaField(
                field_name=f"{field_type}_field",
                field_type=field_type,
                inferred_dtype="object",
                unique_values=10,
                missing_values=0,
                example_values=[]
            )
            assert field.field_type == field_type

    def test_schema_field_all_data_types(self):
        """Test all valid data_type values."""
        valid_data_types = ['nominal', 'ordinal', 'interval', 'ratio']

        for data_type in valid_data_types:
            field = SchemaField(
                field_name="test",
                field_type="numeric",
                data_type=data_type,
                inferred_dtype="float64",
                unique_values=10,
                missing_values=0,
                example_values=[]
            )
            assert field.data_type == data_type


class TestAISummary:
    """Tests for AISummary model."""

    def test_create_ai_summary_with_all_fields(self):
        """Test creating AISummary with all fields."""
        current_time = get_current_time()
        summary = AISummary(
            overview="Dataset contains sales data",
            issues=["Missing values in price column", "Duplicate entries"],
            relationships=["Sales correlate with temperature"],
            suggestions=["Remove duplicates", "Impute missing values"],
            rawMarkdown="# Analysis\n\nDetailed analysis here.",
            createdAt=current_time
        )

        assert summary.overview == "Dataset contains sales data"
        assert len(summary.issues) == 2
        assert len(summary.relationships) == 1
        assert len(summary.suggestions) == 2
        assert summary.raw_markdown == "# Analysis\n\nDetailed analysis here."
        assert summary.created_at == current_time

    def test_ai_summary_alias_fields(self):
        """Test that alias fields work correctly."""
        summary = AISummary(
            overview="Test",
            rawMarkdown="# Test"
        )

        # Both alias and field name should work
        assert summary.raw_markdown == "# Test"

    def test_ai_summary_default_lists(self):
        """Test that lists default to empty."""
        summary = AISummary(
            overview="Test overview",
            rawMarkdown="# Test"
        )

        assert summary.issues == []
        assert summary.relationships == []
        assert summary.suggestions == []

    def test_ai_summary_auto_timestamp(self):
        """Test that created_at auto-generates."""
        summary = AISummary(
            overview="Test",
            rawMarkdown="# Test"
        )

        assert isinstance(summary.created_at, datetime)
        assert summary.created_at.tzinfo == timezone.utc


class TestPIIReport:
    """Tests for PIIReport model."""

    def test_create_pii_report_with_defaults(self):
        """Test creating PIIReport with default values."""
        report = PIIReport()

        assert report.contains_pii is False
        assert report.pii_fields == []
        assert report.risk_level == "low"
        assert report.detection_details == {}
        assert report.masked is False
        assert report.masked_at is None

    def test_create_pii_report_with_pii_detected(self):
        """Test creating PIIReport when PII is detected."""
        report = PIIReport(
            contains_pii=True,
            pii_fields=["email", "ssn"],
            risk_level="high",
            detection_details={"email": ["john@example.com"], "ssn": ["***-**-****"]},
            masked=True,
            masked_at=get_current_time()
        )

        assert report.contains_pii is True
        assert len(report.pii_fields) == 2
        assert report.risk_level == "high"
        assert "email" in report.detection_details
        assert report.masked is True
        assert isinstance(report.masked_at, datetime)

    def test_pii_report_validates_risk_level(self):
        """Test that invalid risk_level raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            PIIReport(risk_level="critical")  # Invalid
        assert "risk_level must be one of" in str(exc_info.value)

    def test_pii_report_all_risk_levels(self):
        """Test all valid risk_level values."""
        valid_levels = ['low', 'medium', 'high']

        for level in valid_levels:
            report = PIIReport(risk_level=level)
            assert report.risk_level == level


class TestDatasetMetadata:
    """Tests for DatasetMetadata model - uses dict validation to avoid DB."""

    def test_model_settings(self):
        """Test DatasetMetadata model settings."""
        assert DatasetMetadata.Settings.name == "dataset_metadata"
        assert "user_id" in DatasetMetadata.Settings.indexes
        assert "dataset_id" in DatasetMetadata.Settings.indexes
        assert "created_at" in DatasetMetadata.Settings.indexes

    def test_model_config(self):
        """Test DatasetMetadata model configuration."""
        assert DatasetMetadata.model_config["populate_by_name"] is True
        assert DatasetMetadata.model_config["arbitrary_types_allowed"] is True

    def test_validates_file_type(self):
        """Test that invalid file_type raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            DatasetMetadata.model_validate({
                "user_id": "user_123",
                "dataset_id": "dataset_456",
                "filename": "data.txt",
                "original_filename": "data.txt",
                "file_type": "txt",  # Invalid
                "file_path": "data.txt",
                "s3_url": "https://s3.amazonaws.com/bucket/data.txt",
                "num_rows": 100,
                "num_columns": 5
            })
        assert "file_type must be one of" in str(exc_info.value)

    def test_negative_dimensions_rejected(self):
        """Test that negative dimensions are rejected."""
        with pytest.raises(ValidationError):
            DatasetMetadata.model_validate({
                "user_id": "user_123",
                "dataset_id": "dataset_456",
                "filename": "data.csv",
                "original_filename": "data.csv",
                "file_type": "csv",
                "file_path": "data.csv",
                "s3_url": "https://s3.amazonaws.com/bucket/data.csv",
                "num_rows": -1,  # Invalid
                "num_columns": 5
            })

        with pytest.raises(ValidationError):
            DatasetMetadata.model_validate({
                "user_id": "user_123",
                "dataset_id": "dataset_456",
                "filename": "data.csv",
                "original_filename": "data.csv",
                "file_type": "csv",
                "file_path": "data.csv",
                "s3_url": "https://s3.amazonaws.com/bucket/data.csv",
                "num_rows": 100,
                "num_columns": -1  # Invalid
            })

    def test_default_version(self):
        """Test that version defaults to 1.0.0."""
        metadata = DatasetMetadata.model_construct(
            user_id="user_123",
            dataset_id="dataset_456",
            filename="data.csv",
            original_filename="data.csv",
            file_type="csv",
            file_path="data.csv",
            s3_url="https://s3.amazonaws.com/bucket/data.csv",
            num_rows=100,
            num_columns=5
        )

        assert metadata.version == "1.0.0"

    def test_all_file_types(self):
        """Test all valid file_type values."""
        valid_types = ['csv', 'excel', 'json', 'parquet', 'xlsx', 'xls']

        for file_type in valid_types:
            metadata = DatasetMetadata.model_construct(
                user_id="user_123",
                dataset_id=f"dataset_{file_type}",
                filename=f"data.{file_type}",
                original_filename=f"data.{file_type}",
                file_type=file_type,
                file_path=f"data.{file_type}",
                s3_url=f"https://s3.amazonaws.com/bucket/data.{file_type}",
                num_rows=100,
                num_columns=5
            )
            assert metadata.file_type == file_type.lower()


class TestDatasetMetadataHelperMethods:
    """Test helper methods using constructed objects."""

    def test_update_timestamp_method(self):
        """Test update_timestamp() method."""
        metadata = DatasetMetadata.model_construct(
            user_id="user_123",
            dataset_id="dataset_456",
            filename="data.csv",
            original_filename="data.csv",
            file_type="csv",
            file_path="data.csv",
            s3_url="https://s3.amazonaws.com/bucket/data.csv",
            num_rows=100,
            num_columns=5
        )

        original_updated_at = metadata.updated_at
        # Small delay to ensure timestamp difference
        import time
        time.sleep(0.01)
        metadata.update_timestamp()

        assert metadata.updated_at > original_updated_at

    def test_mark_processed_method(self):
        """Test mark_processed() method."""
        metadata = DatasetMetadata.model_construct(
            user_id="user_123",
            dataset_id="dataset_456",
            filename="data.csv",
            original_filename="data.csv",
            file_type="csv",
            file_path="data.csv",
            s3_url="https://s3.amazonaws.com/bucket/data.csv",
            num_rows=100,
            num_columns=5
        )

        assert metadata.is_processed is False
        assert metadata.processed_at is None

        metadata.mark_processed()

        assert metadata.is_processed is True
        assert isinstance(metadata.processed_at, datetime)

    def test_get_column_schema_method(self):
        """Test get_column_schema() method."""
        field1 = SchemaField(
            field_name="price",
            field_type="numeric",
            inferred_dtype="float64",
            unique_values=100,
            missing_values=0,
            example_values=[10.0, 20.0]
        )
        field2 = SchemaField(
            field_name="category",
            field_type="categorical",
            inferred_dtype="object",
            unique_values=5,
            missing_values=0,
            example_values=["A", "B"]
        )

        metadata = DatasetMetadata.model_construct(
            user_id="user_123",
            dataset_id="dataset_456",
            filename="data.csv",
            original_filename="data.csv",
            file_type="csv",
            file_path="data.csv",
            s3_url="https://s3.amazonaws.com/bucket/data.csv",
            num_rows=100,
            num_columns=2,
            data_schema=[field1, field2]
        )

        # Test existing column
        price_schema = metadata.get_column_schema("price")
        assert price_schema is not None
        assert price_schema.field_name == "price"
        assert price_schema.field_type == "numeric"

        # Test non-existing column
        missing_schema = metadata.get_column_schema("nonexistent")
        assert missing_schema is None

    def test_has_pii_method(self):
        """Test has_pii() method."""
        # No PII report
        metadata_no_pii = DatasetMetadata.model_construct(
            user_id="user_123",
            dataset_id="dataset_456",
            filename="data.csv",
            original_filename="data.csv",
            file_type="csv",
            file_path="data.csv",
            s3_url="https://s3.amazonaws.com/bucket/data.csv",
            num_rows=100,
            num_columns=5
        )
        assert metadata_no_pii.has_pii() is False

        # PII report but no PII detected
        metadata_no_pii_detected = DatasetMetadata.model_construct(
            user_id="user_123",
            dataset_id="dataset_456",
            filename="data.csv",
            original_filename="data.csv",
            file_type="csv",
            file_path="data.csv",
            s3_url="https://s3.amazonaws.com/bucket/data.csv",
            num_rows=100,
            num_columns=5,
            pii_report=PIIReport(contains_pii=False)
        )
        assert metadata_no_pii_detected.has_pii() is False

        # PII detected
        metadata_with_pii = DatasetMetadata.model_construct(
            user_id="user_123",
            dataset_id="dataset_456",
            filename="data.csv",
            original_filename="data.csv",
            file_type="csv",
            file_path="data.csv",
            s3_url="https://s3.amazonaws.com/bucket/data.csv",
            num_rows=100,
            num_columns=5,
            pii_report=PIIReport(contains_pii=True)
        )
        assert metadata_with_pii.has_pii() is True

    def test_get_pii_risk_level_method(self):
        """Test get_pii_risk_level() method."""
        # No PII report
        metadata_no_report = DatasetMetadata.model_construct(
            user_id="user_123",
            dataset_id="dataset_456",
            filename="data.csv",
            original_filename="data.csv",
            file_type="csv",
            file_path="data.csv",
            s3_url="https://s3.amazonaws.com/bucket/data.csv",
            num_rows=100,
            num_columns=5
        )
        assert metadata_no_report.get_pii_risk_level() == "low"

        # With PII report
        metadata_with_report = DatasetMetadata.model_construct(
            user_id="user_123",
            dataset_id="dataset_456",
            filename="data.csv",
            original_filename="data.csv",
            file_type="csv",
            file_path="data.csv",
            s3_url="https://s3.amazonaws.com/bucket/data.csv",
            num_rows=100,
            num_columns=5,
            pii_report=PIIReport(risk_level="high")
        )
        assert metadata_with_report.get_pii_risk_level() == "high"
