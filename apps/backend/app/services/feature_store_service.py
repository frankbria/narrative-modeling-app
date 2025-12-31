"""
Feature Store Service.

Provides business logic for managing reusable feature definitions,
including CRUD operations, feature application, versioning, and sharing.
"""

import uuid
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from app.models.feature_store import StoredFeature, FeatureVersion, FeatureCollection
from app.models.dataset import DatasetMetadata
from app.services.base_service import BaseService
from app.services.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.services.model_training.feature_engineer import FeatureEngineer
from app.services.s3_service import get_file_from_s3
import pandas as pd
import io

logger = logging.getLogger(__name__)


class FeatureStoreService(BaseService[StoredFeature]):
    """
    Service for managing feature store operations.

    Handles feature CRUD, versioning, application, sharing, and collections.
    """

    model_class = StoredFeature
    resource_name = "Feature"

    def _get_id_field(self) -> str:
        """Return the unique identifier field name."""
        return "feature_id"

    async def save_feature(
        self,
        feature_data: Dict[str, Any],
        user_id: str
    ) -> StoredFeature:
        """
        Save a new feature to the feature store.

        Args:
            feature_data: Feature definition and metadata
            user_id: ID of user creating the feature

        Returns:
            Created StoredFeature instance
        """
        # Generate unique feature ID
        feature_id = f"feat_{uuid.uuid4().hex[:12]}"

        # Create feature
        feature = StoredFeature(
            feature_id=feature_id,
            user_id=user_id,
            name=feature_data["name"],
            description=feature_data["description"],
            category=feature_data["category"],
            tags=feature_data.get("tags", []),
            definition_type=feature_data["definition_type"],
            definition_code=feature_data["definition_code"],
            input_requirements=feature_data["input_requirements"],
            output_type=feature_data["output_type"],
            output_column_name=feature_data["output_column_name"],
            version=1,
            is_public=feature_data.get("is_public", False),
            shared_with=feature_data.get("shared_with", []),
            usage_count=0,
            created_by=user_id
        )

        await feature.save()

        # Create initial version
        version = FeatureVersion(
            version_id=f"ver_{uuid.uuid4().hex[:12]}",
            feature_id=feature_id,
            version_number=1,
            definition_code=feature_data["definition_code"],
            definition_type=feature_data["definition_type"],
            input_requirements=feature_data["input_requirements"],
            output_type=feature_data["output_type"],
            changes_description="Initial version",
            changed_fields=[],
            created_by=user_id
        )

        await version.save()

        logger.info(f"Created feature {feature_id} for user {user_id}")
        return feature

    async def get_feature(
        self,
        feature_id: str,
        user_id: str,
        version: Optional[int] = None
    ) -> StoredFeature:
        """
        Get feature by ID with permission check.

        Args:
            feature_id: Feature identifier
            user_id: Requesting user ID
            version: Optional version number to retrieve

        Returns:
            StoredFeature instance

        Raises:
            NotFoundError: If feature doesn't exist
            PermissionDeniedError: If user doesn't have access
        """
        feature = await self.get_by_id_or_raise(feature_id)

        # Check permissions
        if not self._has_access(feature, user_id):
            raise PermissionDeniedError(
                message=f"You don't have permission to access feature {feature_id}",
                user_id=user_id,
                resource_id=feature_id
            )

        # If specific version requested, reconstruct from version history
        if version is not None:
            version_doc = await FeatureVersion.find_one(
                FeatureVersion.feature_id == feature_id,
                FeatureVersion.version_number == version
            )
            if not version_doc:
                raise NotFoundError(
                    message=f"Version {version} not found for feature {feature_id}",
                    resource_type="FeatureVersion",
                    resource_id=f"{feature_id}_v{version}"
                )

        return feature

    def _has_access(self, feature: StoredFeature, user_id: str) -> bool:
        """Check if user has access to feature."""
        return (
            feature.user_id == user_id or
            feature.is_public or
            user_id in feature.shared_with
        )

    async def search_features(
        self,
        user_id: str,
        query: Optional[str] = None,
        filters: Dict[str, Any] = {},
        skip: int = 0,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        Search features with text query and filters.

        Args:
            user_id: Requesting user ID
            query: Optional text search query
            filters: Optional filters (category, tags, domain)
            skip: Number of results to skip
            limit: Maximum results to return

        Returns:
            Dictionary with items, total, skip, limit
        """
        # Build query conditions
        conditions = []

        # User can see: owned features, public features, or shared features
        access_condition = {
            "$or": [
                {"user_id": user_id},
                {"is_public": True},
                {"shared_with": user_id}
            ]
        }
        conditions.append(access_condition)

        # Text search
        if query:
            conditions.append({"$text": {"$search": query}})

        # Category filter
        if "category" in filters:
            conditions.append({"category": filters["category"]})

        # Tags filter
        if "tags" in filters:
            if isinstance(filters["tags"], list):
                conditions.append({"tags": {"$in": filters["tags"]}})
            else:
                conditions.append({"tags": filters["tags"]})

        # Domain filter (if applicable)
        if "domain" in filters:
            conditions.append({"domain": filters["domain"]})

        # Build final query
        if len(conditions) > 1:
            final_query = {"$and": conditions}
        else:
            final_query = conditions[0] if conditions else {}

        # Execute query
        query_builder = StoredFeature.find(final_query)
        total = await query_builder.count()
        features = await query_builder.skip(skip).limit(limit).to_list()

        return {
            "items": features,
            "total": total,
            "skip": skip,
            "limit": limit
        }

    async def update_feature(
        self,
        feature_id: str,
        user_id: str,
        updates: Dict[str, Any]
    ) -> StoredFeature:
        """
        Update feature and create new version if definition changed.

        Args:
            feature_id: Feature identifier
            user_id: User making the update
            updates: Fields to update

        Returns:
            Updated StoredFeature instance
        """
        feature = await self.get_by_id_or_raise(feature_id)
        await self._check_ownership(feature, user_id)

        # Check if definition changed (requires new version)
        definition_changed = any(
            key in updates for key in ["definition_code", "definition_type", "input_requirements"]
        )

        if definition_changed:
            # Create new version
            feature.version += 1

            changed_fields = [
                key for key in ["definition_code", "definition_type", "input_requirements", "output_type"]
                if key in updates
            ]

            version = FeatureVersion(
                version_id=f"ver_{uuid.uuid4().hex[:12]}",
                feature_id=feature_id,
                version_number=feature.version,
                definition_code=updates.get("definition_code", feature.definition_code),
                definition_type=updates.get("definition_type", feature.definition_type),
                input_requirements=updates.get("input_requirements", feature.input_requirements),
                output_type=updates.get("output_type", feature.output_type),
                changes_description=updates.get("changes_description", f"Updated {', '.join(changed_fields)}"),
                changed_fields=changed_fields,
                created_by=user_id
            )

            await version.save()

        # Update feature fields
        for key, value in updates.items():
            if hasattr(feature, key) and key not in ['feature_id', 'user_id', 'created_by', 'created_at']:
                setattr(feature, key, value)

        feature.update_timestamp()
        await feature.save()

        logger.info(f"Updated feature {feature_id} to version {feature.version}")
        return feature

    async def delete_feature(
        self,
        feature_id: str,
        user_id: str,
        soft_delete: bool = True
    ) -> bool:
        """
        Delete a feature.

        Args:
            feature_id: Feature identifier
            user_id: User requesting deletion
            soft_delete: If True, mark as deleted instead of removing

        Returns:
            True if successful
        """
        return await self.delete(feature_id, user_id, soft_delete=soft_delete)

    async def check_compatibility(
        self,
        feature_id: str,
        dataset_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Check if feature is compatible with dataset schema.

        Args:
            feature_id: Feature identifier
            dataset_id: Dataset identifier
            user_id: User requesting check

        Returns:
            Compatibility report dictionary
        """
        feature = await self.get_feature(feature_id, user_id)

        # Get dataset schema
        dataset = await DatasetMetadata.find_one(
            DatasetMetadata.dataset_id == dataset_id,
            DatasetMetadata.user_id == user_id
        )

        if not dataset:
            raise NotFoundError(
                message=f"Dataset {dataset_id} not found",
                resource_type="Dataset",
                resource_id=dataset_id
            )

        # Check compatibility
        is_compatible, missing_columns, type_mismatches = feature.check_compatibility(
            dataset.data_schema
        )

        # Generate suggestions
        suggestions = []
        if missing_columns:
            suggestions.append(f"Add missing columns: {', '.join(missing_columns)}")
        if type_mismatches:
            for col, types in type_mismatches.items():
                suggestions.append(
                    f"Convert {col} from {types['actual']} to {types['expected']}"
                )

        return {
            "is_compatible": is_compatible,
            "missing_columns": missing_columns,
            "type_mismatches": type_mismatches,
            "suggestions": suggestions
        }

    async def apply_feature(
        self,
        feature_id: str,
        dataset_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Apply feature to a dataset.

        Args:
            feature_id: Feature identifier
            dataset_id: Dataset identifier
            user_id: User applying feature

        Returns:
            Result dictionary with new column data
        """
        feature = await self.get_feature(feature_id, user_id)

        # Check compatibility first
        compat = await self.check_compatibility(feature_id, dataset_id, user_id)
        if not compat["is_compatible"]:
            raise ValidationError(
                message="Feature is not compatible with dataset",
                details=compat
            )

        # Load dataset
        dataset = await DatasetMetadata.find_one(
            DatasetMetadata.dataset_id == dataset_id,
            DatasetMetadata.user_id == user_id
        )

        # Load data from S3
        file_bytes = await get_file_from_s3(dataset.file_path)
        if dataset.file_type == "csv":
            file_str = file_bytes.decode('utf-8')
            df = pd.read_csv(io.StringIO(file_str))
        elif dataset.file_type in ["xls", "xlsx"]:
            file_io = io.BytesIO(file_bytes)
            df = pd.read_excel(file_io)
        else:
            raise ValidationError(
                message=f"Unsupported file type: {dataset.file_type}",
                details={"file_type": dataset.file_type}
            )

        # Apply feature using FeatureEngineer
        engineer = FeatureEngineer()
        result_df = await engineer.apply_stored_feature(df, feature)

        # Increment usage count
        feature.increment_usage()

        # Track application
        if dataset_id not in feature.applied_to_datasets:
            feature.applied_to_datasets.append(dataset_id)

        await feature.save()

        logger.info(f"Applied feature {feature_id} to dataset {dataset_id}")

        return {
            "success": True,
            "feature_id": feature_id,
            "dataset_id": dataset_id,
            "output_column": feature.output_column_name,
            "message": f"Feature applied successfully. Created column: {feature.output_column_name}"
        }

    async def share_feature(
        self,
        feature_id: str,
        user_id: str,
        share_with_user_ids: List[str]
    ) -> StoredFeature:
        """
        Share feature with other users.

        Args:
            feature_id: Feature identifier
            user_id: Owner user ID
            share_with_user_ids: List of user IDs to share with

        Returns:
            Updated StoredFeature instance
        """
        feature = await self.get_by_id_or_raise(feature_id)
        await self._check_ownership(feature, user_id)

        # Add users to shared_with list
        for share_user_id in share_with_user_ids:
            if share_user_id not in feature.shared_with:
                feature.shared_with.append(share_user_id)

        feature.update_timestamp()
        await feature.save()

        logger.info(f"Shared feature {feature_id} with {len(share_with_user_ids)} users")
        return feature

    async def make_public(
        self,
        feature_id: str,
        user_id: str
    ) -> StoredFeature:
        """
        Make feature publicly accessible.

        Args:
            feature_id: Feature identifier
            user_id: Owner user ID

        Returns:
            Updated StoredFeature instance
        """
        feature = await self.get_by_id_or_raise(feature_id)
        await self._check_ownership(feature, user_id)

        feature.is_public = True
        feature.update_timestamp()
        await feature.save()

        logger.info(f"Made feature {feature_id} public")
        return feature

    async def get_version_history(
        self,
        feature_id: str,
        user_id: str
    ) -> List[FeatureVersion]:
        """
        Get version history for a feature.

        Args:
            feature_id: Feature identifier
            user_id: Requesting user ID

        Returns:
            List of FeatureVersion instances
        """
        # Verify user has access to feature
        await self.get_feature(feature_id, user_id)

        # Get all versions, newest first
        versions = await FeatureVersion.find(
            FeatureVersion.feature_id == feature_id
        ).sort(-FeatureVersion.version_number).to_list()

        return versions

    async def export_feature(
        self,
        feature_id: str,
        user_id: str,
        format: str = "json"
    ) -> Dict[str, Any]:
        """
        Export feature definition.

        Args:
            feature_id: Feature identifier
            user_id: Requesting user ID
            format: Export format (json, yaml)

        Returns:
            Exportable feature representation
        """
        feature = await self.get_feature(feature_id, user_id)
        versions = await self.get_version_history(feature_id, user_id)

        export_data = {
            "feature": feature.to_dict(),
            "versions": [
                {
                    "version_number": v.version_number,
                    "definition_code": v.definition_code,
                    "changes_description": v.changes_description,
                    "created_at": v.created_at.isoformat()
                }
                for v in versions
            ],
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "format_version": "1.0"
        }

        return export_data

    async def import_feature(
        self,
        feature_data: Dict[str, Any],
        user_id: str
    ) -> StoredFeature:
        """
        Import feature from exported data.

        Args:
            feature_data: Exported feature data
            user_id: User importing feature

        Returns:
            Created StoredFeature instance
        """
        # Extract feature definition from import data
        feature_def = feature_data.get("feature", feature_data)

        # Create new feature (don't preserve IDs)
        new_feature = await self.save_feature(feature_def, user_id)

        logger.info(f"Imported feature {new_feature.feature_id} for user {user_id}")
        return new_feature

    async def create_collection(
        self,
        collection_data: Dict[str, Any],
        user_id: str
    ) -> FeatureCollection:
        """
        Create a new feature collection.

        Args:
            collection_data: Collection metadata
            user_id: User creating collection

        Returns:
            Created FeatureCollection instance
        """
        collection_id = f"coll_{uuid.uuid4().hex[:12]}"

        collection = FeatureCollection(
            collection_id=collection_id,
            user_id=user_id,
            name=collection_data["name"],
            description=collection_data["description"],
            domain=collection_data["domain"],
            feature_ids=collection_data.get("feature_ids", []),
            feature_count=len(collection_data.get("feature_ids", [])),
            is_public=collection_data.get("is_public", False),
            shared_with=collection_data.get("shared_with", []),
            tags=collection_data.get("tags", []),
            created_by=user_id
        )

        await collection.save()

        logger.info(f"Created collection {collection_id} for user {user_id}")
        return collection

    async def add_to_collection(
        self,
        collection_id: str,
        feature_id: str,
        user_id: str
    ) -> FeatureCollection:
        """
        Add feature to collection.

        Args:
            collection_id: Collection identifier
            feature_id: Feature to add
            user_id: User making change

        Returns:
            Updated FeatureCollection instance
        """
        # Verify collection exists and user owns it
        collection = await FeatureCollection.find_one(
            FeatureCollection.collection_id == collection_id,
            FeatureCollection.user_id == user_id
        )

        if not collection:
            raise NotFoundError(
                message=f"Collection {collection_id} not found or access denied",
                resource_type="FeatureCollection",
                resource_id=collection_id
            )

        # Verify feature exists and user has access
        await self.get_feature(feature_id, user_id)

        # Add feature to collection
        collection.add_feature(feature_id)
        await collection.save()

        logger.info(f"Added feature {feature_id} to collection {collection_id}")
        return collection

    async def get_collection(
        self,
        collection_id: str,
        user_id: str
    ) -> FeatureCollection:
        """
        Get collection by ID with permission check.

        Args:
            collection_id: Collection identifier
            user_id: Requesting user ID

        Returns:
            FeatureCollection instance
        """
        collection = await FeatureCollection.find_one(
            FeatureCollection.collection_id == collection_id
        )

        if not collection:
            raise NotFoundError(
                message=f"Collection {collection_id} not found",
                resource_type="FeatureCollection",
                resource_id=collection_id
            )

        # Check permissions
        if not (collection.user_id == user_id or collection.is_public or user_id in collection.shared_with):
            raise PermissionDeniedError(
                message=f"You don't have permission to access collection {collection_id}",
                user_id=user_id,
                resource_id=collection_id
            )

        return collection

    async def list_collections(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        List collections for user.

        Args:
            user_id: Requesting user ID
            skip: Number of results to skip
            limit: Maximum results to return

        Returns:
            Dictionary with items, total, skip, limit
        """
        # User can see: owned collections, public collections, or shared collections
        query = {
            "$or": [
                {"user_id": user_id},
                {"is_public": True},
                {"shared_with": user_id}
            ]
        }

        query_builder = FeatureCollection.find(query)
        total = await query_builder.count()
        collections = await query_builder.skip(skip).limit(limit).to_list()

        return {
            "items": collections,
            "total": total,
            "skip": skip,
            "limit": limit
        }
