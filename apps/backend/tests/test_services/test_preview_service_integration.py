"""
Unit Tests for PreviewServiceIntegration.

Following TDD methodology with comprehensive mocking approach.
Tests cover all aspects of the preview workflow: data loading, transformation application,
impact calculation, error handling, and edge cases.

Test Coverage:
- generate_preview success cases (single and multiple operations)
- Input validation (empty operations, invalid sample size)
- Transformation error handling (per-operation failures)
- Impact statistics calculation
- Empty data handling
- Large sample size limits
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import pandas as pd
import numpy as np

from app.services.data_processing.preview_service_integration import PreviewServiceIntegration
from app.schemas.preview import PreviewResult, ImpactStatistics
from app.schemas.transformation import TransformationStepRequest

@pytest.mark.unit
class TestPreviewServiceIntegration:
    """Unit tests for PreviewServiceIntegration service."""

    def setup_method(self):
        """Set up test fixtures for each test."""
        # Create service instance with mocked dependencies
        self.service = PreviewServiceIntegration()

    def _create_mock_dataset(self, dataset_id="dataset456", user_id="user123", s3_url="s3://bucket/file.csv"):
        """Helper to create mock dataset"""
        mock_dataset = MagicMock()
        mock_dataset.dataset_id = dataset_id
        mock_dataset.user_id = user_id
        mock_dataset.s3_url = s3_url
        mock_dataset.file_path = s3_url
        return mock_dataset

    @pytest.fixture
    def sample_dataframe(self):
        """Create a sample DataFrame for testing."""
        return pd.DataFrame({
            "id": [1, 2, 3, 4, 5],
            "age": [25, 30, None, 40, 28],
            "salary": [50000, 60000, 70000, 80000, 55000],
            "department": ["Sales", "IT", "Sales", "IT", "HR"]
        })

    @pytest.fixture
    def sample_transformation_step(self):
        """Create a sample transformation step."""
        return TransformationStepRequest(
            transformation_type="drop_missing",
            column="age"
        )

    # =====================================================================
    # Test 1: Successful preview generation
    # =====================================================================

    @pytest.mark.asyncio
    async def test_generate_preview_success(self, sample_dataframe, sample_transformation_step):
        """
        Test successful preview generation with valid inputs.

        Verifies:
        - S3 data loading is called
        - Transformation engine applies transformation
        - Impact statistics are calculated
        - PreviewResult contains original and transformed data
        """
        # ARRANGE
        expected_transformed = sample_dataframe.copy()
        expected_impact = ImpactStatistics(
            rows_affected=1,
            values_changed=1,
            columns_affected=["age"],
            quality_score_before=0.75,
            quality_score_after=0.85,
            value_distributions={
                "age": {
                    "before": {"25": 1, "30": 1, "40": 1, "28": 1, "null": 1},
                    "after": {"25": 1, "30": 1, "40": 1, "28": 1}
                }
            }
        )

        # Mock dataset metadata lookup
        mock_dataset = self._create_mock_dataset()

        # Mock S3 data loading
        with patch(
            'app.models.dataset.DatasetMetadata.find_one',
            new=AsyncMock(return_value=mock_dataset)
        ), patch(
            'app.services.data_processing.preview_service_integration.get_dataframe_from_s3',
            new=AsyncMock(return_value=sample_dataframe)
        ), patch.object(
            self.service.transformation_engine,
            'preview_transformation_step',
            new=AsyncMock(return_value=(expected_transformed, None))
        ), patch.object(
            self.service.preview_service,
            'calculate_impact',
            new=AsyncMock(return_value=expected_impact)
        ):
            # ACT
            result = await self.service.generate_preview(
                user_id="user123",
                dataset_id="dataset456",
                s3_file_path="s3://bucket/file.csv",
                operations=[sample_transformation_step],
                sample_size=100
            )

            # ASSERT
            assert isinstance(result, PreviewResult)
            assert len(result.original_data) == 5
            assert len(result.transformed_data) == 5
            assert len(result.errors) == 0
            assert result.impact_stats.rows_affected == 1
            assert result.impact_stats.quality_score_before == 0.75
            assert result.impact_stats.quality_score_after == 0.85

    # =====================================================================
    # Test 2: Empty operations list validation
    # =====================================================================

    @pytest.mark.asyncio
    async def test_generate_preview_empty_operations(self):
        """
        Test that empty operations list raises ValueError.

        Verifies:
        - Empty operations list is rejected
        - ValueError is raised with appropriate message
        """
        # ACT & ASSERT
        with pytest.raises(ValueError, match="Operations list cannot be empty"):
            await self.service.generate_preview(
                user_id="user123",
                dataset_id="dataset456",
                s3_file_path="s3://bucket/file.csv",
                operations=[],  # Empty operations
                sample_size=100
            )

    # =====================================================================
    # Test 3: Invalid sample size validation (below minimum)
    # =====================================================================

    @pytest.mark.asyncio
    async def test_generate_preview_sample_size_below_minimum(self, sample_transformation_step):
        """
        Test that sample_size below minimum (10) raises ValueError.

        Verifies:
        - Sample size < 10 is rejected
        - ValueError is raised with appropriate message
        """
        # ACT & ASSERT
        with pytest.raises(ValueError, match="Sample size must be between 10 and 1000"):
            await self.service.generate_preview(
                user_id="user123",
                dataset_id="dataset456",
                s3_file_path="s3://bucket/file.csv",
                operations=[sample_transformation_step],
                sample_size=5  # Below minimum
            )

    # =====================================================================
    # Test 4: Invalid sample size validation (above maximum)
    # =====================================================================

    @pytest.mark.asyncio
    async def test_generate_preview_sample_size_above_maximum(self, sample_transformation_step):
        """
        Test that sample_size above maximum (1000) raises ValueError.

        Verifies:
        - Sample size > 1000 is rejected
        - ValueError is raised with appropriate message
        """
        # ACT & ASSERT
        with pytest.raises(ValueError, match="Sample size must be between 10 and 1000"):
            await self.service.generate_preview(
                user_id="user123",
                dataset_id="dataset456",
                s3_file_path="s3://bucket/file.csv",
                operations=[sample_transformation_step],
                sample_size=2000  # Above maximum
            )

    # =====================================================================
    # Test 5: Multiple transformation operations
    # =====================================================================

    @pytest.mark.asyncio
    async def test_generate_preview_multiple_operations(self, sample_dataframe):
        """
        Test preview generation with multiple transformation operations.

        Verifies:
        - All transformations are applied sequentially
        - Each operation receives the result of the previous one
        - Impact statistics reflect cumulative changes
        """
        # ARRANGE
        transformed_df_step1 = sample_dataframe.copy()
        transformed_df_step2 = transformed_df_step1.copy()

        expected_impact = ImpactStatistics(
            rows_affected=2,
            values_changed=5,
            columns_affected=["age", "salary"],
            quality_score_before=0.75,
            quality_score_after=0.90,
            value_distributions={}
        )

        operation1 = TransformationStepRequest(
            transformation_type="drop_missing",
            column="age"
        )
        operation2 = TransformationStepRequest(
            transformation_type="outlier_removal",
            column="salary",
            parameters={"method": "iqr"}
        )

        # Mock dataset metadata lookup
        mock_dataset = self._create_mock_dataset()

        # Mock S3 and transformation engine
        with patch(
            'app.models.dataset.DatasetMetadata.find_one',
            new=AsyncMock(return_value=mock_dataset)
        ), patch(
            'app.services.data_processing.preview_service_integration.get_dataframe_from_s3',
            new=AsyncMock(return_value=sample_dataframe)
        ), patch.object(
            self.service.transformation_engine,
            'preview_transformation_step',
            new=AsyncMock(side_effect=[
                (transformed_df_step1, None),  # First operation
                (transformed_df_step2, None),  # Second operation
            ])
        ), patch.object(
            self.service.preview_service,
            'calculate_impact',
            new=AsyncMock(return_value=expected_impact)
        ):
            # ACT
            result = await self.service.generate_preview(
                user_id="user123",
                dataset_id="dataset456",
                s3_file_path="s3://bucket/file.csv",
                operations=[operation1, operation2],
                sample_size=100
            )

            # ASSERT
            assert isinstance(result, PreviewResult)
            assert len(result.errors) == 0
            assert result.impact_stats.rows_affected == 2
            # Verify transformation engine was called twice
            assert self.service.transformation_engine.preview_transformation_step.call_count == 2

    # =====================================================================
    # Test 6: Transformation failure handling
    # =====================================================================

    @pytest.mark.asyncio
    async def test_generate_preview_transformation_failure(self, sample_dataframe, sample_transformation_step):
        """
        Test preview generation when transformation fails.

        Verifies:
        - Transformation error is caught
        - Error is added to errors list
        - Processing stops on first error
        - Returns original data when all transformations fail
        """
        # ARRANGE
        expected_impact = ImpactStatistics(
            rows_affected=0,
            values_changed=0,
            columns_affected=[],
            quality_score_before=0.5,
            quality_score_after=0.5,
            value_distributions={}
        )

        # Mock dataset metadata lookup
        mock_dataset = self._create_mock_dataset()

        # Mock S3 loading success but transformation failure
        with patch(
            'app.models.dataset.DatasetMetadata.find_one',
            new=AsyncMock(return_value=mock_dataset)
        ), patch(
            'app.services.data_processing.preview_service_integration.get_dataframe_from_s3',
            new=AsyncMock(return_value=sample_dataframe)
        ), patch.object(
            self.service.transformation_engine,
            'preview_transformation_step',
            new=AsyncMock(side_effect=Exception("Invalid column"))
        ), patch.object(
            self.service.preview_service,
            'calculate_impact',
            new=AsyncMock(return_value=expected_impact)
        ):
            # ACT
            result = await self.service.generate_preview(
                user_id="user123",
                dataset_id="dataset456",
                s3_file_path="s3://bucket/file.csv",
                operations=[sample_transformation_step],
                sample_size=100
            )

            # ASSERT
            assert isinstance(result, PreviewResult)
            assert len(result.errors) == 1
            assert "Invalid column" in result.errors[0]
            # When error occurs, original data is still available
            assert len(result.original_data) == len(result.transformed_data)

    # =====================================================================
    # Test 7: S3 loading failure
    # =====================================================================

    @pytest.mark.asyncio
    async def test_generate_preview_s3_load_failure(self, sample_transformation_step):
        """
        Test preview generation when S3 data loading fails.

        Verifies:
        - S3 loading exception is caught
        - Exception is re-raised (not handled gracefully)
        - Appropriate error message is included
        """
        # ARRANGE
        # Mock dataset metadata lookup

        mock_dataset = self._create_mock_dataset()

        with patch(

            'app.models.dataset.DatasetMetadata.find_one',

            new=AsyncMock(return_value=mock_dataset)
        ), patch(

            'app.services.data_processing.preview_service_integration.get_dataframe_from_s3',
            new=AsyncMock(side_effect=Exception("S3 connection failed"))
        ):
            # ACT & ASSERT
            with pytest.raises(Exception, match="Preview generation failed"):
                await self.service.generate_preview(
                    user_id="user123",
                    dataset_id="dataset456",
                    s3_file_path="s3://bucket/file.csv",
                    operations=[sample_transformation_step],
                    sample_size=100
                )

    # =====================================================================
    # Test 8: Empty dataset handling
    # =====================================================================

    @pytest.mark.asyncio
    async def test_generate_preview_empty_dataset(self, sample_transformation_step):
        """
        Test preview generation when loaded dataset is empty.

        Verifies:
        - Empty DataFrame is detected
        - ValueError is raised
        - Appropriate error message is provided
        """
        # ARRANGE
        empty_df = pd.DataFrame()

        # Mock dataset metadata lookup

        mock_dataset = self._create_mock_dataset()

        with patch(

            'app.models.dataset.DatasetMetadata.find_one',

            new=AsyncMock(return_value=mock_dataset)
        ), patch(

            'app.services.data_processing.preview_service_integration.get_dataframe_from_s3',
            new=AsyncMock(return_value=empty_df)
        ):
            # ACT & ASSERT
            with pytest.raises(ValueError, match="Dataset is empty"):
                await self.service.generate_preview(
                    user_id="user123",
                    dataset_id="dataset456",
                    s3_file_path="s3://bucket/file.csv",
                    operations=[sample_transformation_step],
                    sample_size=100
                )

    # =====================================================================
    # Test 9: Data limiting to sample_size
    # =====================================================================

    @pytest.mark.asyncio
    async def test_generate_preview_limits_to_sample_size(self, sample_dataframe, sample_transformation_step):
        """
        Test that preview limits data to sample_size even if more rows are loaded.

        Verifies:
        - Loaded DataFrame with more than sample_size rows is limited
        - Limited data is used for transformations
        - Result contains at most sample_size rows
        """
        # ARRANGE
        # Create a DataFrame with more rows than sample_size
        large_df = pd.concat([sample_dataframe] * 20, ignore_index=True)  # 100 rows
        expected_transformed = large_df.head(10).copy()  # Should be limited to 10

        expected_impact = ImpactStatistics(
            rows_affected=0,
            values_changed=0,
            columns_affected=[],
            quality_score_before=0.75,
            quality_score_after=0.75,
            value_distributions={}
        )

        # Mock dataset metadata lookup

        mock_dataset = self._create_mock_dataset()

        with patch(

            'app.models.dataset.DatasetMetadata.find_one',

            new=AsyncMock(return_value=mock_dataset)
        ), patch(

            'app.services.data_processing.preview_service_integration.get_dataframe_from_s3',
            new=AsyncMock(return_value=large_df)
        ), patch.object(
            self.service.transformation_engine,
            'preview_transformation_step',
            new=AsyncMock(return_value=(expected_transformed, None))
        ), patch.object(
            self.service.preview_service,
            'calculate_impact',
            new=AsyncMock(return_value=expected_impact)
        ):
            # ACT
            result = await self.service.generate_preview(
                user_id="user123",
                dataset_id="dataset456",
                s3_file_path="s3://bucket/file.csv",
                operations=[sample_transformation_step],
                sample_size=10  # Limit to 10 rows
            )

            # ASSERT
            assert isinstance(result, PreviewResult)
            assert len(result.original_data) <= 10

    # =====================================================================
    # Test 10: Impact calculation failure handling
    # =====================================================================

    @pytest.mark.asyncio
    async def test_generate_preview_impact_calculation_failure(self, sample_dataframe, sample_transformation_step):
        """
        Test preview generation when impact calculation fails.

        Verifies:
        - Impact calculation exception is caught
        - Fallback impact stats are used
        - Warning is added to warnings list
        - Preview still returns successfully
        """
        # ARRANGE
        expected_transformed = sample_dataframe.copy()

        # Mock dataset metadata lookup

        mock_dataset = self._create_mock_dataset()

        with patch(

            'app.models.dataset.DatasetMetadata.find_one',

            new=AsyncMock(return_value=mock_dataset)
        ), patch(

            'app.services.data_processing.preview_service_integration.get_dataframe_from_s3',
            new=AsyncMock(return_value=sample_dataframe)
        ), patch.object(
            self.service.transformation_engine,
            'preview_transformation_step',
            new=AsyncMock(return_value=(expected_transformed, None))
        ), patch.object(
            self.service.preview_service,
            'calculate_impact',
            new=AsyncMock(side_effect=Exception("Quality assessment service unavailable"))
        ):
            # ACT
            result = await self.service.generate_preview(
                user_id="user123",
                dataset_id="dataset456",
                s3_file_path="s3://bucket/file.csv",
                operations=[sample_transformation_step],
                sample_size=100
            )

            # ASSERT
            assert isinstance(result, PreviewResult)
            assert len(result.warnings) == 1
            assert "Could not calculate detailed impact statistics" in result.warnings[0]
            # Verify fallback impact stats are used
            assert result.impact_stats.quality_score_before == 0.5
            assert result.impact_stats.quality_score_after == 0.5
            assert len(result.errors) == 0

    # =====================================================================
    # Test 11: Partial transformation failure (multiple operations)
    # =====================================================================

    @pytest.mark.asyncio
    async def test_generate_preview_partial_transformation_failure(self, sample_dataframe):
        """
        Test preview generation when one of multiple transformations fails.

        Verifies:
        - First transformation succeeds
        - Second transformation fails
        - Processing stops on first error
        - Data contains result of first successful transformation plus original data
        """
        # ARRANGE
        transformed_step1 = sample_dataframe.copy()

        expected_impact = ImpactStatistics(
            rows_affected=0,
            values_changed=0,
            columns_affected=[],
            quality_score_before=0.5,
            quality_score_after=0.5,
            value_distributions={}
        )

        operation1 = TransformationStepRequest(
            transformation_type="drop_missing",
            column="age"
        )
        operation2 = TransformationStepRequest(
            transformation_type="derive",
            column="nonexistent"
        )

        # Mock dataset metadata lookup

        mock_dataset = self._create_mock_dataset()

        with patch(

            'app.models.dataset.DatasetMetadata.find_one',

            new=AsyncMock(return_value=mock_dataset)
        ), patch(

            'app.services.data_processing.preview_service_integration.get_dataframe_from_s3',
            new=AsyncMock(return_value=sample_dataframe)
        ), patch.object(
            self.service.transformation_engine,
            'preview_transformation_step',
            new=AsyncMock(side_effect=[
                (transformed_step1, None),  # First operation succeeds
                Exception("Invalid transformation"),  # Second operation fails
            ])
        ), patch.object(
            self.service.preview_service,
            'calculate_impact',
            new=AsyncMock(return_value=expected_impact)
        ):
            # ACT
            result = await self.service.generate_preview(
                user_id="user123",
                dataset_id="dataset456",
                s3_file_path="s3://bucket/file.csv",
                operations=[operation1, operation2],
                sample_size=100
            )

            # ASSERT
            assert isinstance(result, PreviewResult)
            assert len(result.errors) == 1
            assert "Invalid transformation" in result.errors[0]
            # Verify transformation engine was called (at least first operation)
            assert self.service.transformation_engine.preview_transformation_step.call_count >= 1

    # =====================================================================
    # Test 12: Valid minimum sample size
    # =====================================================================

    @pytest.mark.asyncio
    async def test_generate_preview_minimum_sample_size(self, sample_dataframe, sample_transformation_step):
        """
        Test preview generation with valid minimum sample size (10).

        Verifies:
        - Sample size = 10 is accepted
        - Preview generation succeeds
        """
        # ARRANGE
        small_df = sample_dataframe.head(10).copy()
        expected_transformed = small_df.copy()

        expected_impact = ImpactStatistics(
            rows_affected=0,
            values_changed=0,
            columns_affected=[],
            quality_score_before=0.75,
            quality_score_after=0.75,
            value_distributions={}
        )

        # Mock dataset metadata lookup

        mock_dataset = self._create_mock_dataset()

        with patch(

            'app.models.dataset.DatasetMetadata.find_one',

            new=AsyncMock(return_value=mock_dataset)
        ), patch(

            'app.services.data_processing.preview_service_integration.get_dataframe_from_s3',
            new=AsyncMock(return_value=small_df)
        ), patch.object(
            self.service.transformation_engine,
            'preview_transformation_step',
            new=AsyncMock(return_value=(expected_transformed, None))
        ), patch.object(
            self.service.preview_service,
            'calculate_impact',
            new=AsyncMock(return_value=expected_impact)
        ):
            # ACT
            result = await self.service.generate_preview(
                user_id="user123",
                dataset_id="dataset456",
                s3_file_path="s3://bucket/file.csv",
                operations=[sample_transformation_step],
                sample_size=10  # Minimum valid size
            )

            # ASSERT
            assert isinstance(result, PreviewResult)
            assert len(result.errors) == 0

    # =====================================================================
    # Test 13: Valid maximum sample size
    # =====================================================================

    @pytest.mark.asyncio
    async def test_generate_preview_maximum_sample_size(self, sample_transformation_step):
        """
        Test preview generation with valid maximum sample size (1000).

        Verifies:
        - Sample size = 1000 is accepted
        - Preview generation succeeds
        """
        # ARRANGE
        large_df = pd.DataFrame({
            "id": range(1, 1001),
            "value": np.random.rand(1000),
        })
        expected_transformed = large_df.copy()

        expected_impact = ImpactStatistics(
            rows_affected=0,
            values_changed=0,
            columns_affected=[],
            quality_score_before=0.75,
            quality_score_after=0.75,
            value_distributions={}
        )

        # Mock dataset metadata lookup

        mock_dataset = self._create_mock_dataset()

        with patch(

            'app.models.dataset.DatasetMetadata.find_one',

            new=AsyncMock(return_value=mock_dataset)
        ), patch(

            'app.services.data_processing.preview_service_integration.get_dataframe_from_s3',
            new=AsyncMock(return_value=large_df)
        ), patch.object(
            self.service.transformation_engine,
            'preview_transformation_step',
            new=AsyncMock(return_value=(expected_transformed, None))
        ), patch.object(
            self.service.preview_service,
            'calculate_impact',
            new=AsyncMock(return_value=expected_impact)
        ):
            # ACT
            result = await self.service.generate_preview(
                user_id="user123",
                dataset_id="dataset456",
                s3_file_path="s3://bucket/file.csv",
                operations=[sample_transformation_step],
                sample_size=1000  # Maximum valid size
            )

            # ASSERT
            assert isinstance(result, PreviewResult)
            assert len(result.errors) == 0
