"""
Dataset service for DatasetMetadata operations.

This service handles CRUD operations for datasets using the new DatasetMetadata model,
while maintaining backward compatibility with the legacy UserData model through dual-write.
"""

from typing import Any

from app.models.dataset import AISummary, DatasetMetadata, PIIReport, SchemaField
from app.models.user_data import AISummary as LegacyAISummary
from app.models.user_data import SchemaField as LegacySchemaField
from app.models.user_data import UserData
from app.services.base_service import BaseService
from app.services.erasure_service import dataset_erasure_service


class DatasetService(BaseService[DatasetMetadata]):
    """Service for dataset operations using DatasetMetadata."""

    model_class = DatasetMetadata
    resource_name = "Dataset"

    def _get_id_field(self) -> str:
        """Return the unique identifier field name for datasets."""
        return "dataset_id"

    # NOTE: get_by_id() now uses BaseService implementation with _build_field_query()
    # which handles both production (Beanie field expressions) and testing (mocked models)
    # The previous override was unnecessary duplication.

    async def create_dataset(
        self,
        user_id: str,
        dataset_id: str,
        filename: str,
        original_filename: str,
        file_type: str,
        file_path: str,
        s3_url: str,
        num_rows: int,
        num_columns: int,
        columns: list[str],
        data_schema: list[SchemaField],
        file_size: int | None = None,
        statistics: dict[str, Any] | None = None,
        quality_report: dict[str, Any] | None = None,
        data_preview: list[dict[str, Any]] | None = None,
        ai_summary: AISummary | None = None,
        pii_report: PIIReport | None = None,
        inferred_schema: dict[str, Any] | None = None,
        onboarding_progress: dict[str, Any] | None = None,
        **kwargs
    ) -> DatasetMetadata:
        """
        Create dataset metadata and maintain UserData for backward compatibility.

        Args:
            user_id: User who owns the dataset
            dataset_id: Unique dataset identifier
            filename: Storage filename
            original_filename: Original filename from upload
            file_type: File type (csv, excel, json, etc.)
            file_path: Storage path (S3 key)
            s3_url: S3 URL for file access
            num_rows: Number of rows
            num_columns: Number of columns
            columns: List of column names
            data_schema: Detailed schema for each field
            file_size: File size in bytes (optional)
            statistics: Column statistics (optional)
            quality_report: Data quality assessment (optional)
            data_preview: Preview rows (optional)
            ai_summary: AI-generated summary (optional)
            pii_report: PII detection report (optional)
            inferred_schema: Full inferred schema (optional)
            onboarding_progress: Onboarding tutorial progress (optional)
            **kwargs: Additional fields

        Returns:
            Created DatasetMetadata instance
        """
        # Create DatasetMetadata
        dataset = DatasetMetadata(
            user_id=user_id,
            dataset_id=dataset_id,
            filename=filename,
            original_filename=original_filename,
            file_type=file_type,
            file_path=file_path,
            s3_url=s3_url,
            file_size=file_size,
            num_rows=num_rows,
            num_columns=num_columns,
            columns=columns,
            data_schema=data_schema,
            inferred_schema=inferred_schema,
            statistics=statistics,
            quality_report=quality_report,
            data_preview=data_preview,
            ai_summary=ai_summary,
            pii_report=pii_report,
            onboarding_progress=onboarding_progress
        )
        await dataset.save()

        # Dual-write: Maintain UserData for backward compatibility
        await self._create_legacy_userdata(
            user_id=user_id,
            dataset_id=dataset_id,
            filename=filename,
            original_filename=original_filename,
            file_type=file_type,
            file_path=file_path,
            s3_url=s3_url,
            num_rows=num_rows,
            num_columns=num_columns,
            columns=columns,
            data_schema=data_schema,
            statistics=statistics,
            quality_report=quality_report,
            data_preview=data_preview,
            ai_summary=ai_summary,
            pii_report=pii_report,
            inferred_schema=inferred_schema,
            onboarding_progress=onboarding_progress
        )

        return dataset

    async def _create_legacy_userdata(
        self,
        user_id: str,
        dataset_id: str,
        filename: str,
        original_filename: str,
        file_type: str | None,
        file_path: str,
        s3_url: str,
        num_rows: int,
        num_columns: int,
        columns: list[str],
        data_schema: list[SchemaField],
        statistics: dict[str, Any] | None,
        quality_report: dict[str, Any] | None,
        data_preview: list[dict[str, Any]] | None,
        ai_summary: AISummary | None,
        pii_report: PIIReport | None,
        inferred_schema: dict[str, Any] | None,
        onboarding_progress: dict[str, Any] | None
    ) -> None:
        """
        Create legacy UserData for backward compatibility.

        Args:
            Same as create_dataset
        """
        # Convert SchemaField to legacy format
        legacy_schema = [
            LegacySchemaField(
                field_name=field.field_name,
                field_type=field.field_type,
                data_type=field.data_type,
                inferred_dtype=field.inferred_dtype,
                unique_values=field.unique_values,
                missing_values=field.missing_values,
                example_values=field.example_values,
                is_constant=field.is_constant,
                is_high_cardinality=field.is_high_cardinality
            )
            for field in data_schema
        ]

        # Convert AISummary to legacy format
        legacy_ai_summary = None
        if ai_summary:
            legacy_ai_summary = LegacyAISummary(
                overview=ai_summary.overview,
                issues=ai_summary.issues,
                relationships=ai_summary.relationships,
                suggestions=ai_summary.suggestions,
                rawMarkdown=ai_summary.raw_markdown,
                createdAt=ai_summary.created_at
            )

        # Convert PIIReport to legacy format
        contains_pii = False
        pii_risk_level = None
        pii_report_dict = None
        pii_masked = False

        if pii_report:
            contains_pii = pii_report.contains_pii
            pii_risk_level = pii_report.risk_level
            pii_masked = pii_report.masked
            pii_report_dict = {
                "contains_pii": pii_report.contains_pii,
                "pii_fields": pii_report.pii_fields,
                "risk_level": pii_report.risk_level,
                "detection_details": pii_report.detection_details,
                "masked": pii_report.masked,
                "masked_at": pii_report.masked_at.isoformat() if pii_report.masked_at else None
            }

        # Create legacy UserData
        user_data = UserData(
            user_id=user_id,
            filename=filename,
            original_filename=original_filename,
            s3_url=s3_url,
            num_rows=num_rows,
            num_columns=num_columns,
            data_schema=legacy_schema,
            aiSummary=legacy_ai_summary,
            contains_pii=contains_pii,
            pii_report=pii_report_dict,
            pii_risk_level=pii_risk_level,
            pii_masked=pii_masked,
            is_processed=False,
            schema=inferred_schema,
            statistics=statistics,
            quality_report=quality_report,
            row_count=num_rows,
            columns=columns,
            data_preview=data_preview,
            file_type=file_type,
            onboarding_progress=onboarding_progress,
            file_path=file_path
        )

        await user_data.save()

    async def get_dataset(
        self, 
        dataset_id: str, 
        user_id: str | None = None,
        check_ownership: bool = True
    ) -> DatasetMetadata | None:
        """
        Retrieve dataset metadata by dataset ID.

        Args:
            dataset_id: Dataset identifier
            user_id: User ID for ownership check (required if check_ownership=True)
            check_ownership: Whether to verify user ownership

        Returns:
            DatasetMetadata instance or None if not found

        Raises:
            PermissionDeniedError: If user doesn't own the dataset
        """
        return await self.get_by_id(
            resource_id=dataset_id,
            user_id=user_id,
            check_ownership=check_ownership and user_id is not None
        )

    async def get_dataset_or_raise(
        self,
        dataset_id: str,
        user_id: str | None = None,
        check_ownership: bool = True
    ) -> DatasetMetadata:
        """
        Retrieve dataset metadata by dataset ID, raising NotFoundError if not found.

        Args:
            dataset_id: Dataset identifier
            user_id: User ID for ownership check
            check_ownership: Whether to verify user ownership

        Returns:
            DatasetMetadata instance

        Raises:
            NotFoundError: If dataset doesn't exist
            PermissionDeniedError: If user doesn't own the dataset
        """
        return await self.get_by_id_or_raise(
            resource_id=dataset_id,
            user_id=user_id,
            check_ownership=check_ownership and user_id is not None
        )

    # NOTE: list_for_user() now uses BaseService implementation with _build_field_query()
    # which handles both production (Beanie field expressions) and testing (mocked models)
    # The previous override was unnecessary duplication.

    async def list_datasets(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 1000
    ) -> list[DatasetMetadata]:
        """
        List all datasets for a user, sorted chronologically (newest first).

        PERFORMANCE WARNING: Default limit=1000 is high and may cause performance
        issues with large datasets. Consider using pagination with smaller limits
        (e.g., 20-100) or use list_for_user() directly with explicit pagination.

        Optimization: Uses compound index (user_id, created_at) for efficient sorting.

        Args:
            user_id: User identifier
            skip: Number of records to skip (for pagination)
            limit: Maximum records to return (default: 1000 for backward compatibility)

        Returns:
            List of DatasetMetadata instances sorted by created_at descending
        """
        return await self.list_for_user(
            user_id=user_id,
            skip=skip,
            limit=limit,
            sort_field="created_at",
            sort_ascending=False
        )

    async def update_dataset(
        self,
        dataset_id: str,
        user_id: str | None = None,
        **update_fields
    ) -> DatasetMetadata | None:
        """
        Update dataset metadata fields.

        Args:
            dataset_id: Dataset identifier
            user_id: User ID for ownership check (optional for backward compatibility)
            **update_fields: Fields to update

        Returns:
            Updated DatasetMetadata or None if not found

        Raises:
            PermissionDeniedError: If user doesn't own the dataset (when user_id provided)
        """
        # For backward compatibility, allow updates without user_id check
        if user_id:
            return await self.update(
                resource_id=dataset_id,
                user_id=user_id,
                update_data=update_fields
            )
        else:
            # Legacy path: no ownership check
            dataset = await self.get_dataset(dataset_id, check_ownership=False)
            if not dataset:
                return None

            # Update fields
            for field, value in update_fields.items():
                if hasattr(dataset, field):
                    setattr(dataset, field, value)

            # Update timestamp
            dataset.update_timestamp()

            # Save changes
            await dataset.save()

            return dataset

    async def delete_dataset(
        self,
        dataset_id: str,
        user_id: str | None = None
    ) -> bool:
        """
        Cascade-delete a dataset and every child document/artifact (issue #259).

        Delegates to the erasure service so the S3 source object, all child
        documents keyed by ``dataset_id``, per-model S3 artifacts, and the Redis
        viz-cache are removed too — not just the ``DatasetMetadata`` row. The
        sweep is idempotent, so a re-run clears any residuals.

        Note: unlike the pre-#259 implementation, this **does not raise
        NotFoundError** for a missing dataset — erasure is idempotent, so it
        returns False instead. The API route pre-checks existence for its 404.

        Args:
            dataset_id: Dataset identifier
            user_id: Owner id (looked up from the parent when omitted, for
                backward compatibility)

        Returns:
            True if a dataset existed and was erased, False if not found
        """
        # Resolve owner when the caller didn't scope it (legacy path).
        owner_id = user_id
        if owner_id is None:
            dataset = await self.get_dataset(dataset_id, check_ownership=False)
            if not dataset:
                return False
            # `or ""` guards the (near-dead) legacy no-user path: subject_user_id
            # is a required str, and an unowned "" scopes the cascade to nothing.
            owner_id = dataset.user_id or ""

        manifest = await dataset_erasure_service.erase_dataset(
            dataset_id, owner_id, actor_id=owner_id
        )
        return not manifest.idempotent_noop

    async def mark_dataset_processed(
        self,
        dataset_id: str,
        statistics: dict[str, Any] | None = None,
        quality_report: dict[str, Any] | None = None,
        inferred_schema: dict[str, Any] | None = None
    ) -> DatasetMetadata | None:
        """
        Mark dataset as processed and optionally update processing results.

        Args:
            dataset_id: Dataset identifier
            statistics: Column statistics (optional)
            quality_report: Quality assessment (optional)
            inferred_schema: Inferred schema (optional)

        Returns:
            Updated DatasetMetadata or None if not found
        """
        dataset = await self.get_dataset(dataset_id, check_ownership=False)
        if not dataset:
            return None

        # Mark as processed
        dataset.mark_processed()

        # Update processing results if provided
        if statistics:
            dataset.statistics = statistics
        if quality_report:
            dataset.quality_report = quality_report
        if inferred_schema:
            dataset.inferred_schema = inferred_schema

        await dataset.save()

        return dataset

    async def get_datasets_with_pii(self, user_id: str) -> list[DatasetMetadata]:
        """
        Get all datasets for a user that contain PII.

        Args:
            user_id: User identifier

        Returns:
            List of DatasetMetadata instances with PII
        """
        all_datasets = await self.list_datasets(user_id)
        return [dataset for dataset in all_datasets if dataset.has_pii()]

    async def get_unprocessed_datasets(self, user_id: str) -> list[DatasetMetadata]:
        """
        Get all unprocessed datasets for a user, sorted chronologically.

        Optimization: Uses compound index (user_id, is_processed, created_at).

        Args:
            user_id: User identifier

        Returns:
            List of unprocessed DatasetMetadata instances sorted by created_at descending
        """
        return await self.list_for_user(
            user_id=user_id,
            skip=0,
            limit=1000,  # Large limit to get all datasets
            sort_field="created_at",
            sort_ascending=False,
            is_processed=False
        )