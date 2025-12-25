"""
Unit tests for BulkTransformationService.

Tests column selection patterns, preview operations, and job management
without requiring a database connection.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import pandas as pd
import numpy as np

from app.services.bulk_transformation_service import BulkTransformationService
from app.models.bulk_transformation import (
    BulkTransformationJob,
    BulkTransformationProgress,
    BulkTransformationResult,
    ColumnResult,
    BulkJobStatus,
    PatternType,
    ColumnSelectionPattern,
)
from app.models.dataset import DatasetMetadata, SchemaField
from app.services.exceptions import NotFoundError, OperationError


@pytest.fixture
def bulk_service():
    """Create a BulkTransformationService instance."""
    return BulkTransformationService()


@pytest.fixture
def mock_dataset():
    """Create a mock dataset with schema fields."""
    dataset = MagicMock(spec=DatasetMetadata)
    dataset.dataset_id = "test-dataset-123"
    dataset.user_id = "user-123"
    dataset.file_path = "s3://bucket/test.parquet"
    dataset.s3_url = "s3://bucket/test.parquet"
    dataset.data_schema = [
        SchemaField(
            field_name="age",
            field_type="numeric",
            data_type="ratio",
            inferred_dtype="int64",
            unique_values=50,
            missing_values=5,
            example_values=[25, 30, 35],
            is_constant=False,
            is_high_cardinality=False,
        ),
        SchemaField(
            field_name="name",
            field_type="text",
            data_type="nominal",
            inferred_dtype="object",
            unique_values=100,
            missing_values=0,
            example_values=["John", "Jane"],
            is_constant=False,
            is_high_cardinality=True,
        ),
        SchemaField(
            field_name="salary",
            field_type="numeric",
            data_type="ratio",
            inferred_dtype="float64",
            unique_values=200,
            missing_values=10,
            example_values=[50000.0, 75000.0],
            is_constant=False,
            is_high_cardinality=False,
        ),
        SchemaField(
            field_name="is_active",
            field_type="boolean",
            data_type="nominal",
            inferred_dtype="bool",
            unique_values=2,
            missing_values=0,
            example_values=[True, False],
            is_constant=False,
            is_high_cardinality=False,
        ),
        SchemaField(
            field_name="created_at",
            field_type="datetime",
            data_type="interval",
            inferred_dtype="datetime64[ns]",
            unique_values=1000,
            missing_values=0,
            example_values=["2024-01-01", "2024-02-01"],
            is_constant=False,
            is_high_cardinality=True,
        ),
        SchemaField(
            field_name="status",
            field_type="categorical",
            data_type="nominal",
            inferred_dtype="object",
            unique_values=3,
            missing_values=0,
            example_values=["active", "pending", "inactive"],
            is_constant=False,
            is_high_cardinality=False,
        ),
        SchemaField(
            field_name="constant_col",
            field_type="text",
            data_type="nominal",
            inferred_dtype="object",
            unique_values=1,
            missing_values=0,
            example_values=["constant"],
            is_constant=True,
            is_high_cardinality=False,
        ),
    ]
    return dataset


@pytest.fixture
def sample_dataframe():
    """Create a sample DataFrame for testing."""
    return pd.DataFrame({
        "age": [25, 30, 35, None, 40],
        "name": ["John", "Jane", "Bob", "Alice", "Charlie"],
        "salary": [50000.0, 75000.0, None, 60000.0, 80000.0],
        "is_active": [True, False, True, True, False],
        "status": ["active", "pending", "active", "inactive", "active"],
    })


class TestColumnSelectionPatterns:
    """Tests for column selection by pattern."""

    @pytest.mark.asyncio
    async def test_select_columns_by_data_type_numeric(self, bulk_service, mock_dataset):
        """Test selecting numeric columns."""
        with patch.object(
            DatasetMetadata, 'find_one', new_callable=AsyncMock
        ) as mock_find:
            mock_find.return_value = mock_dataset

            pattern = ColumnSelectionPattern(
                pattern_type=PatternType.DATA_TYPE,
                criteria={"types": ["numeric"]}
            )

            result = await bulk_service.select_columns_by_pattern(
                user_id="user-123",
                dataset_id="test-dataset-123",
                pattern=pattern
            )

            assert len(result) == 2
            column_names = [col["column_name"] for col in result]
            assert "age" in column_names
            assert "salary" in column_names

    @pytest.mark.asyncio
    async def test_select_columns_by_data_type_multiple(self, bulk_service, mock_dataset):
        """Test selecting multiple data types."""
        with patch.object(
            DatasetMetadata, 'find_one', new_callable=AsyncMock
        ) as mock_find:
            mock_find.return_value = mock_dataset

            pattern = ColumnSelectionPattern(
                pattern_type=PatternType.DATA_TYPE,
                criteria={"types": ["numeric", "text"]}
            )

            result = await bulk_service.select_columns_by_pattern(
                user_id="user-123",
                dataset_id="test-dataset-123",
                pattern=pattern
            )

            assert len(result) == 4  # age, salary, name, constant_col
            column_names = [col["column_name"] for col in result]
            assert "age" in column_names
            assert "salary" in column_names
            assert "name" in column_names

    @pytest.mark.asyncio
    async def test_select_columns_by_name_pattern(self, bulk_service, mock_dataset):
        """Test selecting columns by name pattern."""
        with patch.object(
            DatasetMetadata, 'find_one', new_callable=AsyncMock
        ) as mock_find:
            mock_find.return_value = mock_dataset

            pattern = ColumnSelectionPattern(
                pattern_type=PatternType.NAME_PATTERN,
                criteria={"pattern": ".*_at$"}  # ends with _at
            )

            result = await bulk_service.select_columns_by_pattern(
                user_id="user-123",
                dataset_id="test-dataset-123",
                pattern=pattern
            )

            assert len(result) == 1
            assert result[0]["column_name"] == "created_at"

    @pytest.mark.asyncio
    async def test_select_columns_by_name_pattern_contains(self, bulk_service, mock_dataset):
        """Test selecting columns containing a substring."""
        with patch.object(
            DatasetMetadata, 'find_one', new_callable=AsyncMock
        ) as mock_find:
            mock_find.return_value = mock_dataset

            pattern = ColumnSelectionPattern(
                pattern_type=PatternType.NAME_PATTERN,
                criteria={"pattern": "a"}  # contains 'a'
            )

            result = await bulk_service.select_columns_by_pattern(
                user_id="user-123",
                dataset_id="test-dataset-123",
                pattern=pattern
            )

            column_names = [col["column_name"] for col in result]
            assert "age" in column_names
            assert "name" in column_names
            assert "salary" in column_names
            assert "is_active" in column_names
            assert "created_at" in column_names
            assert "status" in column_names

    @pytest.mark.asyncio
    async def test_select_columns_by_quality_metric_missing_values(self, bulk_service, mock_dataset):
        """Test selecting columns with missing values above threshold."""
        with patch.object(
            DatasetMetadata, 'find_one', new_callable=AsyncMock
        ) as mock_find:
            mock_find.return_value = mock_dataset

            pattern = ColumnSelectionPattern(
                pattern_type=PatternType.QUALITY_METRIC,
                criteria={"metric": "missing_values", "operator": "gt", "threshold": 0}
            )

            result = await bulk_service.select_columns_by_pattern(
                user_id="user-123",
                dataset_id="test-dataset-123",
                pattern=pattern
            )

            assert len(result) == 2
            column_names = [col["column_name"] for col in result]
            assert "age" in column_names  # 5 missing
            assert "salary" in column_names  # 10 missing

    @pytest.mark.asyncio
    async def test_select_columns_by_quality_metric_is_constant(self, bulk_service, mock_dataset):
        """Test selecting constant columns."""
        with patch.object(
            DatasetMetadata, 'find_one', new_callable=AsyncMock
        ) as mock_find:
            mock_find.return_value = mock_dataset

            pattern = ColumnSelectionPattern(
                pattern_type=PatternType.QUALITY_METRIC,
                criteria={"metric": "is_constant"}
            )

            result = await bulk_service.select_columns_by_pattern(
                user_id="user-123",
                dataset_id="test-dataset-123",
                pattern=pattern
            )

            assert len(result) == 1
            assert result[0]["column_name"] == "constant_col"

    @pytest.mark.asyncio
    async def test_select_columns_by_quality_metric_high_cardinality(self, bulk_service, mock_dataset):
        """Test selecting high cardinality columns."""
        with patch.object(
            DatasetMetadata, 'find_one', new_callable=AsyncMock
        ) as mock_find:
            mock_find.return_value = mock_dataset

            pattern = ColumnSelectionPattern(
                pattern_type=PatternType.QUALITY_METRIC,
                criteria={"metric": "is_high_cardinality"}
            )

            result = await bulk_service.select_columns_by_pattern(
                user_id="user-123",
                dataset_id="test-dataset-123",
                pattern=pattern
            )

            assert len(result) == 2
            column_names = [col["column_name"] for col in result]
            assert "name" in column_names
            assert "created_at" in column_names

    @pytest.mark.asyncio
    async def test_select_columns_dataset_not_found(self, bulk_service):
        """Test error when dataset not found."""
        with patch.object(
            DatasetMetadata, 'find_one', new_callable=AsyncMock
        ) as mock_find:
            mock_find.return_value = None

            pattern = ColumnSelectionPattern(
                pattern_type=PatternType.DATA_TYPE,
                criteria={"types": ["numeric"]}
            )

            with pytest.raises(NotFoundError):
                await bulk_service.select_columns_by_pattern(
                    user_id="user-123",
                    dataset_id="nonexistent-dataset",
                    pattern=pattern
                )


class TestBulkPreview:
    """Tests for bulk transformation preview."""

    @pytest.mark.asyncio
    async def test_preview_bulk_transformation_success(
        self, bulk_service, mock_dataset, sample_dataframe
    ):
        """Test successful bulk preview."""
        with patch.object(
            DatasetMetadata, 'find_one', new_callable=AsyncMock
        ) as mock_find:
            mock_find.return_value = mock_dataset

            with patch(
                'app.services.bulk_transformation_service.get_dataframe_from_s3',
                new_callable=AsyncMock
            ) as mock_get_df:
                mock_get_df.return_value = sample_dataframe

                # Mock the transformation engine
                mock_result = MagicMock()
                mock_result.success = True
                mock_result.preview_data = [{"age": 25}, {"age": 30}]
                mock_result.stats_before = {"count": 5, "mean": 32.5}
                mock_result.stats_after = {"count": 4, "mean": 32.5}
                mock_result.affected_rows = 1
                mock_result.error = None
                mock_result.warnings = []

                with patch.object(
                    bulk_service.engine, 'preview_transformation',
                    return_value=mock_result
                ):
                    result = await bulk_service.preview_bulk_transformation(
                        user_id="user-123",
                        dataset_id="test-dataset-123",
                        selected_columns=["age", "salary"],
                        transformation_type="drop_missing",
                        global_parameters={},
                        preview_rows=10
                    )

                    assert result["success"] is True
                    assert result["total_columns"] == 2
                    assert result["successful_previews"] == 2
                    assert result["failed_previews"] == 0
                    assert len(result["column_previews"]) == 2

    @pytest.mark.asyncio
    async def test_preview_bulk_transformation_invalid_columns(
        self, bulk_service, mock_dataset, sample_dataframe
    ):
        """Test preview with invalid column names."""
        with patch.object(
            DatasetMetadata, 'find_one', new_callable=AsyncMock
        ) as mock_find:
            mock_find.return_value = mock_dataset

            with patch(
                'app.services.bulk_transformation_service.get_dataframe_from_s3',
                new_callable=AsyncMock
            ) as mock_get_df:
                mock_get_df.return_value = sample_dataframe

                with pytest.raises(OperationError) as exc_info:
                    await bulk_service.preview_bulk_transformation(
                        user_id="user-123",
                        dataset_id="test-dataset-123",
                        selected_columns=["nonexistent_column"],
                        transformation_type="drop_missing",
                        global_parameters={},
                    )

                # The error is wrapped in OperationError, check the message or details
                assert exc_info.value.message is not None


class TestBulkJobManagement:
    """Tests for bulk transformation job management."""

    def test_column_result_model(self):
        """Test ColumnResult model creation."""
        result = ColumnResult(
            column_name="test_col",
            success=True,
            affected_rows=100,
            execution_time_ms=50,
            stats_before={"count": 100},
            stats_after={"count": 95},
        )

        assert result.column_name == "test_col"
        assert result.success is True
        assert result.affected_rows == 100
        assert result.execution_time_ms == 50

    def test_bulk_transformation_progress_model(self):
        """Test BulkTransformationProgress model."""
        progress = BulkTransformationProgress(
            total_columns=10,
            processed_columns=5,
            successful_columns=4,
            failed_columns=1,
            current_column="test_col"
        )

        assert progress.total_columns == 10
        assert progress.processed_columns == 5
        assert progress.percentage_complete == 50.0
        assert progress.success_rate == 80.0

    def test_bulk_transformation_progress_zero_columns(self):
        """Test progress with zero columns."""
        progress = BulkTransformationProgress(
            total_columns=0,
            processed_columns=0,
        )

        assert progress.percentage_complete == 0.0
        assert progress.success_rate == 0.0

    def test_bulk_transformation_result_model(self):
        """Test BulkTransformationResult model."""
        result = BulkTransformationResult(
            successful_columns=["col1", "col2"],
            failed_columns=[{"column_name": "col3", "error": "Failed"}],
            column_results=[
                ColumnResult(column_name="col1", success=True, affected_rows=10),
                ColumnResult(column_name="col2", success=True, affected_rows=20),
                ColumnResult(column_name="col3", success=False, error="Failed"),
            ],
            total_time_ms=1000,
            total_rows_affected=30,
        )

        assert len(result.successful_columns) == 2
        assert len(result.failed_columns) == 1
        assert result.total_time_ms == 1000
        assert result.total_rows_affected == 30

    def test_bulk_job_status_enum(self):
        """Test BulkJobStatus enum values."""
        assert BulkJobStatus.PENDING.value == "pending"
        assert BulkJobStatus.RUNNING.value == "running"
        assert BulkJobStatus.COMPLETED.value == "completed"
        assert BulkJobStatus.FAILED.value == "failed"
        assert BulkJobStatus.CANCELLED.value == "cancelled"
        assert BulkJobStatus.PARTIALLY_COMPLETED.value == "partially_completed"


class TestPatternMatching:
    """Tests for pattern matching utilities."""

    def test_compare_value_greater_than(self, bulk_service):
        """Test greater than comparison."""
        assert bulk_service._compare_value(10, 5, "gt") is True
        assert bulk_service._compare_value(5, 10, "gt") is False
        assert bulk_service._compare_value(5, 5, "gt") is False

    def test_compare_value_less_than(self, bulk_service):
        """Test less than comparison."""
        assert bulk_service._compare_value(5, 10, "lt") is True
        assert bulk_service._compare_value(10, 5, "lt") is False
        assert bulk_service._compare_value(5, 5, "lt") is False

    def test_compare_value_equal(self, bulk_service):
        """Test equality comparison."""
        assert bulk_service._compare_value(5, 5, "eq") is True
        assert bulk_service._compare_value(5, 10, "eq") is False

    def test_compare_value_greater_or_equal(self, bulk_service):
        """Test greater than or equal comparison."""
        assert bulk_service._compare_value(10, 5, "gte") is True
        assert bulk_service._compare_value(5, 5, "gte") is True
        assert bulk_service._compare_value(5, 10, "gte") is False

    def test_compare_value_less_or_equal(self, bulk_service):
        """Test less than or equal comparison."""
        assert bulk_service._compare_value(5, 10, "lte") is True
        assert bulk_service._compare_value(5, 5, "lte") is True
        assert bulk_service._compare_value(10, 5, "lte") is False


class TestColumnSelectionPatternValidation:
    """Tests for ColumnSelectionPattern model validation."""

    def test_data_type_pattern_valid(self):
        """Test valid data_type pattern."""
        pattern = ColumnSelectionPattern(
            pattern_type=PatternType.DATA_TYPE,
            criteria={"types": ["numeric", "text"]}
        )
        assert pattern.pattern_type == PatternType.DATA_TYPE
        assert pattern.criteria["types"] == ["numeric", "text"]

    def test_name_pattern_valid(self):
        """Test valid name_pattern."""
        pattern = ColumnSelectionPattern(
            pattern_type=PatternType.NAME_PATTERN,
            criteria={"pattern": "^price_"}
        )
        assert pattern.pattern_type == PatternType.NAME_PATTERN
        assert pattern.criteria["pattern"] == "^price_"

    def test_quality_metric_pattern_valid(self):
        """Test valid quality_metric pattern."""
        pattern = ColumnSelectionPattern(
            pattern_type=PatternType.QUALITY_METRIC,
            criteria={"metric": "missing_values", "operator": "gt", "threshold": 10}
        )
        assert pattern.pattern_type == PatternType.QUALITY_METRIC
        assert pattern.criteria["metric"] == "missing_values"

    def test_data_type_pattern_invalid_type(self):
        """Test data_type pattern with invalid type."""
        with pytest.raises(ValueError) as exc_info:
            ColumnSelectionPattern(
                pattern_type=PatternType.DATA_TYPE,
                criteria={"types": ["invalid_type"]}
            )
        assert "Invalid type" in str(exc_info.value)

    def test_data_type_pattern_missing_types(self):
        """Test data_type pattern without types."""
        with pytest.raises(ValueError) as exc_info:
            ColumnSelectionPattern(
                pattern_type=PatternType.DATA_TYPE,
                criteria={}
            )
        assert "requires 'types'" in str(exc_info.value)

    def test_name_pattern_missing_pattern(self):
        """Test name_pattern without pattern."""
        with pytest.raises(ValueError) as exc_info:
            ColumnSelectionPattern(
                pattern_type=PatternType.NAME_PATTERN,
                criteria={}
            )
        assert "requires 'pattern'" in str(exc_info.value)

    def test_quality_metric_pattern_missing_metric(self):
        """Test quality_metric pattern without metric."""
        with pytest.raises(ValueError) as exc_info:
            ColumnSelectionPattern(
                pattern_type=PatternType.QUALITY_METRIC,
                criteria={}
            )
        assert "requires 'metric'" in str(exc_info.value)

    def test_quality_metric_pattern_invalid_metric(self):
        """Test quality_metric pattern with invalid metric."""
        with pytest.raises(ValueError) as exc_info:
            ColumnSelectionPattern(
                pattern_type=PatternType.QUALITY_METRIC,
                criteria={"metric": "invalid_metric"}
            )
        assert "Invalid metric" in str(exc_info.value)
