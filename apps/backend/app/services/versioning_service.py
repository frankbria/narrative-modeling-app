"""
Data versioning service.

Handles creation, retrieval, and management of dataset versions and transformation lineage,
enabling reproducibility and historical analysis.

Security:
- Version retrieval methods enforce ownership checks when user_id is provided
- Ownership checks can be bypassed for internal operations by omitting user_id parameter
- All bypassed operations are logged for security auditing
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from botocore.exceptions import ClientError
from pymongo.errors import DuplicateKeyError

from app.config import settings
from app.models.dataset import DatasetMetadata
from app.models.version import (
    DatasetVersion,
    TransformationLineage,
    TransformationStep,
    VersionComparison,
)
from app.services.base_service import BaseService
from app.services.exceptions import (
    ConflictError,
    NotFoundError,
    OperationError,
    ValidationError,
)
from app.utils.s3 import create_s3_client

logger = logging.getLogger(__name__)

# Max optimistic-retry attempts when a concurrent writer grabs the same
# version_number (issue #276). Contention is bounded by concurrent transforms
# on one dataset, so a small ceiling is plenty.
_MAX_VERSION_INSERT_RETRIES = 5


class VersioningService(BaseService[DatasetVersion]):
    """Service for managing dataset versions and lineage tracking."""

    model_class = DatasetVersion
    resource_name = "DatasetVersion"

    def __init__(self):
        """Initialize versioning service with S3 client."""
        self.s3_client = create_s3_client()
        self.bucket_name = settings.S3_BUCKET

    def _get_id_field(self) -> str:
        """Return the unique identifier field name for DatasetVersion."""
        return "version_id"

    async def create_base_version(
        self,
        dataset_metadata: DatasetMetadata,
        file_content: bytes,
        user_id: str,
        description: str | None = None
    ) -> DatasetVersion:
        """
        Create initial version for a newly uploaded dataset.

        Args:
            dataset_metadata: Dataset metadata document
            file_content: Raw file content bytes
            user_id: User creating the version
            description: Optional version description

        Returns:
            Created DatasetVersion document

        Raises:
            ConflictError: If dataset already has a base version
        """
        logger.info(f"Creating base version for dataset {dataset_metadata.dataset_id}")

        # Check if base version already exists
        existing_base = await DatasetVersion.find_one(
            DatasetVersion.dataset_id == dataset_metadata.dataset_id,
            DatasetVersion.is_base_version == True,  # noqa: E712 — Beanie query expression
        )
        if existing_base:
            raise ConflictError(
                message=f"Base version already exists for dataset {dataset_metadata.dataset_id}",
                existing_id=existing_base.version_id
            )

        # Compute content and schema hashes
        content_hash = DatasetVersion.compute_content_hash(file_content)

        # Extract dtypes from schema
        dtypes = {}
        for field in dataset_metadata.data_schema:
            dtypes[field.field_name] = field.inferred_dtype

        schema_hash = DatasetVersion.compute_schema_hash(
            dataset_metadata.columns,
            dtypes
        )

        # Create version document
        version_id = str(uuid.uuid4())
        version = DatasetVersion(
            version_id=version_id,
            dataset_id=dataset_metadata.dataset_id,
            version_number=1,
            user_id=user_id,
            content_hash=content_hash,
            file_size=len(file_content),
            file_path=dataset_metadata.file_path,
            s3_url=dataset_metadata.s3_url,
            description=description or "Initial upload",
            num_rows=dataset_metadata.num_rows,
            num_columns=dataset_metadata.num_columns,
            columns=dataset_metadata.columns,
            schema_hash=schema_hash,
            is_base_version=True,
            created_by=user_id
        )

        await version.insert()
        logger.info(f"Created base version {version_id} for dataset {dataset_metadata.dataset_id}")
        return version

    async def create_transformation_version(
        self,
        parent_version_id: str,
        transformed_content: bytes,
        transformation_steps: list[dict[str, Any]],
        dataset_metadata: DatasetMetadata,
        user_id: str,
        description: str | None = None,
        transformation_config_id: str | None = None,
        quality_before: dict[str, Any] | None = None,
        quality_after: dict[str, Any] | None = None
    ) -> tuple[DatasetVersion, TransformationLineage]:
        """
        Create new version after transformation application.

        Args:
            parent_version_id: ID of parent version
            transformed_content: Transformed file content bytes
            transformation_steps: List of transformation step dictionaries
            dataset_metadata: Updated dataset metadata
            user_id: User performing transformation
            description: Optional version description
            transformation_config_id: Optional reference to full config
            quality_before: Optional quality report (dict) of the parent data
            quality_after: Optional quality report (dict) of the transformed data

        Returns:
            Tuple of (new_version, lineage)

        Raises:
            NotFoundError: If parent version not found
            OperationError: If S3 upload fails
        """
        logger.info(f"Creating transformation version from parent {parent_version_id}")

        # Retrieve parent version
        parent_version = await DatasetVersion.find_one(
            DatasetVersion.version_id == parent_version_id
        )
        if not parent_version:
            raise NotFoundError(
                resource_type="DatasetVersion",
                resource_id=parent_version_id
            )

        # Check for duplicate content (deduplication)
        content_hash = DatasetVersion.compute_content_hash(transformed_content)
        existing_version = await DatasetVersion.find_one(
            DatasetVersion.dataset_id == parent_version.dataset_id,
            DatasetVersion.content_hash == content_hash
        )

        if existing_version:
            logger.info(f"Duplicate content detected, updating existing version {existing_version.version_id} with new metadata")

            # Update description if provided
            if description:
                existing_version.description = description
                await existing_version.save()

            # Still create lineage to track this transformation
            lineage = await self._create_lineage(
                parent_version=parent_version,
                child_version=existing_version,
                transformation_steps=transformation_steps,
                dataset_metadata=dataset_metadata,
                user_id=user_id,
                transformation_config_id=transformation_config_id,
                quality_before=quality_before,
                quality_after=quality_after
            )
            return existing_version, lineage

        # Upload transformed file to S3 under a collision-proof key (issue #276).
        # The key embeds version_id (a UUID), NOT the racy version number, so two
        # concurrent transforms can never put_object to the same key and silently
        # overwrite each other's content.
        version_id = str(uuid.uuid4())
        versioned_file_path = f"datasets/{user_id}/{parent_version.dataset_id}/versions/{version_id}/{dataset_metadata.filename}"

        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=versioned_file_path,
                Body=transformed_content
            )
            s3_url = f"s3://{self.bucket_name}/{versioned_file_path}"
            logger.info(f"Uploaded version to {s3_url}")
        except ClientError as e:
            logger.error(f"Failed to upload version to S3: {e}")
            raise OperationError(
                message="Failed to upload version to S3",
                operation="s3_upload",
                original_error=e
            )

        # Compute schema hash
        dtypes = {}
        for field in dataset_metadata.data_schema:
            dtypes[field.field_name] = field.inferred_dtype
        schema_hash = DatasetVersion.compute_schema_hash(
            dataset_metadata.columns,
            dtypes
        )

        # Insert with optimistic retry on the unique (dataset_id, version_number)
        # index (issue #276): recompute the next number each attempt so a concurrent
        # writer that grabbed the same number loses one race, not the data. The S3
        # object is already keyed by version_id, so a retry never re-uploads.
        next_version_number = 0
        for attempt in range(_MAX_VERSION_INSERT_RETRIES):
            next_version_number = await self._get_next_version_number(parent_version.dataset_id)
            new_version = DatasetVersion(
                version_id=version_id,
                dataset_id=parent_version.dataset_id,
                version_number=next_version_number,
                user_id=user_id,
                content_hash=content_hash,
                file_size=len(transformed_content),
                file_path=versioned_file_path,
                s3_url=s3_url,
                description=description or f"Transformation from v{parent_version.version_number}",
                num_rows=dataset_metadata.num_rows,
                num_columns=dataset_metadata.num_columns,
                columns=dataset_metadata.columns,
                schema_hash=schema_hash,
                parent_version_id=parent_version_id,
                is_base_version=False,
                created_by=user_id
            )
            try:
                await new_version.insert()
                break
            except DuplicateKeyError:
                if attempt == _MAX_VERSION_INSERT_RETRIES - 1:
                    logger.error(
                        f"Version number contention for dataset {parent_version.dataset_id} "
                        f"exhausted {_MAX_VERSION_INSERT_RETRIES} retries"
                    )
                    raise OperationError(
                        message="Failed to assign a unique version number after retries",
                        operation="version_insert",
                    )
                logger.warning(
                    f"Version number {next_version_number} collided for dataset "
                    f"{parent_version.dataset_id}; retrying (attempt {attempt + 1})"
                )
        logger.info(f"Created transformation version {version_id} (v{next_version_number})")

        # Create lineage tracking
        lineage = await self._create_lineage(
            parent_version=parent_version,
            child_version=new_version,
            transformation_steps=transformation_steps,
            dataset_metadata=dataset_metadata,
            user_id=user_id,
            transformation_config_id=transformation_config_id,
            quality_before=quality_before,
            quality_after=quality_after
        )

        # Link lineage to version
        new_version.transformation_lineage_id = lineage.lineage_id
        await new_version.save()

        return new_version, lineage

    async def _create_lineage(
        self,
        parent_version: DatasetVersion,
        child_version: DatasetVersion,
        transformation_steps: list[dict[str, Any]],
        dataset_metadata: DatasetMetadata,
        user_id: str,
        transformation_config_id: str | None = None,
        quality_before: dict[str, Any] | None = None,
        quality_after: dict[str, Any] | None = None
    ) -> TransformationLineage:
        """Create transformation lineage record."""
        lineage_id = str(uuid.uuid4())

        # Convert transformation step dicts to TransformationStep models
        steps = [TransformationStep(**step) for step in transformation_steps]

        # Calculate total execution time
        total_time = sum(step.execution_time or 0 for step in steps)

        # Quality trend (issue #102, AC3): improvement is the 0-100 score delta.
        quality_improvement: float | None = None
        if quality_before and quality_after:
            before_score = quality_before.get("score_0_100")
            after_score = quality_after.get("score_0_100")
            if before_score is not None and after_score is not None:
                quality_improvement = round(float(after_score) - float(before_score), 1)

        lineage = TransformationLineage(
            lineage_id=lineage_id,
            parent_version_id=parent_version.version_id,
            child_version_id=child_version.version_id,
            dataset_id=parent_version.dataset_id,
            user_id=user_id,
            transformation_steps=steps,
            transformation_config_id=transformation_config_id,
            total_execution_time=total_time if total_time > 0 else None,
            rows_before=parent_version.num_rows,
            rows_after=child_version.num_rows,
            columns_before=parent_version.num_columns,
            columns_after=child_version.num_columns,
            quality_before=quality_before,
            quality_after=quality_after,
            quality_improvement=quality_improvement
        )

        lineage.mark_completed()
        await lineage.insert()
        logger.info(f"Created lineage {lineage_id} from {parent_version.version_id} to {child_version.version_id}")

        return lineage

    async def _get_next_version_number(self, dataset_id: str) -> int:
        """Get next version number for dataset."""
        latest_version = await DatasetVersion.find(
            DatasetVersion.dataset_id == dataset_id
        ).sort("-version_number").first_or_none()

        if latest_version:
            return latest_version.version_number + 1
        return 1

    async def get_version(
        self,
        version_id: str,
        mark_accessed: bool = True,
        user_id: str | None = None
    ) -> DatasetVersion | None:
        """
        Retrieve a specific dataset version.

        Security: Ownership check enforced when user_id is provided.

        Args:
            version_id: Version identifier
            mark_accessed: Whether to increment access counter
            user_id: Optional user ID for ownership verification.
                    If provided, only returns version if dataset is owned by this user.
                    If None, bypasses ownership check (for internal operations).

        Returns:
            DatasetVersion or None if not found or ownership check fails
        """
        version = await DatasetVersion.find_one({"version_id": version_id})

        if not version:
            return None

        # Enforce ownership check if user_id is provided
        if user_id is not None:
            # Get the dataset to check ownership
            from app.models.dataset import DatasetMetadata
            dataset = await DatasetMetadata.find_one({"dataset_id": version.dataset_id})
            if dataset and dataset.user_id != user_id:
                logger.warning(
                    f"Ownership check failed: User {user_id} attempted to access "
                    f"version {version_id} of dataset {version.dataset_id} owned by {dataset.user_id}"
                )
                return None
        else:
            # Log bypassed ownership check for security audit
            logger.info(
                f"Ownership check bypassed for version {version_id} "
                f"(dataset {version.dataset_id}). This is expected for internal operations."
            )

        if mark_accessed:
            version.mark_accessed()
            await version.save()

        return version

    async def get_version_content(self, version_id: str) -> bytes:
        """
        Retrieve file content for a specific version.

        Args:
            version_id: Version identifier

        Returns:
            File content bytes

        Raises:
            NotFoundError: If version not found
            OperationError: If S3 retrieval fails
        """
        version = await self.get_version(version_id, mark_accessed=True)
        if not version:
            raise NotFoundError(
                resource_type="DatasetVersion",
                resource_id=version_id
            )

        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=version.file_path
            )
            content = response['Body'].read()
            logger.info(f"Retrieved content for version {version_id} ({len(content)} bytes)")
            return content
        except ClientError as e:
            logger.error(f"Failed to retrieve version content from S3: {e}")
            raise OperationError(
                message="Failed to retrieve version content from S3",
                operation="s3_download",
                original_error=e
            )

    async def list_versions(
        self,
        dataset_id: str,
        user_id: str | None = None,
        limit: int = 50,
        skip: int = 0
    ) -> list[DatasetVersion]:
        """
        List versions for a dataset.

        Args:
            dataset_id: Dataset identifier
            user_id: Optional user filter
            limit: Maximum versions to return
            skip: Number of versions to skip

        Returns:
            List of DatasetVersion documents
        """
        # Build filter conditionally
        filter_dict = {"dataset_id": dataset_id}
        if user_id:
            filter_dict["user_id"] = user_id

        # Single find() call with combined filter
        query = DatasetVersion.find(filter_dict)
        versions = await query.sort("-version_number").skip(skip).limit(limit).to_list()
        logger.info(f"Listed {len(versions)} versions for dataset {dataset_id}")
        return versions

    async def get_quality_trend(self, dataset_id: str) -> list[dict[str, Any]]:
        """Quality score trend across a dataset's versions (issue #102, AC3).

        Reads transformation lineage records (oldest first) and projects each one's
        before/after 0-100 quality scores. Never raises — returns [] when there is
        no lineage / no quality data.
        """
        lineages = await TransformationLineage.find(
            TransformationLineage.dataset_id == dataset_id
        ).sort("+created_at").to_list()

        versions = await DatasetVersion.find(
            DatasetVersion.dataset_id == dataset_id
        ).to_list()
        version_number = {v.version_id: v.version_number for v in versions}

        points: list[dict[str, Any]] = []
        for lineage in lineages:
            before = (lineage.quality_before or {}).get("score_0_100")
            after = (lineage.quality_after or {}).get("score_0_100")
            transforms = ", ".join(
                step.step_type for step in lineage.transformation_steps
            ) or "transformation"
            points.append({
                "version_number": version_number.get(lineage.child_version_id),
                "created_at": lineage.created_at,
                "score_before": before,
                "score_after": after,
                "improvement": lineage.quality_improvement,
                "transformation": transforms,
            })
        return points

    async def get_lineage_chain(self, version_id: str) -> list[TransformationLineage]:
        """
        Get complete lineage chain from base version to specified version.

        Args:
            version_id: Target version ID

        Returns:
            List of TransformationLineage documents in chronological order
        """
        chain: list[TransformationLineage] = []
        current_version_id: str | None = version_id

        while current_version_id:
            version = await self.get_version(current_version_id, mark_accessed=False)
            if not version:
                break

            if version.transformation_lineage_id:
                lineage = await TransformationLineage.find_one(
                    TransformationLineage.lineage_id == version.transformation_lineage_id
                )
                if lineage:
                    chain.insert(0, lineage)  # Insert at beginning for chronological order

            current_version_id = version.parent_version_id

        logger.info(f"Retrieved lineage chain of {len(chain)} transformations for version {version_id}")
        return chain

    async def compare_versions(
        self,
        version1_id: str,
        version2_id: str
    ) -> VersionComparison:
        """
        Compare two dataset versions.

        Args:
            version1_id: First version ID
            version2_id: Second version ID

        Returns:
            VersionComparison with detailed differences

        Raises:
            NotFoundError: If versions not found
            ValidationError: If versions are not from same dataset
        """
        version1 = await self.get_version(version1_id, mark_accessed=False)
        version2 = await self.get_version(version2_id, mark_accessed=False)

        if not version1 or not version2:
            missing_ids = []
            if not version1:
                missing_ids.append(version1_id)
            if not version2:
                missing_ids.append(version2_id)
            raise NotFoundError(
                message=f"Version(s) not found: {', '.join(missing_ids)}",
                resource_type="DatasetVersion",
                resource_id=missing_ids[0]
            )

        if version1.dataset_id != version2.dataset_id:
            raise ValidationError(
                message="Versions must be from the same dataset",
                details={
                    "version1_dataset_id": version1.dataset_id,
                    "version2_dataset_id": version2.dataset_id
                }
            )

        # Calculate dimensional changes
        rows_diff = version2.num_rows - version1.num_rows
        columns_diff = version2.num_columns - version1.num_columns

        # Schema changes
        cols1 = set(version1.columns)
        cols2 = set(version2.columns)
        columns_added = list(cols2 - cols1)
        columns_removed = list(cols1 - cols2)

        # Check schema identity
        schema_identical = (
            version1.schema_hash == version2.schema_hash and
            version1.columns == version2.columns
        )

        # Find lineage path
        lineage_path = await self._find_lineage_path(version1_id, version2_id)

        # Content similarity based on hash
        content_similarity = 100.0 if version1.content_hash == version2.content_hash else 0.0

        comparison = VersionComparison(
            version1_id=version1_id,
            version2_id=version2_id,
            rows_diff=rows_diff,
            columns_diff=columns_diff,
            columns_added=columns_added,
            columns_removed=columns_removed,
            schema_identical=schema_identical,
            content_similarity=content_similarity,
            lineage_path=[lineage.lineage_id for lineage in lineage_path],
            transformation_count=len(lineage_path)
        )

        logger.info(f"Compared versions {version1_id} and {version2_id}: {len(lineage_path)} transformations")
        return comparison

    async def _find_lineage_path(
        self,
        version1_id: str,
        version2_id: str
    ) -> list[TransformationLineage]:
        """Find transformation lineage path between two versions."""
        # Get lineage chains for both versions
        chain1 = await self.get_lineage_chain(version1_id)
        chain2 = await self.get_lineage_chain(version2_id)

        # Find common ancestor and path
        if not chain1 and not chain2:
            return []

        # If one is ancestor of the other
        if len(chain1) < len(chain2):
            # version1 might be ancestor of version2
            path = chain2[len(chain1):]
            return path
        elif len(chain2) < len(chain1):
            # version2 might be ancestor of version1
            path = chain1[len(chain2):]
            return list(reversed(path))

        return []

    async def pin_version(
        self,
        version_id: str,
        user_id: str | None = None
    ) -> DatasetVersion:
        """
        Pin a version to prevent auto-deletion.

        Security: Ownership check enforced when user_id is provided.

        Args:
            version_id: Version to pin
            user_id: Optional user ID for ownership verification

        Returns:
            Updated DatasetVersion

        Raises:
            NotFoundError: If version not found
            PermissionDeniedError: If ownership check fails (via get_version)
        """
        version = await self.get_version(version_id, mark_accessed=False, user_id=user_id)
        if not version:
            raise NotFoundError(
                resource_type="DatasetVersion",
                resource_id=version_id
            )

        version.pin_version()
        await version.save()
        logger.info(f"Pinned version {version_id}")
        return version

    async def unpin_version(
        self,
        version_id: str,
        user_id: str | None = None
    ) -> DatasetVersion:
        """
        Unpin a version, allowing auto-deletion.

        Security: Ownership check enforced when user_id is provided.

        Args:
            version_id: Version to unpin
            user_id: Optional user ID for ownership verification

        Returns:
            Updated DatasetVersion

        Raises:
            NotFoundError: If version not found
            PermissionDeniedError: If ownership check fails (via get_version)
        """
        version = await self.get_version(version_id, mark_accessed=False, user_id=user_id)
        if not version:
            raise NotFoundError(
                resource_type="DatasetVersion",
                resource_id=version_id
            )

        version.unpin_version()
        await version.save()
        logger.info(f"Unpinned version {version_id}")
        return version

    async def cleanup_old_versions(
        self,
        dataset_id: str,
        retention_days: int = 30,
        keep_count: int = 10
    ) -> int:
        """
        Clean up old versions based on retention policy.

        Args:
            dataset_id: Dataset to clean
            retention_days: Days to retain unpinned versions
            keep_count: Minimum number of recent versions to keep

        Returns:
            Number of versions deleted
        """
        cutoff_date = datetime.now(UTC) - timedelta(days=retention_days)

        # Get all versions for dataset
        all_versions = await DatasetVersion.find(
            DatasetVersion.dataset_id == dataset_id
        ).sort("-version_number").to_list()

        # Determine versions to delete
        deleted_count = 0
        for i, version in enumerate(all_versions):
            # Keep pinned, base, recently used, or recent versions
            if (
                version.is_pinned or
                version.is_base_version or
                i < keep_count or
                version.created_at > cutoff_date or
                len(version.used_in_training) > 0
            ):
                continue

            # Delete from S3
            try:
                self.s3_client.delete_object(
                    Bucket=self.bucket_name,
                    Key=version.file_path
                )
            except ClientError as e:
                logger.warning(f"Failed to delete S3 object for version {version.version_id}: {e}")

            # Delete from database
            await version.delete()
            deleted_count += 1
            logger.info(f"Deleted old version {version.version_id}")

        logger.info(f"Cleaned up {deleted_count} old versions for dataset {dataset_id}")
        return deleted_count


# Global service instance
versioning_service = VersioningService()