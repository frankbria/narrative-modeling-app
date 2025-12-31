"""
Tests for Feature Store models - Unit tests only (no database required).

Following TDD methodology:
1. RED: Write failing tests first
2. GREEN: Implement models to pass tests
3. REFACTOR: Improve code quality

Tests cover:
- StoredFeature model creation and validation
- FeatureVersion model
- FeatureCollection model
- Field validators
- Helper methods
- Edge cases and error conditions
"""

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError
from app.models.feature_store import (
    StoredFeature,
    FeatureVersion,
    FeatureCollection,
    get_current_time
)


class TestGetCurrentTime:
    """Tests for get_current_time utility function."""

    def test_get_current_time_returns_datetime(self):
        """🔴 RED: Test that get_current_time returns a datetime object."""
        current_time = get_current_time()
        assert isinstance(current_time, datetime)

    def test_get_current_time_has_utc_timezone(self):
        """🔴 RED: Test that returned datetime has UTC timezone."""
        current_time = get_current_time()
        assert current_time.tzinfo == timezone.utc


class TestStoredFeature:
    """Tests for StoredFeature model."""

    def test_create_stored_feature_with_minimal_data(self):
        """🔴 RED: Test creating a StoredFeature with minimal required fields."""
        # ARRANGE & ACT: Using model_construct to avoid database operations
        feature_data = {
            "feature_id": "feat_123",
            "user_id": "user_456",
            "name": "Test Feature",
            "description": "A test feature for unit testing",
            "category": "transformation",
            "tags": ["test", "numeric"],
            "definition_type": "transformation",
            "definition_code": "df['new_col'] = df['old_col'] * 2",
            "input_requirements": {"old_col": "numeric"},
            "output_type": "numeric",
            "output_column_name": "new_col",
            "version": 1,
            "is_public": False,
            "shared_with": [],
            "usage_count": 0,
            "created_by": "user_456"
        }

        feature = StoredFeature.model_construct(**feature_data)

        # ASSERT
        assert feature.feature_id == "feat_123"
        assert feature.user_id == "user_456"
        assert feature.name == "Test Feature"
        assert feature.description == "A test feature for unit testing"
        assert feature.category == "transformation"
        assert feature.tags == ["test", "numeric"]
        assert feature.definition_type == "transformation"
        assert feature.definition_code == "df['new_col'] = df['old_col'] * 2"
        assert feature.input_requirements == {"old_col": "numeric"}
        assert feature.output_type == "numeric"
        assert feature.output_column_name == "new_col"
        assert feature.version == 1
        assert feature.is_public is False
        assert feature.usage_count == 0

    def test_create_stored_feature_with_all_fields(self):
        """🔴 RED: Test creating StoredFeature with all optional fields."""
        feature_data = {
            "feature_id": "feat_full",
            "user_id": "user_789",
            "name": "Full Feature",
            "description": "Feature with all fields",
            "category": "aggregation",
            "tags": ["complete", "tested"],
            "definition_type": "aggregation",
            "definition_code": "df.groupby('category')['value'].sum()",
            "input_requirements": {"category": "categorical", "value": "numeric"},
            "output_type": "numeric",
            "output_column_name": "category_sum",
            "version": 3,
            "is_public": True,
            "shared_with": ["user_001", "user_002"],
            "usage_count": 42,
            "last_used_at": datetime.now(timezone.utc),
            "applied_to_datasets": ["dataset_1", "dataset_2"],
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "created_by": "user_789"
        }

        feature = StoredFeature.model_construct(**feature_data)

        assert feature.feature_id == "feat_full"
        assert feature.version == 3
        assert feature.is_public is True
        assert len(feature.shared_with) == 2
        assert feature.usage_count == 42
        assert len(feature.applied_to_datasets) == 2

    def test_stored_feature_validates_definition_type(self):
        """🔴 RED: Test that invalid definition_type raises ValidationError."""
        # Test the validator function directly
        with pytest.raises(ValueError) as exc_info:
            StoredFeature.validate_definition_type("invalid_type")
        assert "definition_type must be one of" in str(exc_info.value)

    def test_stored_feature_all_definition_types(self):
        """🔴 RED: Test all valid definition_type values."""
        valid_types = ['transformation', 'aggregation', 'encoding', 'custom']

        for def_type in valid_types:
            feature_data = {
                "feature_id": f"feat_{def_type}",
                "user_id": "user_123",
                "name": f"{def_type.title()} Feature",
                "description": "Test",
                "category": "test",
                "tags": [],
                "definition_type": def_type,
                "definition_code": "code",
                "input_requirements": {},
                "output_type": "numeric",
                "output_column_name": "output",
                "version": 1,
                "is_public": False,
                "shared_with": [],
                "usage_count": 0,
                "created_by": "user_123"
            }

            feature = StoredFeature.model_construct(**feature_data)
            assert feature.definition_type == def_type

    def test_stored_feature_increment_usage(self):
        """🔴 RED: Test increment_usage() method."""
        feature_data = {
            "feature_id": "feat_usage",
            "user_id": "user_123",
            "name": "Usage Test",
            "description": "Test usage increment",
            "category": "test",
            "tags": [],
            "definition_type": "transformation",
            "definition_code": "code",
            "input_requirements": {},
            "output_type": "numeric",
            "output_column_name": "output",
            "version": 1,
            "is_public": False,
            "shared_with": [],
            "usage_count": 0,
            "created_by": "user_123"
        }

        feature = StoredFeature.model_construct(**feature_data)
        initial_count = feature.usage_count
        initial_last_used = feature.last_used_at

        # Increment usage
        feature.increment_usage()

        assert feature.usage_count == initial_count + 1
        assert feature.last_used_at is not None
        if initial_last_used:
            assert feature.last_used_at > initial_last_used

    def test_stored_feature_update_timestamp(self):
        """🔴 RED: Test update_timestamp() method."""
        feature_data = {
            "feature_id": "feat_timestamp",
            "user_id": "user_123",
            "name": "Timestamp Test",
            "description": "Test timestamp update",
            "category": "test",
            "tags": [],
            "definition_type": "transformation",
            "definition_code": "code",
            "input_requirements": {},
            "output_type": "numeric",
            "output_column_name": "output",
            "version": 1,
            "is_public": False,
            "shared_with": [],
            "usage_count": 0,
            "created_by": "user_123"
        }

        feature = StoredFeature.model_construct(**feature_data)
        original_updated_at = feature.updated_at

        # Update timestamp
        feature.update_timestamp()

        assert feature.updated_at > original_updated_at

    def test_stored_feature_check_compatibility_compatible(self):
        """🔴 RED: Test check_compatibility() with compatible schema."""
        feature_data = {
            "feature_id": "feat_compat",
            "user_id": "user_123",
            "name": "Compatibility Test",
            "description": "Test compatibility checking",
            "category": "test",
            "tags": [],
            "definition_type": "transformation",
            "definition_code": "code",
            "input_requirements": {"age": "numeric", "name": "text"},
            "output_type": "numeric",
            "output_column_name": "age_category",
            "version": 1,
            "is_public": False,
            "shared_with": [],
            "usage_count": 0,
            "created_by": "user_123"
        }

        feature = StoredFeature.model_construct(**feature_data)

        # Mock dataset schema (list of SchemaField-like dicts)
        dataset_schema = [
            {"field_name": "age", "field_type": "numeric", "inferred_dtype": "int64"},
            {"field_name": "name", "field_type": "text", "inferred_dtype": "object"},
            {"field_name": "city", "field_type": "text", "inferred_dtype": "object"}
        ]

        is_compatible, missing, mismatches = feature.check_compatibility(dataset_schema)

        assert is_compatible is True
        assert len(missing) == 0
        assert len(mismatches) == 0

    def test_stored_feature_check_compatibility_missing_columns(self):
        """🔴 RED: Test check_compatibility() with missing columns."""
        feature_data = {
            "feature_id": "feat_missing",
            "user_id": "user_123",
            "name": "Missing Test",
            "description": "Test missing columns",
            "category": "test",
            "tags": [],
            "definition_type": "transformation",
            "definition_code": "code",
            "input_requirements": {"age": "numeric", "salary": "numeric", "name": "text"},
            "output_type": "numeric",
            "output_column_name": "output",
            "version": 1,
            "is_public": False,
            "shared_with": [],
            "usage_count": 0,
            "created_by": "user_123"
        }

        feature = StoredFeature.model_construct(**feature_data)

        # Dataset missing 'salary' column
        dataset_schema = [
            {"field_name": "age", "field_type": "numeric", "inferred_dtype": "int64"},
            {"field_name": "name", "field_type": "text", "inferred_dtype": "object"}
        ]

        is_compatible, missing, mismatches = feature.check_compatibility(dataset_schema)

        assert is_compatible is False
        assert "salary" in missing
        assert len(missing) == 1

    def test_stored_feature_check_compatibility_type_mismatch(self):
        """🔴 RED: Test check_compatibility() with type mismatches."""
        feature_data = {
            "feature_id": "feat_mismatch",
            "user_id": "user_123",
            "name": "Mismatch Test",
            "description": "Test type mismatches",
            "category": "test",
            "tags": [],
            "definition_type": "transformation",
            "definition_code": "code",
            "input_requirements": {"age": "numeric", "name": "text"},
            "output_type": "numeric",
            "output_column_name": "output",
            "version": 1,
            "is_public": False,
            "shared_with": [],
            "usage_count": 0,
            "created_by": "user_123"
        }

        feature = StoredFeature.model_construct(**feature_data)

        # Dataset has 'age' as text instead of numeric
        dataset_schema = [
            {"field_name": "age", "field_type": "text", "inferred_dtype": "object"},
            {"field_name": "name", "field_type": "text", "inferred_dtype": "object"}
        ]

        is_compatible, missing, mismatches = feature.check_compatibility(dataset_schema)

        assert is_compatible is False
        assert len(missing) == 0
        assert "age" in mismatches
        assert mismatches["age"]["expected"] == "numeric"
        assert mismatches["age"]["actual"] == "text"

    def test_stored_feature_to_dict(self):
        """🔴 RED: Test to_dict() method."""
        feature_data = {
            "feature_id": "feat_dict",
            "user_id": "user_123",
            "name": "Dict Test",
            "description": "Test dict conversion",
            "category": "test",
            "tags": ["tag1"],
            "definition_type": "transformation",
            "definition_code": "code",
            "input_requirements": {"col": "numeric"},
            "output_type": "numeric",
            "output_column_name": "output",
            "version": 1,
            "is_public": False,
            "shared_with": [],
            "usage_count": 5,
            "created_by": "user_123"
        }

        feature = StoredFeature.model_construct(**feature_data)
        feature_dict = feature.to_dict()

        assert isinstance(feature_dict, dict)
        assert feature_dict["feature_id"] == "feat_dict"
        assert feature_dict["name"] == "Dict Test"
        assert feature_dict["usage_count"] == 5
        assert "created_at" in feature_dict
        assert "updated_at" in feature_dict


class TestFeatureVersion:
    """Tests for FeatureVersion model."""

    def test_create_feature_version_with_minimal_data(self):
        """🔴 RED: Test creating a FeatureVersion with required fields."""
        version_data = {
            "version_id": "ver_123",
            "feature_id": "feat_456",
            "version_number": 1,
            "definition_code": "df['new'] = df['old'] * 2",
            "definition_type": "transformation",
            "input_requirements": {"old": "numeric"},
            "output_type": "numeric",
            "changes_description": "Initial version",
            "changed_fields": [],
            "created_by": "user_789",
            "created_at": datetime.now(timezone.utc)
        }

        version = FeatureVersion.model_construct(**version_data)

        assert version.version_id == "ver_123"
        assert version.feature_id == "feat_456"
        assert version.version_number == 1
        assert version.definition_code == "df['new'] = df['old'] * 2"
        assert version.definition_type == "transformation"
        assert version.changes_description == "Initial version"
        assert version.created_by == "user_789"

    def test_create_feature_version_with_changes(self):
        """🔴 RED: Test creating FeatureVersion with change tracking."""
        version_data = {
            "version_id": "ver_change",
            "feature_id": "feat_456",
            "version_number": 2,
            "definition_code": "df['new'] = df['old'] * 3",
            "definition_type": "transformation",
            "input_requirements": {"old": "numeric"},
            "output_type": "numeric",
            "changes_description": "Changed multiplier from 2 to 3",
            "changed_fields": ["definition_code"],
            "created_by": "user_789",
            "created_at": datetime.now(timezone.utc)
        }

        version = FeatureVersion.model_construct(**version_data)

        assert version.version_number == 2
        assert "definition_code" in version.changed_fields
        assert "multiplier" in version.changes_description.lower()

    def test_feature_version_get_diff(self):
        """🔴 RED: Test get_diff() method comparing two versions."""
        version1_data = {
            "version_id": "ver_1",
            "feature_id": "feat_diff",
            "version_number": 1,
            "definition_code": "df['new'] = df['old'] * 2",
            "definition_type": "transformation",
            "input_requirements": {"old": "numeric"},
            "output_type": "numeric",
            "changes_description": "Initial",
            "changed_fields": [],
            "created_by": "user_123",
            "created_at": datetime.now(timezone.utc)
        }

        version2_data = {
            "version_id": "ver_2",
            "feature_id": "feat_diff",
            "version_number": 2,
            "definition_code": "df['new'] = df['old'] * 3",
            "definition_type": "transformation",
            "input_requirements": {"old": "numeric"},
            "output_type": "numeric",
            "changes_description": "Changed multiplier",
            "changed_fields": ["definition_code"],
            "created_by": "user_123",
            "created_at": datetime.now(timezone.utc)
        }

        version1 = FeatureVersion.model_construct(**version1_data)
        version2 = FeatureVersion.model_construct(**version2_data)

        diff = version2.get_diff(version1)

        assert isinstance(diff, dict)
        assert "version_number" in diff
        assert diff["version_number"]["from"] == 1
        assert diff["version_number"]["to"] == 2
        assert "definition_code" in diff


class TestFeatureCollection:
    """Tests for FeatureCollection model."""

    def test_create_feature_collection_with_minimal_data(self):
        """🔴 RED: Test creating a FeatureCollection with required fields."""
        collection_data = {
            "collection_id": "coll_123",
            "user_id": "user_456",
            "name": "Test Collection",
            "description": "A collection of test features",
            "domain": "finance",
            "feature_ids": ["feat_1", "feat_2", "feat_3"],
            "feature_count": 3,
            "is_public": False,
            "shared_with": [],
            "tags": ["test", "finance"],
            "created_by": "user_456"
        }

        collection = FeatureCollection.model_construct(**collection_data)

        assert collection.collection_id == "coll_123"
        assert collection.user_id == "user_456"
        assert collection.name == "Test Collection"
        assert collection.domain == "finance"
        assert len(collection.feature_ids) == 3
        assert collection.feature_count == 3
        assert collection.is_public is False

    def test_create_feature_collection_with_all_fields(self):
        """🔴 RED: Test creating FeatureCollection with all optional fields."""
        collection_data = {
            "collection_id": "coll_full",
            "user_id": "user_789",
            "name": "Full Collection",
            "description": "Complete collection",
            "domain": "healthcare",
            "feature_ids": ["feat_a", "feat_b"],
            "feature_count": 2,
            "is_public": True,
            "shared_with": ["user_001"],
            "tags": ["complete", "healthcare"],
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "created_by": "user_789"
        }

        collection = FeatureCollection.model_construct(**collection_data)

        assert collection.is_public is True
        assert len(collection.shared_with) == 1
        assert collection.domain == "healthcare"

    def test_feature_collection_add_feature(self):
        """🔴 RED: Test add_feature() method."""
        collection_data = {
            "collection_id": "coll_add",
            "user_id": "user_123",
            "name": "Add Test",
            "description": "Test adding features",
            "domain": "retail",
            "feature_ids": ["feat_1"],
            "feature_count": 1,
            "is_public": False,
            "shared_with": [],
            "tags": [],
            "created_by": "user_123"
        }

        collection = FeatureCollection.model_construct(**collection_data)
        initial_count = collection.feature_count

        # Add feature
        collection.add_feature("feat_2")

        assert "feat_2" in collection.feature_ids
        assert collection.feature_count == initial_count + 1
        assert len(collection.feature_ids) == collection.feature_count

    def test_feature_collection_add_duplicate_feature(self):
        """🔴 RED: Test add_feature() with duplicate ID (should not add)."""
        collection_data = {
            "collection_id": "coll_dup",
            "user_id": "user_123",
            "name": "Duplicate Test",
            "description": "Test duplicate handling",
            "domain": "retail",
            "feature_ids": ["feat_1", "feat_2"],
            "feature_count": 2,
            "is_public": False,
            "shared_with": [],
            "tags": [],
            "created_by": "user_123"
        }

        collection = FeatureCollection.model_construct(**collection_data)
        initial_count = collection.feature_count

        # Try to add duplicate
        collection.add_feature("feat_1")

        # Should not add duplicate
        assert collection.feature_count == initial_count
        assert collection.feature_ids.count("feat_1") == 1

    def test_feature_collection_remove_feature(self):
        """🔴 RED: Test remove_feature() method."""
        collection_data = {
            "collection_id": "coll_remove",
            "user_id": "user_123",
            "name": "Remove Test",
            "description": "Test removing features",
            "domain": "retail",
            "feature_ids": ["feat_1", "feat_2", "feat_3"],
            "feature_count": 3,
            "is_public": False,
            "shared_with": [],
            "tags": [],
            "created_by": "user_123"
        }

        collection = FeatureCollection.model_construct(**collection_data)
        initial_count = collection.feature_count

        # Remove feature
        collection.remove_feature("feat_2")

        assert "feat_2" not in collection.feature_ids
        assert collection.feature_count == initial_count - 1
        assert len(collection.feature_ids) == collection.feature_count

    def test_feature_collection_remove_nonexistent_feature(self):
        """🔴 RED: Test remove_feature() with non-existent ID (should handle gracefully)."""
        collection_data = {
            "collection_id": "coll_nonexist",
            "user_id": "user_123",
            "name": "Nonexistent Test",
            "description": "Test nonexistent removal",
            "domain": "retail",
            "feature_ids": ["feat_1"],
            "feature_count": 1,
            "is_public": False,
            "shared_with": [],
            "tags": [],
            "created_by": "user_123"
        }

        collection = FeatureCollection.model_construct(**collection_data)
        initial_count = collection.feature_count

        # Try to remove non-existent feature
        collection.remove_feature("feat_nonexist")

        # Should not change anything
        assert collection.feature_count == initial_count
