"""
Dataset service for DatasetMetadata operations.

This service handles CRUD operations for datasets using the new DatasetMetadata model,
while maintaining backward compatibility with the legacy UserData model through dual-write.
"""

from typing import List, Optional, Any, Dict
from app.models.dataset import DatasetMetadata, SchemaField, AISummary, PIIReport
from app.models.user_data import UserData, SchemaField as LegacySchemaField, AISummary as LegacyAISummary


class DatasetService:
    """Service for dataset operations using DatasetMetadata."""

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
        columns: List[str],
        data_schema: List[SchemaField],
        file_size: Optional[int] = None,
        statistics: Optional[Dict[str, Any]] = None,
        quality_report: Optional[Dict[str, Any]] = None,
        data_preview: Optional[List[Dict[str, Any]]] = None,
        ai_summary: Optional[AISummary] = None,
        pii_report: Optional[PIIReport] = None,
        inferred_schema: Optional[Dict[str, Any]] = None,
        onboarding_progress: Optional[Dict[str, Any]] = None,
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
        file_type: Optional[str],
        file_path: str,
        s3_url: str,
        num_rows: int,
        num_columns: int,
        columns: List[str],
        data_schema: List[SchemaField],
        statistics: Optional[Dict[str, Any]],
        quality_report: Optional[Dict[str, Any]],
        data_preview: Optional[List[Dict[str, Any]]],
        ai_summary: Optional[AISummary],
        pii_report: Optional[PIIReport],
        inferred_schema: Optional[Dict[str, Any]],
        onboarding_progress: Optional[Dict[str, Any]]
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

    async def get_dataset(self, dataset_id: str) -> Optional[DatasetMetadata]:
        """
        Retrieve dataset metadata by dataset ID.

        Args:
            dataset_id: Dataset identifier

        Returns:
            DatasetMetadata instance or None if not found
        """
        return await DatasetMetadata.find_one(DatasetMetadata.dataset_id == dataset_id)

    async def list_datasets(self, user_id: str) -> List[DatasetMetadata]:
        """
        List all datasets for a user.

        Args:
            user_id: User identifier

        Returns:
            List of DatasetMetadata instances
        """
        return await DatasetMetadata.find(DatasetMetadata.user_id == user_id).to_list()

    async def update_dataset(
        self,
        dataset_id: str,
        **update_fields
    ) -> Optional[DatasetMetadata]:
        """
        Update dataset metadata fields.

        Args:
            dataset_id: Dataset identifier
            **update_fields: Fields to update

        Returns:
            Updated DatasetMetadata or None if not found
        """
        dataset = await self.get_dataset(dataset_id)
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

    async def delete_dataset(self, dataset_id: str) -> bool:
        """
        Delete dataset metadata.

        Args:
            dataset_id: Dataset identifier

        Returns:
            True if deleted, False if not found
        """
        dataset = await self.get_dataset(dataset_id)
        if not dataset:
            return False

        await dataset.delete()
        return True

    async def mark_dataset_processed(
        self,
        dataset_id: str,
        statistics: Optional[Dict[str, Any]] = None,
        quality_report: Optional[Dict[str, Any]] = None,
        inferred_schema: Optional[Dict[str, Any]] = None
    ) -> Optional[DatasetMetadata]:
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
        dataset = await self.get_dataset(dataset_id)
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

    async def get_datasets_with_pii(self, user_id: str) -> List[DatasetMetadata]:
        """
        Get all datasets for a user that contain PII.

        Args:
            user_id: User identifier

        Returns:
            List of DatasetMetadata instances with PII
        """
        all_datasets = await self.list_datasets(user_id)
        return [dataset for dataset in all_datasets if dataset.has_pii()]

    async def get_unprocessed_datasets(self, user_id: str) -> List[DatasetMetadata]:
        """
        Get all unprocessed datasets for a user.

        Args:
            user_id: User identifier

        Returns:
            List of unprocessed DatasetMetadata instances
        """
        return await DatasetMetadata.find(
            DatasetMetadata.user_id == user_id,
            DatasetMetadata.is_processed == False
        ).to_list()
