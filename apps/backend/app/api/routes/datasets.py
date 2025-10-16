"""
Dataset API routes.

Provides endpoints for managing datasets using DatasetService.
Implements Story 12.1: API Integration for New Models (Dataset portion).
"""

from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File
from typing import Optional
import logging
import uuid
import hashlib
from datetime import datetime, timezone

from app.schemas.dataset import (
    DatasetListResponse,
    DatasetListItem,
    DatasetDetailResponse,
    DatasetUploadResponse,
    DatasetUpdateRequest,
    DatasetDeleteResponse,
    DatasetSchemaResponse,
    DatasetPreviewResponse,
    DatasetProcessingRequest,
    DatasetProcessingResponse
)
from app.services.dataset_service import DatasetService
from app.auth.nextauth_auth import get_current_user_id
from app.utils.s3 import upload_file_to_s3
from app.services.data_processing.data_processor import DataProcessor

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/datasets", response_model=DatasetListResponse)
async def list_datasets(
    current_user_id: str = Depends(get_current_user_id)
):
    """
    List all datasets for the authenticated user.

    Returns datasets sorted by created_at (newest first).
    """
    try:
        logger.info(f"Listing datasets for user {current_user_id}")

        service = DatasetService()
        datasets = await service.list_datasets(user_id=current_user_id)

        # Convert to list response
        dataset_items = [
            DatasetListItem(
                dataset_id=ds.dataset_id,
                filename=ds.filename,
                original_filename=ds.original_filename,
                file_type=ds.file_type,
                num_rows=ds.num_rows,
                num_columns=ds.num_columns,
                file_size=ds.file_size,
                is_processed=ds.is_processed,
                contains_pii=ds.has_pii(),
                created_at=ds.created_at,
                updated_at=ds.updated_at
            )
            for ds in datasets
        ]

        return DatasetListResponse(
            datasets=dataset_items,
            total=len(dataset_items)
        )

    except Exception as e:
        logger.error(f"Error listing datasets for user {current_user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing datasets: {str(e)}"
        )


@router.post("/datasets/upload", response_model=DatasetUploadResponse)
async def upload_dataset(
    file: UploadFile = File(...),
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Upload and process a new dataset file.

    Supported file types: csv, xlsx, xls, json, parquet.
    Returns dataset metadata with preview data.
    """
    try:
        logger.info(f"Uploading dataset {file.filename} for user {current_user_id}")

        # Validate file type
        file_extension = file.filename.split('.')[-1].lower()
        supported_types = ['csv', 'xlsx', 'xls', 'json', 'parquet']

        if file_extension not in supported_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type: .{file_extension}. Supported types: {', '.join(supported_types)}"
            )

        # Generate dataset ID
        dataset_id = f"dataset_{uuid.uuid4().hex[:16]}"

        # Read file content
        file_content = await file.read()
        file_size = len(file_content)

        # Upload to S3
        file_path = f"datasets/{current_user_id}/{dataset_id}_{file.filename}"
        success, s3_url = upload_file_to_s3(
            file_content=file_content,
            s3_filename=file_path,
            content_type=file.content_type or 'application/octet-stream'
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to upload file to S3"
            )

        # Process file with DataProcessor
        processor = DataProcessor()
        processed_data = await processor.process_bytes(
            file_bytes=file_content,
            filename=file.filename,
            file_type=file_extension
        )

        # Extract data from processed result
        preview_data = processed_data.get_preview()
        num_rows = len(processed_data.dataframe)
        num_columns = len(processed_data.dataframe.columns)
        columns = [str(col) for col in processed_data.dataframe.columns]

        # Create dataset metadata
        service = DatasetService()
        dataset = await service.create_dataset(
            user_id=current_user_id,
            dataset_id=dataset_id,
            filename=file.filename,
            original_filename=file.filename,
            file_type=file_extension,
            file_path=file_path,
            s3_url=s3_url,
            file_size=file_size,
            num_rows=num_rows,
            num_columns=num_columns,
            columns=columns,
            data_schema=[],  # Will be populated from schema inference
            data_preview=preview_data['data'],
            inferred_schema=processed_data.schema.model_dump(),
            statistics=processed_data.statistics.model_dump(),
            quality_report=processed_data.quality_report.model_dump()
        )

        logger.info(f"Dataset {dataset_id} uploaded successfully")

        # Build response with backward compatibility
        return DatasetUploadResponse(
            status="success",
            dataset_id=dataset.dataset_id,
            file_id=dataset.dataset_id,  # Backward compatibility
            filename=dataset.filename,
            num_rows=dataset.num_rows,
            num_columns=dataset.num_columns,
            preview=dataset.data_preview or [],
            headers=dataset.columns,
            s3_url=dataset.s3_url,
            file_size=dataset.file_size,
            file_type=dataset.file_type
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading dataset: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error uploading dataset: {str(e)}"
        )


@router.get("/datasets/{dataset_id}", response_model=DatasetDetailResponse)
async def get_dataset(
    dataset_id: str,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Get detailed information about a specific dataset.

    Returns full dataset metadata including schema, statistics, and quality report.
    """
    try:
        logger.info(f"Getting dataset {dataset_id}")

        service = DatasetService()
        dataset = await service.get_dataset(dataset_id=dataset_id)

        if not dataset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dataset {dataset_id} not found"
            )

        # Verify ownership
        if dataset.user_id != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this dataset"
            )

        # Build response
        return DatasetDetailResponse(
            dataset_id=dataset.dataset_id,
            filename=dataset.filename,
            original_filename=dataset.original_filename,
            file_type=dataset.file_type,
            file_path=dataset.file_path,
            s3_url=dataset.s3_url,
            file_size=dataset.file_size,
            num_rows=dataset.num_rows,
            num_columns=dataset.num_columns,
            columns=dataset.columns,
            data_schema=[field.model_dump() for field in dataset.data_schema],
            inferred_schema=dataset.inferred_schema,
            statistics=dataset.statistics,
            quality_report=dataset.quality_report,
            data_preview=dataset.data_preview,
            ai_summary=dataset.ai_summary.model_dump() if dataset.ai_summary else None,
            pii_report=dataset.pii_report.model_dump() if dataset.pii_report else None,
            is_processed=dataset.is_processed,
            processed_at=dataset.processed_at,
            version=dataset.version,
            created_at=dataset.created_at,
            updated_at=dataset.updated_at
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting dataset {dataset_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting dataset: {str(e)}"
        )


@router.put("/datasets/{dataset_id}", response_model=DatasetDetailResponse)
async def update_dataset(
    dataset_id: str,
    update_data: DatasetUpdateRequest,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Update dataset metadata.

    Can update statistics, quality_report, ai_summary, and other metadata fields.
    """
    try:
        logger.info(f"Updating dataset {dataset_id}")

        service = DatasetService()
        dataset = await service.get_dataset(dataset_id=dataset_id)

        if not dataset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dataset {dataset_id} not found"
            )

        # Verify ownership
        if dataset.user_id != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this dataset"
            )

        # Build update fields from request
        update_fields = {}
        if update_data.statistics is not None:
            update_fields['statistics'] = update_data.statistics
        if update_data.quality_report is not None:
            update_fields['quality_report'] = update_data.quality_report
        if update_data.ai_summary is not None:
            update_fields['ai_summary'] = update_data.ai_summary
        if update_data.inferred_schema is not None:
            update_fields['inferred_schema'] = update_data.inferred_schema

        # Update dataset
        updated_dataset = await service.update_dataset(
            dataset_id=dataset_id,
            **update_fields
        )

        logger.info(f"Dataset {dataset_id} updated successfully")

        # Build response
        return DatasetDetailResponse(
            dataset_id=updated_dataset.dataset_id,
            filename=updated_dataset.filename,
            original_filename=updated_dataset.original_filename,
            file_type=updated_dataset.file_type,
            file_path=updated_dataset.file_path,
            s3_url=updated_dataset.s3_url,
            file_size=updated_dataset.file_size,
            num_rows=updated_dataset.num_rows,
            num_columns=updated_dataset.num_columns,
            columns=updated_dataset.columns,
            data_schema=[field.model_dump() for field in updated_dataset.data_schema],
            inferred_schema=updated_dataset.inferred_schema,
            statistics=updated_dataset.statistics,
            quality_report=updated_dataset.quality_report,
            data_preview=updated_dataset.data_preview,
            ai_summary=updated_dataset.ai_summary.model_dump() if updated_dataset.ai_summary else None,
            pii_report=updated_dataset.pii_report.model_dump() if updated_dataset.pii_report else None,
            is_processed=updated_dataset.is_processed,
            processed_at=updated_dataset.processed_at,
            version=updated_dataset.version,
            created_at=updated_dataset.created_at,
            updated_at=updated_dataset.updated_at
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating dataset {dataset_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating dataset: {str(e)}"
        )


@router.delete("/datasets/{dataset_id}", response_model=DatasetDeleteResponse)
async def delete_dataset(
    dataset_id: str,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Delete a dataset.

    This will remove the dataset metadata. S3 cleanup is handled separately.
    """
    try:
        logger.info(f"Deleting dataset {dataset_id}")

        service = DatasetService()
        dataset = await service.get_dataset(dataset_id=dataset_id)

        if not dataset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dataset {dataset_id} not found"
            )

        # Verify ownership
        if dataset.user_id != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this dataset"
            )

        # Delete dataset
        success = await service.delete_dataset(dataset_id=dataset_id)

        if success:
            logger.info(f"Dataset {dataset_id} deleted successfully")
            return DatasetDeleteResponse(
                status="success",
                dataset_id=dataset_id,
                message=f"Dataset {dataset_id} deleted successfully"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete dataset"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting dataset {dataset_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting dataset: {str(e)}"
        )


@router.get("/datasets/{dataset_id}/schema", response_model=DatasetSchemaResponse)
async def get_dataset_schema(
    dataset_id: str,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Get dataset schema information.

    Returns detailed field-level schema with types and statistics.
    """
    try:
        logger.info(f"Getting schema for dataset {dataset_id}")

        service = DatasetService()
        dataset = await service.get_dataset(dataset_id=dataset_id)

        if not dataset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dataset {dataset_id} not found"
            )

        # Verify ownership
        if dataset.user_id != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this dataset"
            )

        # Build schema response
        return DatasetSchemaResponse(
            dataset_id=dataset.dataset_id,
            schema=[field.model_dump() for field in dataset.data_schema],
            num_fields=len(dataset.data_schema)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting schema for dataset {dataset_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting schema: {str(e)}"
        )


@router.get("/datasets/{dataset_id}/preview", response_model=DatasetPreviewResponse)
async def get_dataset_preview(
    dataset_id: str,
    limit: int = 10,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Get preview rows from dataset.

    Returns up to `limit` rows of data for preview.
    """
    try:
        logger.info(f"Getting preview for dataset {dataset_id}")

        service = DatasetService()
        dataset = await service.get_dataset(dataset_id=dataset_id)

        if not dataset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dataset {dataset_id} not found"
            )

        # Verify ownership
        if dataset.user_id != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this dataset"
            )

        # Get preview data
        preview_data = dataset.data_preview or []

        # Limit preview rows
        limited_preview = preview_data[:limit]

        return DatasetPreviewResponse(
            dataset_id=dataset.dataset_id,
            preview=limited_preview,
            total_rows=dataset.num_rows,
            preview_rows=len(limited_preview)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting preview for dataset {dataset_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting preview: {str(e)}"
        )


@router.post("/datasets/{dataset_id}/process", response_model=DatasetProcessingResponse)
async def mark_dataset_processed(
    dataset_id: str,
    processing_data: DatasetProcessingRequest,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Mark dataset as processed and update processing results.

    Updates statistics, quality_report, and inferred_schema from processing pipeline.
    """
    try:
        logger.info(f"Marking dataset {dataset_id} as processed")

        service = DatasetService()
        dataset = await service.get_dataset(dataset_id=dataset_id)

        if not dataset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dataset {dataset_id} not found"
            )

        # Verify ownership
        if dataset.user_id != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this dataset"
            )

        # Mark as processed with results
        updated_dataset = await service.mark_dataset_processed(
            dataset_id=dataset_id,
            statistics=processing_data.statistics,
            quality_report=processing_data.quality_report,
            inferred_schema=processing_data.inferred_schema
        )

        logger.info(f"Dataset {dataset_id} marked as processed")

        return DatasetProcessingResponse(
            dataset_id=updated_dataset.dataset_id,
            is_processed=updated_dataset.is_processed,
            processed_at=updated_dataset.processed_at,
            statistics=updated_dataset.statistics,
            quality_report=updated_dataset.quality_report
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking dataset {dataset_id} as processed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing dataset: {str(e)}"
        )
