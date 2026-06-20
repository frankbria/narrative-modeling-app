"""
Feature Store models for MongoDB.

This module provides models for storing, versioning, and managing reusable
feature definitions that can be applied across datasets.

Models:
- StoredFeature: Main feature definition with metadata and usage tracking
- FeatureVersion: Version history for feature definitions
- FeatureCollection: Organized groups of related features
"""

from datetime import UTC, datetime
from typing import Annotated, Any

from beanie import Document, Indexed, PydanticObjectId
from pydantic import Field, field_validator


def get_current_time() -> datetime:
    """Get current UTC time for default timestamps."""
    return datetime.now(UTC)


class StoredFeature(Document):
    """
    Stored feature definition document.

    Represents a reusable feature engineering operation that can be applied
    to datasets. Includes metadata, versioning, usage tracking, and sharing capabilities.
    """

    # Identification
    feature_id: Annotated[str, Indexed()] = Field(..., description="Unique feature identifier")
    user_id: Annotated[str, Indexed()] = Field(..., description="User who owns this feature")

    # Basic metadata
    name: str = Field(..., description="Human-readable feature name")
    description: str = Field(..., description="Description of what the feature does")
    category: Annotated[str, Indexed()] = Field(..., description="Feature category for organization")
    tags: list[str] = Field(default_factory=list, description="User-defined tags for discovery")

    # Feature definition
    definition_type: str = Field(..., description="Type: transformation, aggregation, encoding, custom")
    definition_code: str = Field(..., description="Serialized feature logic (code or config)")
    input_requirements: dict[str, str] = Field(
        default_factory=dict,
        description="Required input columns and their types"
    )

    # Output specification
    output_type: str = Field(..., description="Output data type: numeric, categorical, text, boolean")
    output_column_name: str = Field(..., description="Name of the generated column")

    # Versioning
    version: int = Field(default=1, ge=1, description="Current version number")

    # Sharing and permissions
    is_public: bool = Field(default=False, description="Whether feature is publicly accessible")
    shared_with: list[str] = Field(default_factory=list, description="User IDs with shared access")

    # Usage tracking
    usage_count: int = Field(default=0, ge=0, description="Number of times feature has been applied")
    last_used_at: datetime | None = Field(None, description="Last time feature was used")
    applied_to_datasets: list[str] = Field(
        default_factory=list,
        description="Dataset IDs where this feature has been applied"
    )

    # Timestamps
    created_at: datetime = Field(default_factory=get_current_time, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=get_current_time, description="Last update timestamp")
    created_by: str = Field(..., description="User ID who created this feature")

    class Settings:
        name = "feature_store"
        indexes = [
            # Single field indexes
            "feature_id",
            "user_id",
            "category",
            "is_public",
            "created_at",
            # Compound indexes for common query patterns
            [("user_id", 1), ("created_at", -1)],  # User's features chronologically
            [("category", 1), ("is_public", 1)],  # Public features by category
            [("is_public", 1), ("created_at", -1)],  # Recent public features
            [("user_id", 1), ("category", 1)],  # User's features by category
            # Text search index for name and description
            [("name", "text"), ("description", "text")],
        ]

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {
            PydanticObjectId: str,
            datetime: lambda dt: dt.isoformat()
        }
    }

    @field_validator('definition_type')
    @classmethod
    def validate_definition_type(cls, v: str) -> str:
        """Validate definition_type is one of allowed values."""
        allowed_types = {'transformation', 'aggregation', 'encoding', 'custom'}
        if v not in allowed_types:
            raise ValueError(f"definition_type must be one of {allowed_types}, got: {v}")
        return v

    @field_validator('output_type')
    @classmethod
    def validate_output_type(cls, v: str) -> str:
        """Validate output_type is one of allowed values."""
        allowed_types = {'numeric', 'categorical', 'text', 'boolean'}
        if v not in allowed_types:
            raise ValueError(f"output_type must be one of {allowed_types}, got: {v}")
        return v

    def increment_usage(self) -> None:
        """Increment usage count and update last_used_at timestamp."""
        self.usage_count += 1
        self.last_used_at = get_current_time()

    def update_timestamp(self) -> None:
        """Update the updated_at timestamp to current time."""
        self.updated_at = get_current_time()

    def check_compatibility(self, dataset_schema: list[dict[str, Any]]) -> tuple[bool, list[str], dict[str, dict[str, str]]]:
        """
        Check if feature is compatible with a dataset schema.

        Args:
            dataset_schema: List of schema field dictionaries with field_name and field_type

        Returns:
            Tuple of (is_compatible, missing_columns, type_mismatches)
            - is_compatible: True if all requirements are met
            - missing_columns: List of required columns not in dataset
            - type_mismatches: Dict of {column: {expected: type, actual: type}}
        """
        # Build lookup for dataset columns
        dataset_columns = {field["field_name"]: field["field_type"] for field in dataset_schema}

        missing_columns = []
        type_mismatches = {}

        # Check each required input column
        for required_col, required_type in self.input_requirements.items():
            if required_col not in dataset_columns:
                missing_columns.append(required_col)
            elif dataset_columns[required_col] != required_type:
                type_mismatches[required_col] = {
                    "expected": required_type,
                    "actual": dataset_columns[required_col]
                }

        is_compatible = len(missing_columns) == 0 and len(type_mismatches) == 0

        return is_compatible, missing_columns, type_mismatches

    def to_dict(self) -> dict[str, Any]:
        """
        Convert feature to dictionary representation.

        Returns:
            Dictionary representation of the feature
        """
        return {
            "feature_id": self.feature_id,
            "user_id": self.user_id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "tags": self.tags,
            "definition_type": self.definition_type,
            "definition_code": self.definition_code,
            "input_requirements": self.input_requirements,
            "output_type": self.output_type,
            "output_column_name": self.output_column_name,
            "version": self.version,
            "is_public": self.is_public,
            "shared_with": self.shared_with,
            "usage_count": self.usage_count,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "applied_to_datasets": self.applied_to_datasets,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "created_by": self.created_by
        }


class FeatureVersion(Document):
    """
    Feature version tracking document.

    Records historical versions of feature definitions to enable
    version comparison, rollback, and change tracking.
    """

    # Version identification
    version_id: Annotated[str, Indexed()] = Field(..., description="Unique version identifier")
    feature_id: Annotated[str, Indexed()] = Field(..., description="Parent feature identifier")
    version_number: int = Field(..., ge=1, description="Sequential version number")

    # Version snapshot
    definition_code: str = Field(..., description="Feature definition code at this version")
    definition_type: str = Field(..., description="Feature definition type")
    input_requirements: dict[str, str] = Field(
        default_factory=dict,
        description="Input requirements at this version"
    )
    output_type: str = Field(..., description="Output type at this version")

    # Change tracking
    changes_description: str = Field(..., description="Description of changes in this version")
    changed_fields: list[str] = Field(
        default_factory=list,
        description="List of fields that changed from previous version"
    )

    # Metadata
    created_by: str = Field(..., description="User who created this version")
    created_at: datetime = Field(default_factory=get_current_time, description="Version creation time")

    class Settings:
        name = "feature_versions"
        indexes = [
            "version_id",
            "feature_id",
            "created_at",
            [("feature_id", 1), ("version_number", -1)],  # Latest versions first
            [("feature_id", 1), ("created_at", -1)],  # Chronological versions
        ]

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {
            PydanticObjectId: str,
            datetime: lambda dt: dt.isoformat()
        }
    }

    @field_validator('definition_type')
    @classmethod
    def validate_definition_type(cls, v: str) -> str:
        """Validate definition_type is one of allowed values."""
        allowed_types = {'transformation', 'aggregation', 'encoding', 'custom'}
        if v not in allowed_types:
            raise ValueError(f"definition_type must be one of {allowed_types}, got: {v}")
        return v

    def get_diff(self, previous_version: "FeatureVersion") -> dict[str, dict[str, Any]]:
        """
        Compare this version with a previous version.

        Args:
            previous_version: Previous FeatureVersion to compare against

        Returns:
            Dictionary of differences with {field: {from: value, to: value}}
        """
        diff: dict[str, dict[str, Any]] = {}

        # Compare version number
        if self.version_number != previous_version.version_number:
            diff["version_number"] = {
                "from": previous_version.version_number,
                "to": self.version_number
            }

        # Compare definition code
        if self.definition_code != previous_version.definition_code:
            diff["definition_code"] = {
                "from": previous_version.definition_code,
                "to": self.definition_code
            }

        # Compare definition type
        if self.definition_type != previous_version.definition_type:
            diff["definition_type"] = {
                "from": previous_version.definition_type,
                "to": self.definition_type
            }

        # Compare input requirements
        if self.input_requirements != previous_version.input_requirements:
            diff["input_requirements"] = {
                "from": previous_version.input_requirements,
                "to": self.input_requirements
            }

        # Compare output type
        if self.output_type != previous_version.output_type:
            diff["output_type"] = {
                "from": previous_version.output_type,
                "to": self.output_type
            }

        return diff


class FeatureCollection(Document):
    """
    Feature collection document.

    Groups related features together for organization and batch application.
    Collections can be shared and used to apply multiple features at once.
    """

    # Identification
    collection_id: Annotated[str, Indexed()] = Field(..., description="Unique collection identifier")
    user_id: Annotated[str, Indexed()] = Field(..., description="User who owns this collection")

    # Basic metadata
    name: str = Field(..., description="Collection name")
    description: str = Field(..., description="Description of the collection")
    domain: Annotated[str, Indexed()] = Field(..., description="Domain/industry: finance, healthcare, retail, etc.")

    # Features in collection
    feature_ids: list[str] = Field(default_factory=list, description="List of feature IDs in collection")
    feature_count: int = Field(default=0, ge=0, description="Number of features in collection")

    # Sharing
    is_public: bool = Field(default=False, description="Whether collection is publicly accessible")
    shared_with: list[str] = Field(default_factory=list, description="User IDs with shared access")

    # Tags for organization
    tags: list[str] = Field(default_factory=list, description="User-defined tags")

    # Timestamps
    created_at: datetime = Field(default_factory=get_current_time, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=get_current_time, description="Last update timestamp")
    created_by: str = Field(..., description="User ID who created this collection")

    class Settings:
        name = "feature_collections"
        indexes = [
            "collection_id",
            "user_id",
            "domain",
            "is_public",
            [("user_id", 1), ("domain", 1)],  # User's collections by domain
            [("is_public", 1), ("domain", 1)],  # Public collections by domain
            [("user_id", 1), ("created_at", -1)],  # User's collections chronologically
        ]

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {
            PydanticObjectId: str,
            datetime: lambda dt: dt.isoformat()
        }
    }

    def add_feature(self, feature_id: str) -> None:
        """
        Add a feature to the collection.

        Args:
            feature_id: ID of feature to add
        """
        # Only add if not already in collection
        if feature_id not in self.feature_ids:
            self.feature_ids.append(feature_id)
            self.feature_count += 1
            self.updated_at = get_current_time()

    def remove_feature(self, feature_id: str) -> None:
        """
        Remove a feature from the collection.

        Args:
            feature_id: ID of feature to remove
        """
        if feature_id in self.feature_ids:
            self.feature_ids.remove(feature_id)
            self.feature_count -= 1
            self.updated_at = get_current_time()

    async def get_features(self) -> list[StoredFeature]:
        """
        Retrieve all StoredFeature objects in this collection.

        Returns:
            List of StoredFeature documents
        """
        features = []
        for feature_id in self.feature_ids:
            feature = await StoredFeature.find_one(StoredFeature.feature_id == feature_id)
            if feature:
                features.append(feature)
        return features
