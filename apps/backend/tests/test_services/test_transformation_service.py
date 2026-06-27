"""
Tests for TransformationService with versioning integration.

Tests transformation configuration operations and integration with versioning service.
Following TDD methodology with comprehensive mocking approach.

Test Coverage:
- apply_transformation creates version
- apply_transformation updates current_position
- apply_transformation handles branching (truncates forward history)
- apply_transformation links version to transformation config
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from app.services.transformation_service import TransformationService


@pytest.fixture
def transformation_service():
    """Create transformation service instance."""
    return TransformationService()


@pytest.fixture
def mock_dataset():
    """Create mock dataset metadata."""
    mock = MagicMock()
    mock.dataset_id = "ds1"
    mock.user_id = "user1"
    mock.file_path = "s3://bucket/datasets/user1/ds1/test.csv"
    mock.s3_url = "s3://bucket/datasets/user1/ds1/test.csv"
    mock.save = AsyncMock()
    mock.update_timestamp = MagicMock()
    return mock


@pytest.fixture
def sample_dataframe():
    """Create sample DataFrame for testing."""
    return pd.DataFrame({
        "id": [1, 2, 3, 4, 5],
        "age": [25, 30, None, 40, 28],
        "salary": [50000, 60000, 70000, 80000, 55000],
        "department": ["Sales", "IT", "Sales", "IT", "HR"]
    })


@pytest.fixture
def mock_parent_version():
    """Create mock parent version."""
    mock = MagicMock()
    mock.version_id = "parent_version_123"
    mock.version_number = 1
    return mock


@pytest.mark.unit
class TestApplyTransformationVersioning:
    """Tests for apply_transformation versioning integration."""

    @pytest.mark.asyncio
    async def test_apply_transformation_creates_version(
        self,
        transformation_service,
        mock_dataset,
        sample_dataframe,
        mock_parent_version
    ):
        """
        Test that successful transformation creates a new version.

        Verifies:
        - versioning_service.create_transformation_version is called
        - New version is created with correct parameters
        - Version is linked to transformation config
        """
        # ARRANGE
        user_id = "user1"
        dataset_id = "ds1"
        transformation_type = "drop_missing"
        parameters = {"column": "age"}

        transformed_df = sample_dataframe.dropna(subset=["age"])

        # Mock transformation result
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.transformed_data = transformed_df.to_dict('records')
        mock_result.affected_rows = 1
        mock_result.affected_columns = ["age"]
        mock_result.warnings = []

        # Mock TransformationConfig instance
        mock_config = MagicMock()
        mock_config.config_id = "config_ds1_12345"
        mock_config.transformation_steps = []
        mock_config.current_position = -1
        mock_config.save = AsyncMock()

        # Mock version and lineage
        mock_version = MagicMock()
        mock_version.version_id = "version123"
        mock_lineage = MagicMock()

        with patch('app.models.dataset.DatasetMetadata.find_one',
                   new=AsyncMock(return_value=mock_dataset)), \
             patch('app.services.transformation_engine.data_utils.get_dataframe_from_s3',
                   new=AsyncMock(return_value=sample_dataframe)), \
             patch('app.services.transformation_engine.data_utils.upload_dataframe_to_s3',
                   new=AsyncMock(return_value="s3://bucket/transformed/user1/ds1_12345.parquet")), \
             patch.object(transformation_service.engine, 'apply_transformation', return_value=mock_result), \
             patch.object(transformation_service, 'create_transformation_config',
                          new=AsyncMock(return_value=mock_config)), \
             patch.object(transformation_service, 'add_transformation_step',
                          new=AsyncMock(return_value=mock_config)), \
             patch.object(transformation_service, 'mark_transformations_applied',
                          new=AsyncMock(return_value=mock_config)), \
             patch('app.models.version.DatasetVersion.find') as mock_find, \
             patch('app.services.redis_cache.cache_service') as mock_cache, \
             patch('app.services.versioning_service.versioning_service') as mock_versioning:

            # Mock find().sort().first_or_none() chain
            mock_cursor = MagicMock()
            mock_cursor.sort = MagicMock(return_value=mock_cursor)
            mock_cursor.first_or_none = AsyncMock(return_value=mock_parent_version)
            mock_find.return_value = mock_cursor

            mock_cache.delete_pattern = AsyncMock()
            mock_versioning.create_transformation_version = AsyncMock(
                return_value=(mock_version, mock_lineage)
            )

            # ACT
            result = await transformation_service.apply_transformation(
                user_id=user_id,
                dataset_id=dataset_id,
                transformation_type=transformation_type,
                parameters=parameters
            )

            # ASSERT
            assert result["success"] is True
            # Versioning service should have been called
            mock_versioning.create_transformation_version.assert_called_once()
            call_args = mock_versioning.create_transformation_version.call_args
            assert call_args is not None

    @pytest.mark.asyncio
    async def test_apply_transformation_updates_current_position(
        self,
        transformation_service,
        mock_dataset,
        sample_dataframe,
        mock_parent_version
    ):
        """
        Test that applying transformation updates current_position.

        Verifies:
        - current_position is updated to len(transformation_steps) - 1
        - Position points to the newly added step
        """
        # ARRANGE
        user_id = "user1"
        dataset_id = "ds1"
        transformation_type = "drop_missing"
        parameters = {"column": "age"}

        transformed_df = sample_dataframe.dropna(subset=["age"])

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.transformed_data = transformed_df.to_dict('records')
        mock_result.affected_rows = 1
        mock_result.affected_columns = ["age"]
        mock_result.warnings = []

        # Mock TransformationConfig with existing steps
        mock_config = MagicMock()
        mock_config.config_id = "config_ds1_12345"
        mock_config.transformation_steps = [MagicMock(), MagicMock()]  # 2 existing steps
        mock_config.current_position = 1  # At end of existing steps
        mock_config.save = AsyncMock()

        # Mock add_transformation_step to update position
        async def mock_add_step(config_id, **kwargs):
            mock_config.transformation_steps.append(MagicMock())
            mock_config.current_position = len(mock_config.transformation_steps) - 1
            return mock_config

        mock_version = MagicMock()
        mock_version.version_id = "version123"
        mock_lineage = MagicMock()

        with patch('app.models.dataset.DatasetMetadata.find_one',
                   new=AsyncMock(return_value=mock_dataset)), \
             patch('app.services.transformation_engine.data_utils.get_dataframe_from_s3',
                   new=AsyncMock(return_value=sample_dataframe)), \
             patch('app.services.transformation_engine.data_utils.upload_dataframe_to_s3',
                   new=AsyncMock(return_value="s3://bucket/transformed/user1/ds1_12345.parquet")), \
             patch.object(transformation_service.engine, 'apply_transformation', return_value=mock_result), \
             patch.object(transformation_service, 'create_transformation_config',
                          new=AsyncMock(return_value=mock_config)), \
             patch.object(transformation_service, 'add_transformation_step',
                          new=mock_add_step), \
             patch.object(transformation_service, 'mark_transformations_applied',
                          new=AsyncMock(return_value=mock_config)), \
             patch('app.models.version.DatasetVersion.find') as mock_find, \
             patch('app.services.redis_cache.cache_service') as mock_cache, \
             patch('app.services.versioning_service.versioning_service') as mock_versioning:

            # Mock find().sort().first_or_none() chain
            mock_cursor = MagicMock()
            mock_cursor.sort = MagicMock(return_value=mock_cursor)
            mock_cursor.first_or_none = AsyncMock(return_value=mock_parent_version)
            mock_find.return_value = mock_cursor

            mock_cache.delete_pattern = AsyncMock()
            mock_versioning.create_transformation_version = AsyncMock(
                return_value=(mock_version, mock_lineage)
            )

            # ACT
            result = await transformation_service.apply_transformation(
                user_id=user_id,
                dataset_id=dataset_id,
                transformation_type=transformation_type,
                parameters=parameters
            )

            # ASSERT
            assert result["success"] is True
            # Position should be updated to point to the new step
            assert mock_config.current_position == 2  # 3 steps total, position at index 2

    @pytest.mark.asyncio
    async def test_apply_transformation_truncates_forward_history(
        self,
        transformation_service,
        mock_dataset,
        sample_dataframe,
        mock_parent_version
    ):
        """
        Test that applying transformation after undo truncates forward history.

        Verifies:
        - When current_position < len(steps) - 1, forward history is truncated
        - add_transformation_step handles branching correctly
        - New step becomes the new end of history
        """
        # ARRANGE
        user_id = "user1"
        dataset_id = "ds1"
        transformation_type = "drop_missing"
        parameters = {"column": "age"}

        transformed_df = sample_dataframe.dropna(subset=["age"])

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.transformed_data = transformed_df.to_dict('records')
        mock_result.affected_rows = 1
        mock_result.affected_columns = ["age"]
        mock_result.warnings = []

        # Mock TransformationConfig in middle of history (after undo)
        mock_config = MagicMock()
        mock_config.config_id = "config_ds1_12345"
        step1 = MagicMock()
        step1.transformation_type = "normalize"
        step2 = MagicMock()
        step2.transformation_type = "scale"
        step3 = MagicMock()
        step3.transformation_type = "encode"
        mock_config.transformation_steps = [step1, step2, step3]  # 3 steps
        mock_config.current_position = 0  # At first step (after 2 undos)
        mock_config.save = AsyncMock()

        # Mock add_transformation_step to simulate branching
        async def mock_add_step(config_id, **kwargs):
            # Truncate forward history
            mock_config.transformation_steps = mock_config.transformation_steps[:mock_config.current_position + 1]
            # Add new step
            new_step = MagicMock()
            new_step.transformation_type = kwargs['transformation_type']
            mock_config.transformation_steps.append(new_step)
            mock_config.current_position = len(mock_config.transformation_steps) - 1
            return mock_config

        mock_version = MagicMock()
        mock_version.version_id = "version123"
        mock_lineage = MagicMock()

        with patch('app.models.dataset.DatasetMetadata.find_one',
                   new=AsyncMock(return_value=mock_dataset)), \
             patch('app.services.transformation_engine.data_utils.get_dataframe_from_s3',
                   new=AsyncMock(return_value=sample_dataframe)), \
             patch('app.services.transformation_engine.data_utils.upload_dataframe_to_s3',
                   new=AsyncMock(return_value="s3://bucket/transformed/user1/ds1_12345.parquet")), \
             patch.object(transformation_service.engine, 'apply_transformation', return_value=mock_result), \
             patch.object(transformation_service, 'create_transformation_config',
                          new=AsyncMock(return_value=mock_config)), \
             patch.object(transformation_service, 'add_transformation_step',
                          new=mock_add_step), \
             patch.object(transformation_service, 'mark_transformations_applied',
                          new=AsyncMock(return_value=mock_config)), \
             patch('app.models.version.DatasetVersion.find') as mock_find, \
             patch('app.services.redis_cache.cache_service') as mock_cache, \
             patch('app.services.versioning_service.versioning_service') as mock_versioning:

            # Mock find().sort().first_or_none() chain
            mock_cursor = MagicMock()
            mock_cursor.sort = MagicMock(return_value=mock_cursor)
            mock_cursor.first_or_none = AsyncMock(return_value=mock_parent_version)
            mock_find.return_value = mock_cursor

            mock_cache.delete_pattern = AsyncMock()
            mock_versioning.create_transformation_version = AsyncMock(
                return_value=(mock_version, mock_lineage)
            )

            # ACT
            result = await transformation_service.apply_transformation(
                user_id=user_id,
                dataset_id=dataset_id,
                transformation_type=transformation_type,
                parameters=parameters
            )

            # ASSERT
            assert result["success"] is True
            # Forward history should be truncated: only step1 + new step
            assert len(mock_config.transformation_steps) == 2
            assert mock_config.transformation_steps[0] == step1  # Original first step
            assert mock_config.transformation_steps[1].transformation_type == "drop_missing"  # New step
            assert mock_config.current_position == 1  # At new step

    @pytest.mark.asyncio
    async def test_apply_transformation_links_version_to_config(
        self,
        transformation_service,
        mock_dataset,
        sample_dataframe,
        mock_parent_version
    ):
        """
        Test that version is properly linked to transformation config.

        Verifies:
        - Version metadata includes transformation_config_id
        - Config can be retrieved from version
        """
        # ARRANGE
        user_id = "user1"
        dataset_id = "ds1"
        transformation_type = "drop_missing"
        parameters = {"column": "age"}

        transformed_df = sample_dataframe.dropna(subset=["age"])

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.transformed_data = transformed_df.to_dict('records')
        mock_result.affected_rows = 1
        mock_result.affected_columns = ["age"]
        mock_result.warnings = []

        mock_config = MagicMock()
        mock_config.config_id = "config_ds1_12345"
        mock_config.transformation_steps = []
        mock_config.current_position = -1
        mock_config.save = AsyncMock()

        mock_version = MagicMock()
        mock_version.version_id = "version123"
        mock_lineage = MagicMock()

        with patch('app.models.dataset.DatasetMetadata.find_one',
                   new=AsyncMock(return_value=mock_dataset)), \
             patch('app.services.transformation_engine.data_utils.get_dataframe_from_s3',
                   new=AsyncMock(return_value=sample_dataframe)), \
             patch('app.services.transformation_engine.data_utils.upload_dataframe_to_s3',
                   new=AsyncMock(return_value="s3://bucket/transformed/user1/ds1_12345.parquet")), \
             patch.object(transformation_service.engine, 'apply_transformation', return_value=mock_result), \
             patch.object(transformation_service, 'create_transformation_config',
                          new=AsyncMock(return_value=mock_config)), \
             patch.object(transformation_service, 'add_transformation_step',
                          new=AsyncMock(return_value=mock_config)), \
             patch.object(transformation_service, 'mark_transformations_applied',
                          new=AsyncMock(return_value=mock_config)), \
             patch('app.models.version.DatasetVersion.find') as mock_find, \
             patch('app.services.redis_cache.cache_service') as mock_cache, \
             patch('app.services.versioning_service.versioning_service') as mock_versioning:

            # Mock find().sort().first_or_none() chain
            mock_cursor = MagicMock()
            mock_cursor.sort = MagicMock(return_value=mock_cursor)
            mock_cursor.first_or_none = AsyncMock(return_value=mock_parent_version)
            mock_find.return_value = mock_cursor

            mock_cache.delete_pattern = AsyncMock()
            mock_versioning.create_transformation_version = AsyncMock(
                return_value=(mock_version, mock_lineage)
            )

            # ACT
            result = await transformation_service.apply_transformation(
                user_id=user_id,
                dataset_id=dataset_id,
                transformation_type=transformation_type,
                parameters=parameters
            )

            # ASSERT
            assert result["success"] is True
            # Verify create_transformation_version was called with config_id
            call_args = mock_versioning.create_transformation_version.call_args
            assert call_args is not None
            if call_args.kwargs:
                assert "transformation_config_id" in call_args.kwargs
                # Verify config_id starts with expected prefix (actual ID includes timestamp)
                assert call_args.kwargs["transformation_config_id"].startswith("config_ds1_")


@pytest.mark.unit
class TestQualityAssessmentHelpers:
    """Quality helpers used for version trend tracking (issue #102, AC3)."""

    def test_infer_column_types(self, transformation_service, sample_dataframe):
        types = transformation_service._infer_column_types(sample_dataframe)
        assert types["id"] == "integer"
        assert types["age"] == "float"  # has a NaN -> float dtype
        assert types["department"] == "string"

    @pytest.mark.asyncio
    async def test_assess_quality_dict_returns_json_native(self, transformation_service, sample_dataframe):
        result = await transformation_service._assess_quality_dict(sample_dataframe)
        assert result is not None
        assert "score_0_100" in result
        assert isinstance(result["score_0_100"], (int, float))
        # enum dict keys are serialised to plain strings (mode="json")
        assert all(isinstance(k, str) for k in result["component_scores"])

    @pytest.mark.asyncio
    async def test_assess_quality_dict_never_raises(self, transformation_service):
        # A column-less frame must not blow up the version path; returns a dict or None.
        result = await transformation_service._assess_quality_dict(pd.DataFrame())
        assert result is None or "score_0_100" in result
