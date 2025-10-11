"""
Tests for version models.

Tests DatasetVersion, TransformationLineage, and VersionComparison models.
"""

import pytest
from datetime import datetime, timezone
from app.models.version import (
    DatasetVersion,
    TransformationLineage,
    TransformationStep,
    VersionComparison
)


class TestTransformationStep:
    """Tests for TransformationStep model."""

    def test_transformation_step_creation(self):
        """Test creating a transformation step."""
        step = TransformationStep(
            step_type="drop_missing",
            parameters={"threshold": 0.5},
            affected_columns=["age", "income"],
            rows_affected=100,
            execution_time=1.5
        )

        assert step.step_type == "drop_missing"
        assert step.parameters == {"threshold": 0.5}
        assert step.affected_columns == ["age", "income"]
        assert step.rows_affected == 100
        assert step.execution_time == 1.5

    def test_transformation_step_type_validation(self):
        """Test transformation step type validation."""
        with pytest.raises(ValueError, match="step_type must be one of"):
            TransformationStep(
                step_type="invalid_type",
                parameters={}
            )

    def test_transformation_step_defaults(self):
        """Test transformation step default values."""
        step = TransformationStep(step_type="encode")

        assert step.parameters == {}
        assert step.affected_columns == []
        assert step.rows_affected is None
        assert step.execution_time is None


class TestDatasetVersion:
    """Tests for DatasetVersion model."""

    def test_dataset_version_creation(self):
        """Test creating a dataset version."""
        version = DatasetVersion.model_construct(
            version_id="v1",
            dataset_id="ds1",
            version_number=1,
            user_id="user1",
            content_hash="abc123",
            file_size=1024,
            file_path="path/to/file",
            s3_url="s3://bucket/path",
            num_rows=100,
            num_columns=5,
            columns=["col1", "col2", "col3", "col4", "col5"],
            schema_hash="schema123",
            is_base_version=True,
            created_by="user1"
        )

        assert version.version_id == "v1"
        assert version.dataset_id == "ds1"
        assert version.version_number == 1
        assert version.user_id == "user1"
        assert version.content_hash == "abc123"
        assert version.file_size == 1024
        assert version.num_rows == 100
        assert version.num_columns == 5
        assert len(version.columns) == 5
        assert version.is_base_version is True
        assert version.created_by == "user1"

    def test_dataset_version_defaults(self):
        """Test dataset version default values."""
        version = DatasetVersion.model_construct(
            version_id="v1",
            dataset_id="ds1",
            version_number=1,
            user_id="user1",
            content_hash="abc123",
            file_size=1024,
            file_path="path/to/file",
            s3_url="s3://bucket/path",
            num_rows=100,
            num_columns=5,
            schema_hash="schema123",
            created_by="user1"
        )

        assert version.columns == []
        assert version.tags == []
        assert version.used_in_training == []
        assert version.access_count == 0
        assert version.is_pinned is False
        assert version.is_base_version is False
        assert version.parent_version_id is None
        assert version.transformation_lineage_id is None
        assert version.description is None
        assert version.last_accessed_at is None
        assert version.expires_at is None

    def test_compute_content_hash(self):
        """Test content hash computation."""
        content = b"test content"
        hash1 = DatasetVersion.compute_content_hash(content)
        hash2 = DatasetVersion.compute_content_hash(content)

        assert hash1 == hash2
        assert isinstance(hash1, str)
        assert len(hash1) == 64  # SHA-256 produces 64-character hex

    def test_compute_content_hash_different_content(self):
        """Test that different content produces different hashes."""
        hash1 = DatasetVersion.compute_content_hash(b"content1")
        hash2 = DatasetVersion.compute_content_hash(b"content2")

        assert hash1 != hash2

    def test_compute_schema_hash(self):
        """Test schema hash computation."""
        columns = ["col1", "col2", "col3"]
        dtypes = {"col1": "int64", "col2": "float64", "col3": "object"}

        hash1 = DatasetVersion.compute_schema_hash(columns, dtypes)
        hash2 = DatasetVersion.compute_schema_hash(columns, dtypes)

        assert hash1 == hash2
        assert isinstance(hash1, str)
        assert len(hash1) == 64

    def test_compute_schema_hash_order_independent(self):
        """Test that schema hash is order-independent."""
        columns1 = ["col1", "col2", "col3"]
        columns2 = ["col3", "col1", "col2"]
        dtypes = {"col1": "int64", "col2": "float64", "col3": "object"}

        hash1 = DatasetVersion.compute_schema_hash(columns1, dtypes)
        hash2 = DatasetVersion.compute_schema_hash(columns2, dtypes)

        assert hash1 == hash2

    def test_mark_accessed(self):
        """Test marking version as accessed."""
        version = DatasetVersion.model_construct(
            version_id="v1",
            dataset_id="ds1",
            version_number=1,
            user_id="user1",
            content_hash="abc123",
            file_size=1024,
            file_path="path/to/file",
            s3_url="s3://bucket/path",
            num_rows=100,
            num_columns=5,
            schema_hash="schema123",
            created_by="user1"
        )

        assert version.access_count == 0
        assert version.last_accessed_at is None

        version.mark_accessed()

        assert version.access_count == 1
        assert version.last_accessed_at is not None
        assert isinstance(version.last_accessed_at, datetime)

        # Mark accessed again
        first_access_time = version.last_accessed_at
        version.mark_accessed()

        assert version.access_count == 2
        assert version.last_accessed_at >= first_access_time

    def test_link_to_training(self):
        """Test linking version to training job."""
        version = DatasetVersion.model_construct(
            version_id="v1",
            dataset_id="ds1",
            version_number=1,
            user_id="user1",
            content_hash="abc123",
            file_size=1024,
            file_path="path/to/file",
            s3_url="s3://bucket/path",
            num_rows=100,
            num_columns=5,
            schema_hash="schema123",
            created_by="user1"
        )

        assert len(version.used_in_training) == 0

        version.link_to_training("job1")
        assert version.used_in_training == ["job1"]

        version.link_to_training("job2")
        assert version.used_in_training == ["job1", "job2"]

        # Linking same job twice should not duplicate
        version.link_to_training("job1")
        assert version.used_in_training == ["job1", "job2"]

    def test_pin_version(self):
        """Test pinning a version."""
        version = DatasetVersion.model_construct(
            version_id="v1",
            dataset_id="ds1",
            version_number=1,
            user_id="user1",
            content_hash="abc123",
            file_size=1024,
            file_path="path/to/file",
            s3_url="s3://bucket/path",
            num_rows=100,
            num_columns=5,
            schema_hash="schema123",
            created_by="user1"
        )

        assert version.is_pinned is False

        version.pin_version()
        assert version.is_pinned is True
        assert version.expires_at is None

    def test_unpin_version(self):
        """Test unpinning a version."""
        version = DatasetVersion.model_construct(
            version_id="v1",
            dataset_id="ds1",
            version_number=1,
            user_id="user1",
            content_hash="abc123",
            file_size=1024,
            file_path="path/to/file",
            s3_url="s3://bucket/path",
            num_rows=100,
            num_columns=5,
            schema_hash="schema123",
            created_by="user1"
        )

        version.pin_version()
        assert version.is_pinned is True

        version.unpin_version()
        assert version.is_pinned is False


class TestTransformationLineage:
    """Tests for TransformationLineage model."""

    def test_transformation_lineage_creation(self):
        """Test creating a transformation lineage."""
        steps = [
            TransformationStep(
                step_type="drop_missing",
                parameters={"threshold": 0.5},
                affected_columns=["age"],
                rows_affected=10
            ),
            TransformationStep(
                step_type="encode",
                parameters={"method": "onehot"},
                affected_columns=["category"]
            )
        ]

        lineage = TransformationLineage.model_construct(
            lineage_id="lin1",
            parent_version_id="v1",
            child_version_id="v2",
            dataset_id="ds1",
            user_id="user1",
            transformation_steps=steps,
            rows_before=1000,
            rows_after=990,
            columns_before=10,
            columns_after=15
        )

        assert lineage.lineage_id == "lin1"
        assert lineage.parent_version_id == "v1"
        assert lineage.child_version_id == "v2"
        assert lineage.dataset_id == "ds1"
        assert lineage.user_id == "user1"
        assert len(lineage.transformation_steps) == 2
        assert lineage.rows_before == 1000
        assert lineage.rows_after == 990
        assert lineage.columns_before == 10
        assert lineage.columns_after == 15

    def test_transformation_lineage_defaults(self):
        """Test transformation lineage default values."""
        lineage = TransformationLineage.model_construct(
            lineage_id="lin1",
            parent_version_id="v1",
            child_version_id="v2",
            dataset_id="ds1",
            user_id="user1",
            rows_before=1000,
            rows_after=990,
            columns_before=10,
            columns_after=15
        )

        assert lineage.transformation_steps == []
        assert lineage.transformation_config_id is None
        assert lineage.total_execution_time is None
        assert lineage.data_loss_percentage == 0.0
        assert lineage.quality_before is None
        assert lineage.quality_after is None
        assert lineage.quality_improvement is None
        assert lineage.is_reproducible is True
        assert lineage.reproducibility_notes is None
        assert lineage.is_validated is False
        assert lineage.validation_status is None
        assert lineage.validation_errors == []
        assert lineage.completed_at is None

    def test_calculate_data_loss(self):
        """Test data loss calculation."""
        lineage = TransformationLineage.model_construct(
            lineage_id="lin1",
            parent_version_id="v1",
            child_version_id="v2",
            dataset_id="ds1",
            user_id="user1",
            rows_before=1000,
            rows_after=800,
            columns_before=10,
            columns_after=10
        )

        data_loss = lineage.calculate_data_loss()
        assert data_loss == 20.0  # 200/1000 = 20%

    def test_calculate_data_loss_no_loss(self):
        """Test data loss calculation with no loss."""
        lineage = TransformationLineage.model_construct(
            lineage_id="lin1",
            parent_version_id="v1",
            child_version_id="v2",
            dataset_id="ds1",
            user_id="user1",
            rows_before=1000,
            rows_after=1000,
            columns_before=10,
            columns_after=10
        )

        data_loss = lineage.calculate_data_loss()
        assert data_loss == 0.0

    def test_calculate_data_loss_zero_rows(self):
        """Test data loss calculation with zero rows before."""
        lineage = TransformationLineage.model_construct(
            lineage_id="lin1",
            parent_version_id="v1",
            child_version_id="v2",
            dataset_id="ds1",
            user_id="user1",
            rows_before=0,
            rows_after=0,
            columns_before=10,
            columns_after=10
        )

        data_loss = lineage.calculate_data_loss()
        assert data_loss == 0.0

    def test_mark_completed(self):
        """Test marking lineage as completed."""
        lineage = TransformationLineage.model_construct(
            lineage_id="lin1",
            parent_version_id="v1",
            child_version_id="v2",
            dataset_id="ds1",
            user_id="user1",
            rows_before=1000,
            rows_after=900,
            columns_before=10,
            columns_after=10
        )

        assert lineage.completed_at is None
        assert lineage.data_loss_percentage == 0.0

        lineage.mark_completed()

        assert lineage.completed_at is not None
        assert isinstance(lineage.completed_at, datetime)
        assert lineage.data_loss_percentage == 10.0  # 100/1000 = 10%

    def test_add_validation_error(self):
        """Test adding validation errors."""
        lineage = TransformationLineage.model_construct(
            lineage_id="lin1",
            parent_version_id="v1",
            child_version_id="v2",
            dataset_id="ds1",
            user_id="user1",
            rows_before=1000,
            rows_after=900,
            columns_before=10,
            columns_after=10
        )

        assert len(lineage.validation_errors) == 0
        assert lineage.validation_status is None
        assert lineage.is_validated is False

        lineage.add_validation_error("Error 1")

        assert len(lineage.validation_errors) == 1
        assert lineage.validation_errors[0] == "Error 1"
        assert lineage.validation_status == "failed"
        assert lineage.is_validated is True

        lineage.add_validation_error("Error 2")
        assert len(lineage.validation_errors) == 2

    def test_mark_validated(self):
        """Test marking lineage as validated."""
        lineage = TransformationLineage.model_construct(
            lineage_id="lin1",
            parent_version_id="v1",
            child_version_id="v2",
            dataset_id="ds1",
            user_id="user1",
            rows_before=1000,
            rows_after=900,
            columns_before=10,
            columns_after=10
        )

        assert lineage.is_validated is False
        assert lineage.validation_status is None

        lineage.mark_validated(passed=True)
        assert lineage.is_validated is True
        assert lineage.validation_status == "passed"

        lineage.mark_validated(passed=False)
        assert lineage.validation_status == "failed"

    def test_validation_status_validation(self):
        """Test validation status field validation."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError, match="validation_status must be one of"):
            TransformationLineage.model_validate({
                "lineage_id": "lin1",
                "parent_version_id": "v1",
                "child_version_id": "v2",
                "dataset_id": "ds1",
                "user_id": "user1",
                "rows_before": 1000,
                "rows_after": 900,
                "columns_before": 10,
                "columns_after": 10,
                "validation_status": "invalid_status"
            })

    def test_get_transformation_summary(self):
        """Test getting transformation summary."""
        steps = [
            TransformationStep(
                step_type="drop_missing",
                parameters={"threshold": 0.5},
                affected_columns=["age", "income"],
                rows_affected=10,
                execution_time=1.5
            ),
            TransformationStep(
                step_type="encode",
                parameters={"method": "onehot"},
                affected_columns=["category", "region"],
                execution_time=2.3
            )
        ]

        lineage = TransformationLineage.model_construct(
            lineage_id="lin1",
            parent_version_id="v1",
            child_version_id="v2",
            dataset_id="ds1",
            user_id="user1",
            transformation_steps=steps,
            total_execution_time=3.8,
            rows_before=1000,
            rows_after=990,
            columns_before=10,
            columns_after=15,
            data_loss_percentage=1.0
        )

        summary = lineage.get_transformation_summary()

        assert summary["total_steps"] == 2
        assert summary["step_types"] == ["drop_missing", "encode"]
        assert set(summary["affected_columns"]) == {"age", "income", "category", "region"}
        assert summary["data_loss_percentage"] == 1.0
        assert summary["execution_time"] == 3.8
        assert summary["is_reproducible"] is True


class TestVersionComparison:
    """Tests for VersionComparison model."""

    def test_version_comparison_creation(self):
        """Test creating a version comparison."""
        comparison = VersionComparison(
            version1_id="v1",
            version2_id="v2",
            rows_diff=100,
            columns_diff=2,
            columns_added=["new_col1", "new_col2"],
            columns_removed=["old_col"],
            schema_identical=False,
            content_similarity=75.5,
            lineage_path=["lin1", "lin2"],
            transformation_count=2
        )

        assert comparison.version1_id == "v1"
        assert comparison.version2_id == "v2"
        assert comparison.rows_diff == 100
        assert comparison.columns_diff == 2
        assert len(comparison.columns_added) == 2
        assert len(comparison.columns_removed) == 1
        assert comparison.schema_identical is False
        assert comparison.content_similarity == 75.5
        assert len(comparison.lineage_path) == 2
        assert comparison.transformation_count == 2

    def test_version_comparison_defaults(self):
        """Test version comparison default values."""
        comparison = VersionComparison(
            version1_id="v1",
            version2_id="v2",
            rows_diff=0,
            columns_diff=0
        )

        assert comparison.columns_added == []
        assert comparison.columns_removed == []
        assert comparison.columns_renamed == {}
        assert comparison.dtype_changes == {}
        assert comparison.content_similarity == 0.0
        assert comparison.schema_identical is False
        assert comparison.lineage_path == []
        assert comparison.transformation_count == 0
        assert comparison.compared_at is not None
        assert isinstance(comparison.compared_at, datetime)

    def test_version_comparison_identical_versions(self):
        """Test comparison of identical versions."""
        comparison = VersionComparison(
            version1_id="v1",
            version2_id="v1",  # Same version
            rows_diff=0,
            columns_diff=0,
            schema_identical=True,
            content_similarity=100.0
        )

        assert comparison.rows_diff == 0
        assert comparison.columns_diff == 0
        assert comparison.schema_identical is True
        assert comparison.content_similarity == 100.0
        assert comparison.transformation_count == 0
