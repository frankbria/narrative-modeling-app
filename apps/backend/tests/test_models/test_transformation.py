"""
Tests for TransformationConfig model - Unit tests only (no database required).

Tests cover:
- TransformationStep validation
- TransformationPreview model
- TransformationValidation model
- TransformationConfig model
- Helper methods
- Edge cases and error conditions
"""

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError
from app.models.transformation import (
    TransformationConfig,
    TransformationStep,
    TransformationPreview,
    TransformationValidation,
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


class TestTransformationStep:
    """Tests for TransformationStep model."""

    def test_create_step_with_valid_data(self):
        """Test creating TransformationStep with valid data."""
        step = TransformationStep(
            transformation_type="encode",
            column="category",
            parameters={"method": "one_hot"}
        )

        assert step.transformation_type == "encode"
        assert step.column == "category"
        assert step.parameters == {"method": "one_hot"}
        assert step.is_valid is True
        assert step.validation_errors == []

    def test_create_step_with_multiple_columns(self):
        """Test creating TransformationStep with multiple columns."""
        step = TransformationStep(
            transformation_type="scale",
            columns=["age", "income"],
            parameters={"method": "standard"}
        )

        assert step.transformation_type == "scale"
        assert step.columns == ["age", "income"]
        assert step.column is None

    def test_step_validates_transformation_type(self):
        """Test that invalid transformation_type raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            TransformationStep(
                transformation_type="invalid_type",
                column="test",
                parameters={}
            )
        assert "transformation_type must be one of" in str(exc_info.value)

    def test_step_validates_column_required(self):
        """Test that column is required for certain transformation types."""
        # Should raise error for transformation types that require column
        with pytest.raises(ValidationError):
            TransformationStep(
                transformation_type="encode",
                parameters={}
            )

    def test_step_accepts_no_column_for_some_types(self):
        """Test that some transformation types don't require column."""
        step = TransformationStep(
            transformation_type="drop_duplicates",
            parameters={}
        )
        assert step.transformation_type == "drop_duplicates"
        assert step.column is None

    def test_step_all_transformation_types(self):
        """Test all valid transformation_type values."""
        valid_types = [
            'encode', 'scale', 'impute', 'drop_missing',
            'filter', 'aggregate', 'derive', 'normalize',
            'standardize', 'one_hot_encode', 'label_encode',
            'fill_missing', 'drop_duplicates', 'outlier_removal'
        ]

        for trans_type in valid_types:
            # Use drop_duplicates pattern for types that don't require column
            if trans_type in ['drop_duplicates', 'filter', 'aggregate', 'outlier_removal']:
                step = TransformationStep(
                    transformation_type=trans_type,
                    parameters={}
                )
            else:
                step = TransformationStep(
                    transformation_type=trans_type,
                    column="test_col",
                    parameters={}
                )
            assert step.transformation_type == trans_type

    def test_step_with_impact_tracking(self):
        """Test TransformationStep with impact tracking fields."""
        step = TransformationStep(
            transformation_type="drop_missing",
            parameters={},
            rows_affected=100,
            data_loss_percentage=10.5
        )

        assert step.rows_affected == 100
        assert step.data_loss_percentage == 10.5

    def test_step_auto_timestamp(self):
        """Test that applied_at auto-generates."""
        step = TransformationStep(
            transformation_type="drop_duplicates",
            parameters={}
        )

        assert isinstance(step.applied_at, datetime)
        assert step.applied_at.tzinfo == timezone.utc


class TestTransformationPreview:
    """Tests for TransformationPreview model."""

    def test_create_preview_with_defaults(self):
        """Test creating TransformationPreview with default values."""
        preview = TransformationPreview(
            estimated_rows_affected=500
        )

        assert preview.sample_before == []
        assert preview.sample_after == []
        assert preview.affected_columns == []
        assert preview.estimated_rows_affected == 500
        assert preview.estimated_data_loss == 0.0
        assert preview.warnings == []

    def test_create_preview_with_all_fields(self):
        """Test creating TransformationPreview with all fields."""
        preview = TransformationPreview(
            sample_before=[{"age": 25}, {"age": None}],
            sample_after=[{"age": 25}, {"age": 30}],
            affected_columns=["age"],
            estimated_rows_affected=100,
            estimated_data_loss=5.0,
            warnings=["10 rows will be dropped"]
        )

        assert len(preview.sample_before) == 2
        assert len(preview.sample_after) == 2
        assert preview.affected_columns == ["age"]
        assert preview.estimated_data_loss == 5.0
        assert len(preview.warnings) == 1

    def test_preview_auto_timestamp(self):
        """Test that generated_at auto-generates."""
        preview = TransformationPreview(
            estimated_rows_affected=100
        )

        assert isinstance(preview.generated_at, datetime)
        assert preview.generated_at.tzinfo == timezone.utc


class TestTransformationValidation:
    """Tests for TransformationValidation model."""

    def test_create_validation_valid(self):
        """Test creating TransformationValidation for valid config."""
        validation = TransformationValidation(
            is_valid=True,
            errors=[],
            warnings=["Consider data backup"]
        )

        assert validation.is_valid is True
        assert validation.errors == []
        assert len(validation.warnings) == 1

    def test_create_validation_invalid(self):
        """Test creating TransformationValidation for invalid config."""
        validation = TransformationValidation(
            is_valid=False,
            errors=["Column 'age' not found", "Invalid parameter"],
            warnings=[]
        )

        assert validation.is_valid is False
        assert len(validation.errors) == 2

    def test_validation_with_detailed_checks(self):
        """Test TransformationValidation with detailed validation checks."""
        validation = TransformationValidation(
            is_valid=True,
            parameter_validation={"step_0": True, "step_1": True},
            data_type_compatibility={"age": True, "income": False},
            dependency_validation=True
        )

        assert validation.parameter_validation["step_0"] is True
        assert validation.data_type_compatibility["income"] is False
        assert validation.dependency_validation is True

    def test_validation_auto_timestamp(self):
        """Test that validated_at auto-generates."""
        validation = TransformationValidation(
            is_valid=True
        )

        assert isinstance(validation.validated_at, datetime)
        assert validation.validated_at.tzinfo == timezone.utc


class TestTransformationConfig:
    """Tests for TransformationConfig model."""

    def test_model_settings(self):
        """Test TransformationConfig model settings."""
        assert TransformationConfig.Settings.name == "transformation_configs"
        assert "user_id" in TransformationConfig.Settings.indexes
        assert "dataset_id" in TransformationConfig.Settings.indexes
        assert "config_id" in TransformationConfig.Settings.indexes

    def test_model_config(self):
        """Test TransformationConfig model configuration."""
        assert TransformationConfig.model_config["populate_by_name"] is True
        assert TransformationConfig.model_config["arbitrary_types_allowed"] is True

    def test_create_config_minimal(self):
        """Test creating TransformationConfig with minimal fields."""
        config = TransformationConfig.model_construct(
            user_id="user_123",
            dataset_id="dataset_456",
            config_id="config_789"
        )

        assert config.user_id == "user_123"
        assert config.dataset_id == "dataset_456"
        assert config.config_id == "config_789"
        assert config.transformation_steps == []
        assert config.is_applied is False
        assert config.total_transformations == 0

    def test_config_default_version(self):
        """Test that version defaults to 1.0.0."""
        config = TransformationConfig.model_construct(
            user_id="user_123",
            dataset_id="dataset_456",
            config_id="config_789"
        )

        assert config.version == "1.0.0"

    def test_config_auto_timestamps(self):
        """Test that timestamps auto-generate."""
        config = TransformationConfig.model_construct(
            user_id="user_123",
            dataset_id="dataset_456",
            config_id="config_789"
        )

        assert isinstance(config.created_at, datetime)
        assert isinstance(config.updated_at, datetime)


class TestTransformationConfigHelperMethods:
    """Test helper methods for TransformationConfig."""

    def test_add_transformation_step(self):
        """Test add_transformation_step() method."""
        config = TransformationConfig.model_construct(
            user_id="user_123",
            dataset_id="dataset_456",
            config_id="config_789",
            transformation_steps=[],
            total_transformations=0
        )

        step = config.add_transformation_step(
            transformation_type="encode",
            column="category",
            parameters={"method": "one_hot"}
        )

        assert isinstance(step, TransformationStep)
        assert len(config.transformation_steps) == 1
        assert config.total_transformations == 1
        assert step.transformation_type == "encode"

    def test_add_multiple_transformation_steps(self):
        """Test adding multiple transformation steps."""
        config = TransformationConfig.model_construct(
            user_id="user_123",
            dataset_id="dataset_456",
            config_id="config_789",
            transformation_steps=[],
            total_transformations=0
        )

        config.add_transformation_step("encode", column="cat1", parameters={})
        config.add_transformation_step("scale", column="num1", parameters={})
        config.add_transformation_step("impute", column="num2", parameters={})

        assert len(config.transformation_steps) == 3
        assert config.total_transformations == 3

    def test_update_timestamp_method(self):
        """Test update_timestamp() method."""
        config = TransformationConfig.model_construct(
            user_id="user_123",
            dataset_id="dataset_456",
            config_id="config_789"
        )

        original_updated_at = config.updated_at
        import time
        time.sleep(0.01)
        config.update_timestamp()

        assert config.updated_at > original_updated_at

    def test_mark_applied_method(self):
        """Test mark_applied() method."""
        config = TransformationConfig.model_construct(
            user_id="user_123",
            dataset_id="dataset_456",
            config_id="config_789"
        )

        assert config.is_applied is False
        assert config.applied_at is None
        assert config.current_file_path is None

        config.mark_applied("s3://bucket/transformed.csv")

        assert config.is_applied is True
        assert isinstance(config.applied_at, datetime)
        assert config.current_file_path == "s3://bucket/transformed.csv"

    def test_get_transformation_history(self):
        """Test get_transformation_history() method."""
        step1 = TransformationStep(
            transformation_type="encode",
            column="category",
            parameters={"method": "one_hot"},
            rows_affected=1000,
            data_loss_percentage=0.0
        )
        step2 = TransformationStep(
            transformation_type="drop_missing",
            parameters={},
            rows_affected=50,
            data_loss_percentage=5.0
        )

        config = TransformationConfig.model_construct(
            user_id="user_123",
            dataset_id="dataset_456",
            config_id="config_789",
            transformation_steps=[step1, step2]
        )

        history = config.get_transformation_history()

        assert len(history) == 2
        assert history[0]["type"] == "encode"
        assert history[0]["column"] == "category"
        assert history[1]["type"] == "drop_missing"
        assert history[1]["data_loss_percentage"] == 5.0

    def test_validate_transformations_method(self):
        """Test validate_transformations() method."""
        step1 = TransformationStep(
            transformation_type="encode",
            column="category",
            parameters={}
        )
        step2 = TransformationStep(
            transformation_type="scale",
            column="age",
            parameters={}
        )

        config = TransformationConfig.model_construct(
            user_id="user_123",
            dataset_id="dataset_456",
            config_id="config_789",
            transformation_steps=[step1, step2],
            total_data_loss=0.0
        )

        validation = config.validate_transformations()

        assert isinstance(validation, TransformationValidation)
        assert validation.is_valid is True
        assert len(validation.errors) == 0

    def test_validate_transformations_with_high_data_loss(self):
        """Test validation warns about high data loss."""
        step = TransformationStep(
            transformation_type="drop_missing",
            parameters={},
            data_loss_percentage=60.0
        )

        config = TransformationConfig.model_construct(
            user_id="user_123",
            dataset_id="dataset_456",
            config_id="config_789",
            transformation_steps=[step],
            total_data_loss=60.0
        )

        validation = config.validate_transformations()

        assert len(validation.warnings) > 0
        assert any("data loss" in warning.lower() for warning in validation.warnings)

    def test_validate_transformations_detects_errors(self):
        """Test validation detects invalid steps."""
        # Create step with validation errors
        step = TransformationStep(
            transformation_type="drop_duplicates",
            parameters={},
            is_valid=False,
            validation_errors=["Parameter X is invalid"]
        )

        config = TransformationConfig.model_construct(
            user_id="user_123",
            dataset_id="dataset_456",
            config_id="config_789",
            transformation_steps=[step],
            total_data_loss=0.0
        )

        validation = config.validate_transformations()

        assert validation.is_valid is False
        assert len(validation.errors) > 0

    def test_clear_transformations_method(self):
        """Test clear_transformations() method."""
        step1 = TransformationStep(
            transformation_type="encode",
            column="category",
            parameters={}
        )
        step2 = TransformationStep(
            transformation_type="scale",
            column="age",
            parameters={}
        )

        config = TransformationConfig.model_construct(
            user_id="user_123",
            dataset_id="dataset_456",
            config_id="config_789",
            transformation_steps=[step1, step2],
            total_transformations=2,
            total_data_loss=10.0,
            is_applied=True,
            applied_at=get_current_time()
        )

        config.clear_transformations()

        assert config.transformation_steps == []
        assert config.total_transformations == 0
        assert config.total_data_loss == 0.0
        assert config.is_applied is False
        assert config.applied_at is None
        assert config.validation_result is None

    def test_get_affected_columns_method(self):
        """Test get_affected_columns() method."""
        step1 = TransformationStep(
            transformation_type="encode",
            column="category",
            parameters={}
        )
        step2 = TransformationStep(
            transformation_type="scale",
            columns=["age", "income"],
            parameters={}
        )
        step3 = TransformationStep(
            transformation_type="drop_duplicates",
            parameters={}
        )

        config = TransformationConfig.model_construct(
            user_id="user_123",
            dataset_id="dataset_456",
            config_id="config_789",
            transformation_steps=[step1, step2, step3]
        )

        affected = config.get_affected_columns()

        assert len(affected) == 3
        assert "category" in affected
        assert "age" in affected
        assert "income" in affected

    def test_config_with_preview(self):
        """Test TransformationConfig with preview."""
        preview = TransformationPreview(
            sample_before=[{"age": 25}],
            sample_after=[{"age": 25}],
            affected_columns=["age"],
            estimated_rows_affected=100,
            estimated_data_loss=0.0
        )

        config = TransformationConfig.model_construct(
            user_id="user_123",
            dataset_id="dataset_456",
            config_id="config_789",
            last_preview=preview
        )

        assert config.last_preview is not None
        assert len(config.last_preview.sample_before) == 1
        assert config.last_preview.estimated_rows_affected == 100

    def test_config_with_validation_result(self):
        """Test TransformationConfig with validation result."""
        validation = TransformationValidation(
            is_valid=True,
            errors=[],
            warnings=["Consider data backup"]
        )

        config = TransformationConfig.model_construct(
            user_id="user_123",
            dataset_id="dataset_456",
            config_id="config_789",
            validation_result=validation,
            last_validated_at=get_current_time()
        )

        assert config.validation_result is not None
        assert config.validation_result.is_valid is True
        assert isinstance(config.last_validated_at, datetime)

    def test_config_versioning(self):
        """Test versioning fields."""
        config = TransformationConfig.model_construct(
            user_id="user_123",
            dataset_id="dataset_456",
            config_id="config_789",
            version="2.1.0",
            parent_config_id="config_000"
        )

        assert config.version == "2.1.0"
        assert config.parent_config_id == "config_000"


class TestTransformationConfigEdgeCases:
    """Test edge cases and complex scenarios."""

    def test_empty_transformation_history(self):
        """Test get_transformation_history with no steps."""
        config = TransformationConfig.model_construct(
            user_id="user_123",
            dataset_id="dataset_456",
            config_id="config_789",
            transformation_steps=[]
        )

        history = config.get_transformation_history()
        assert history == []

    def test_get_affected_columns_with_no_columns(self):
        """Test get_affected_columns with no column-specific transformations."""
        step = TransformationStep(
            transformation_type="drop_duplicates",
            parameters={}
        )

        config = TransformationConfig.model_construct(
            user_id="user_123",
            dataset_id="dataset_456",
            config_id="config_789",
            transformation_steps=[step]
        )

        affected = config.get_affected_columns()
        assert affected == []

    def test_multiple_validations(self):
        """Test running validate_transformations multiple times."""
        step = TransformationStep(
            transformation_type="encode",
            column="category",
            parameters={}
        )

        config = TransformationConfig.model_construct(
            user_id="user_123",
            dataset_id="dataset_456",
            config_id="config_789",
            transformation_steps=[step],
            total_data_loss=0.0
        )

        validation1 = config.validate_transformations()
        first_validated_at = config.last_validated_at

        import time
        time.sleep(0.01)

        validation2 = config.validate_transformations()
        second_validated_at = config.last_validated_at

        assert validation1.is_valid == validation2.is_valid
        assert second_validated_at > first_validated_at

    def test_cumulative_data_loss_warning(self):
        """Test that cumulative data loss triggers warning."""
        config = TransformationConfig.model_construct(
            user_id="user_123",
            dataset_id="dataset_456",
            config_id="config_789",
            transformation_steps=[],
            total_data_loss=55.0  # Over 50%
        )

        validation = config.validate_transformations()

        # Should have warning about total data loss
        assert any("Total data loss" in warning or "50%" in warning
                  for warning in validation.warnings)
