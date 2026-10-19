"""
Dataset API routes.

Provides endpoints for managing datasets using DatasetService.
Implements Story 12.1: API Integration for New Models (Dataset portion).
"""

import logging
import time
import uuid

import numpy as np
from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    HTTPException,
    Path,
    Query,
    UploadFile,
    status,
)

from app.auth.nextauth_auth import get_current_user_id
from app.billing.enforcement import quota
from app.billing.storage import enforce_storage_ceiling
from app.models.dataset import DatasetMetadata
from app.schemas.dataset import (
    DatasetDeleteResponse,
    DatasetDetailResponse,
    DatasetListItem,
    DatasetListResponse,
    DatasetPreviewResponse,
    DatasetProcessingRequest,
    DatasetProcessingResponse,
    DatasetSchemaResponse,
    DatasetUpdateRequest,
    DatasetUploadResponse,
)
from app.schemas.erasure import EraseResponse, ErasureRequest
from app.schemas.feature_selection import (
    FeatureImportanceRequest,
    FeatureImportanceResponse,
    FeatureSelectionRequest,
    FeatureSelectionResult,
    MethodComparisonRequest,
    MethodComparisonResponse,
    RedundancyDetectionRequest,
    RedundancyDetectionResponse,
    SelectedFeaturesResponse,
)
from app.schemas.preview import PreviewRequest, PreviewResponse
from app.services.data_processing.data_processor import (
    DataProcessor,
    EmptyFileError,
    ProcessedData,
    UnreadableFileError,
)
from app.services.dataset_service import DatasetService
from app.services.erasure_service import dataset_erasure_service
from app.services.model_training.feature_selection_service import (
    FeatureSelectionConfig,
    FeatureSelectionService,
)
from app.services.versioning_service import versioning_service
from app.utils.s3 import dataset_s3_key, upload_file_to_s3
from app.utils.upload_limits import read_upload_capped

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/datasets", response_model=DatasetListResponse)
async def list_datasets(
    current_user_id: str = Depends(get_current_user_id),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(20, ge=1, le=100, description="Items per page (max 100)")
):
    """
    List all datasets for the authenticated user with pagination.

    Returns datasets sorted by created_at (newest first).

    Args:
        current_user_id: Authenticated user ID
        page: Page number (1-indexed, default: 1)
        limit: Items per page (max 100, default: 20)

    Returns:
        Paginated list of datasets with metadata
    """
    try:
        logger.info(f"Listing datasets for user {current_user_id} (page={page}, limit={limit})")

        service = DatasetService()

        # Calculate skip for database-level pagination
        skip = (page - 1) * limit

        # Get paginated datasets with database-level pagination for better performance
        datasets = await service.list_datasets(
            user_id=current_user_id,
            skip=skip,
            limit=limit
        )

        # Get total count for pagination metadata
        total = await service.count_for_user(current_user_id)

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
            total=total
        )

    except Exception as e:
        logger.error(f"Error listing datasets for user {current_user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while listing datasets. Please try again or contact support."
        )


_UPLOAD_TYPES = ("csv", "xlsx", "xls", "json", "parquet")


def _upload_extension(file: UploadFile) -> str:
    """The upload's extension, or 400 for a missing name or an unsupported type."""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is missing a filename."
        )
    extension = file.filename.split('.')[-1].lower()
    if extension not in _UPLOAD_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: .{extension}. Supported types: {', '.join(_UPLOAD_TYPES)}"
        )
    return extension


async def _processed_upload(content: bytes, filename: str, extension: str) -> ProcessedData:
    """The parsed upload, or 400 for bytes that cannot be read as their type (#899).

    Runs before the S3 put, so a file nobody can use is never stored.
    """
    try:
        return await DataProcessor().process_bytes(
            file_bytes=content, filename=filename, file_type=extension
        )
    except EmptyFileError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except UnreadableFileError as e:
        # With the traceback: a reader defect would otherwise pass for a bad file.
        logger.warning(f"Upload could not be read as .{extension}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not read the file as .{extension}: {e}"
        ) from e


def _stored_upload(user_id: str, filename: str, content: bytes, content_type: str | None) -> tuple[str, str]:
    """Put the upload under a server-derived key (#496/#581); the client filename never
    reaches the key. Returns (key, url), or 500 when the put fails."""
    file_path = dataset_s3_key(user_id, filename)
    success, s3_url = upload_file_to_s3(
        file_content=content,
        s3_filename=file_path,
        content_type=content_type or 'application/octet-stream'
    )
    if not success or s3_url is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload file to S3"
        )
    return file_path, s3_url


async def _create_base_version(dataset: DatasetMetadata, content: bytes, user_id: str) -> None:
    """The lineage root (#276). Best-effort: versioning must never fail the upload."""
    try:
        await versioning_service.create_base_version(
            dataset_metadata=dataset, file_content=content, user_id=user_id
        )
    except Exception as e:
        logger.warning(f"Failed to create base version for dataset {dataset.dataset_id}: {e}")


@router.post(
    "/datasets/upload",
    response_model=DatasetUploadResponse,
    dependencies=[Depends(quota("uploads"))],
)
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
        extension = _upload_extension(file)
        filename = str(file.filename)
        file_content = await read_upload_capped(file)
        file_size = len(file_content)
        await enforce_storage_ceiling(current_user_id, file_size)

        processed_data = await _processed_upload(file_content, filename, extension)
        file_path, s3_url = _stored_upload(current_user_id, filename, file_content, file.content_type)

        dataset = await DatasetService().create_dataset(
            user_id=current_user_id,
            dataset_id=f"dataset_{uuid.uuid4().hex[:16]}",
            filename=filename,
            original_filename=filename,
            file_type=extension,
            file_path=file_path,
            s3_url=s3_url,
            file_size=file_size,
            num_rows=len(processed_data.dataframe),
            num_columns=len(processed_data.dataframe.columns),
            columns=[str(col) for col in processed_data.dataframe.columns],
            data_schema=[],  # Will be populated from schema inference
            data_preview=processed_data.get_preview()['data'],
            inferred_schema=processed_data.schema.model_dump(),
            statistics=processed_data.statistics.model_dump(),
            quality_report=processed_data.quality_report.model_dump()
        )
        await _create_base_version(dataset, file_content, current_user_id)
        logger.info(f"Dataset {dataset.dataset_id} uploaded successfully")

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
        logger.error(f"Error uploading dataset: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while uploading the dataset. Please try again or contact support."
        )


#: What PUT /datasets/{id} may change. The request also carries pii_report, which this
#: route has never applied.
_UPDATABLE = {"statistics", "quality_report", "ai_summary", "inferred_schema"}


async def _callers_dataset(dataset_id: str, user_id: str) -> DatasetMetadata:
    """The caller's dataset, or 404.

    A dataset that is someone else's answers exactly like one that does not exist.
    These routes used to answer 403 "Access denied" for it, which told any signed-in
    caller which ids are real (#751).
    """
    dataset = await DatasetService().get_dataset(dataset_id=dataset_id)
    if dataset is None or dataset.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {dataset_id} not found"
        )
    return dataset


def _detail(dataset: DatasetMetadata) -> DatasetDetailResponse:
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

        dataset = await _callers_dataset(dataset_id, current_user_id)

        return _detail(dataset)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting dataset {dataset_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving the dataset. Please try again or contact support."
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

        await _callers_dataset(dataset_id, current_user_id)

        updated_dataset = await DatasetService().update_dataset(
            dataset_id=dataset_id,
            **update_data.model_dump(exclude_none=True, include=_UPDATABLE),
        )

        if not updated_dataset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dataset {dataset_id} not found"
            )

        logger.info(f"Dataset {dataset_id} updated successfully")

        return _detail(updated_dataset)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating dataset {dataset_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while updating the dataset. Please try again or contact support."
        )


@router.delete("/datasets/{dataset_id}", response_model=DatasetDeleteResponse)
async def delete_dataset(
    dataset_id: str,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Delete a dataset.

    Cascade-deletes the dataset: the S3 source object, every child document
    keyed by ``dataset_id`` (versions, lineage, workflow, training jobs, ML
    models + their S3 artifacts, viz cache, column stats, features, etc.), and
    the Redis viz-cache. Idempotent (issue #259).
    """
    try:
        logger.info(f"Deleting dataset {dataset_id}")

        await _callers_dataset(dataset_id, current_user_id)

        # Cascade-delete dataset + all children/artifacts
        success = await DatasetService().delete_dataset(
            dataset_id=dataset_id, user_id=current_user_id
        )

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
        logger.error(f"Error deleting dataset {dataset_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while deleting the dataset. Please try again or contact support."
        )


@router.post("/datasets/{dataset_id}/erase", response_model=EraseResponse)
async def erase_dataset(
    dataset_id: str,
    request: ErasureRequest | None = Body(None),
    current_user_id: str = Depends(get_current_user_id),
):
    """
    Right-to-erasure for a single dataset (issue #259).

    Cascade-erases the dataset across both id-spaces and returns a deletion
    manifest recording exactly what was removed (per-collection counts, S3
    objects, Redis keys, and any failures). The operation is recorded in an
    append-only audit log; the returned ``erasure_id`` identifies that entry
    (``None`` when nothing was erased). Idempotent: erasing an already-erased or
    unowned dataset returns a no-op manifest.
    """
    manifest = await dataset_erasure_service.erase_dataset(
        dataset_id,
        current_user_id,
        actor_id=current_user_id,
        reason=request.reason if request else None,
    )
    return EraseResponse(
        erasure_id=manifest.erasure_id, status=manifest.status, manifest=manifest
    )


# NOTE: user-scoped, but lives on the datasets router because erasure is
# implemented here; it resolves to /api/v1/users/me/erase. Move to a users.py
# router if that surface grows.
@router.post("/users/me/erase", response_model=EraseResponse)
async def erase_current_user_data(
    request: ErasureRequest | None = Body(None),
    current_user_id: str = Depends(get_current_user_id),
):
    """
    Right-to-erasure for all data owned by the authenticated user (issue #259).

    Cascade-erases every dataset the user owns (both id-spaces) plus leftover
    user-scoped records (models, jobs, feedback), returning an aggregate
    deletion manifest. Recorded in the append-only audit log. Does not delete
    the account/auth record itself — only the user's data.
    """
    manifest = await dataset_erasure_service.erase_user(
        current_user_id,
        actor_id=current_user_id,
        reason=request.reason if request else None,
    )
    return EraseResponse(
        erasure_id=manifest.erasure_id, status=manifest.status, manifest=manifest
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

        dataset = await _callers_dataset(dataset_id, current_user_id)

        # Build schema response
        return DatasetSchemaResponse(
            dataset_id=dataset.dataset_id,
            schema=[field.model_dump() for field in dataset.data_schema],
            num_fields=len(dataset.data_schema)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting schema for dataset {dataset_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving the dataset schema. Please try again or contact support."
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

        dataset = await _callers_dataset(dataset_id, current_user_id)

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
        logger.error(f"Error getting preview for dataset {dataset_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while generating the dataset preview. Please try again or contact support."
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

        await _callers_dataset(dataset_id, current_user_id)

        # Mark as processed with results
        updated_dataset = await DatasetService().mark_dataset_processed(
            dataset_id=dataset_id,
            statistics=processing_data.statistics,
            quality_report=processing_data.quality_report,
            inferred_schema=processing_data.inferred_schema
        )

        if not updated_dataset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dataset {dataset_id} not found"
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
        logger.error(f"Error marking dataset {dataset_id} as processed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing the dataset. Please try again or contact support."
        )


@router.post(
    "/datasets/{dataset_id}/transformations/preview",
    response_model=PreviewResponse,
    summary="Preview transformation effects on dataset sample",
    description="""
    Generate a preview of transformation effects before applying them permanently.

    This endpoint:
    - Loads a sample of rows from the dataset (configurable size: 10-1000 rows)
    - Applies transformation operations sequentially
    - Calculates impact statistics (rows affected, quality score changes, etc.)
    - Returns both original and transformed data for side-by-side comparison

    **Performance**:
    - Results cache pending (future optimization)
    - Response time: < 3 seconds for 1000 rows
    - Memory usage: ~50-200 MB for max sample size

    **Rate Limiting**:
    - Rate limiting infrastructure prepared (future enhancement)
    - Planned: Maximum 5 concurrent preview requests per user

    **Timeout**:
    - Preview generation will timeout after 30 seconds
    - Complex transformations on large samples may timeout
    """,
    responses={
        200: {
            "description": "Preview generated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "preview_result": {
                            "original_data": [
                                {"id": 1, "age": None, "salary": 50000},
                                {"id": 2, "age": 30, "salary": 75000}
                            ],
                            "transformed_data": [
                                {"id": 1, "age": 28, "salary": 50000},
                                {"id": 2, "age": 30, "salary": 75000}
                            ],
                            "impact_stats": {
                                "rows_affected": 1,
                                "values_changed": 1,
                                "columns_affected": ["age"],
                                "quality_score_before": 0.8,
                                "quality_score_after": 1.0,
                                "value_distributions": {}
                            },
                            "warnings": ["Replaced 1 null value in 'age' column with mean"],
                            "errors": []
                        },
                        "error": None,
                        "cache_hit": False
                    }
                }
            }
        },
        404: {
            "description": "Dataset not found or not owned by user",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Dataset dataset_id123 not found or not owned by user"
                    }
                }
            }
        },
        408: {
            "description": "Preview generation timeout (>30 seconds)",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Preview generation timeout after 30 seconds. Try reducing sample_size or simplifying transformations."
                    }
                }
            }
        },
        429: {
            "description": "Rate limit exceeded or queue full",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Too many concurrent preview requests. Please wait before retrying."
                    }
                }
            }
        },
        500: {
            "description": "Internal server error during preview generation",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Preview generation failed: [error details]"
                    }
                }
            }
        }
    }
)
async def preview_transformation(
    dataset_id: str = Path(..., description="Dataset identifier"),
    request: PreviewRequest = Body(..., description="Preview request with transformation operations and sample size"),
    current_user_id: str = Depends(get_current_user_id)
) -> PreviewResponse:
    """
    Preview transformation effects before applying them permanently.

    This endpoint:
    1. Verifies user owns the dataset (CRITICAL SECURITY CHECK)
    2. Loads sample data from S3 (limited by sample_size parameter)
    3. Applies transformations via PreviewService sequentially
    4. Calculates impact statistics by comparing original vs transformed data
    5. Returns before/after data with impact metrics for side-by-side comparison

    Args:
        dataset_id: Dataset identifier from URL path
        request: PreviewRequest containing:
            - operations: List of TransformationStepRequest to preview
            - sample_size: Number of rows to sample (10-1000, default 100)
        current_user_id: Authenticated user ID (from JWT dependency)

    Returns:
        PreviewResponse with:
        - success: Whether preview generation succeeded
        - preview_result: PreviewResult with original/transformed data and impact stats (null if failed)
        - error: Error message if preview failed (null if successful)
        - cache_hit: Whether result was served from cache (false currently, pending implementation)

    Raises:
        HTTPException 404: Dataset not found or not owned by user
        HTTPException 408: Preview generation timeout (>30 seconds)
        HTTPException 429: Rate limit exceeded (when rate limiting is implemented)
        HTTPException 500: Internal server error during preview generation

    Impact Statistics Explained:
        - rows_affected: Count of rows with ANY cell changes
        - values_changed: Total number of individual cells modified
        - columns_affected: Which columns had modifications
        - quality_score_before: Data quality before transformation (0.0-1.0)
        - quality_score_after: Data quality after transformation (0.0-1.0)
        - value_distributions: Before/after value frequency for affected columns

    Example Request:
        POST /api/datasets/dataset123/transformations/preview
        {
            "operations": [
                {"transformation_type": "remove_nulls", "column": "age"},
                {"transformation_type": "remove_outliers", "column": "salary", "parameters": {"method": "iqr"}}
            ],
            "sample_size": 100
        }

    Example Response (success):
        {
            "success": true,
            "preview_result": {
                "original_data": [
                    {"id": 1, "age": null, "salary": 50000},
                    {"id": 2, "age": 30, "salary": 75000},
                    {"id": 3, "age": 45, "salary": 120000}
                ],
                "transformed_data": [
                    {"id": 1, "age": 28, "salary": 50000},
                    {"id": 2, "age": 30, "salary": 75000},
                    {"id": 3, "age": 45, "salary": 75000}
                ],
                "impact_stats": {
                    "rows_affected": 2,
                    "values_changed": 2,
                    "columns_affected": ["age", "salary"],
                    "quality_score_before": 0.72,
                    "quality_score_after": 0.89,
                    "value_distributions": {
                        "age": {
                            "before": {"28": 0, "30": 1, "45": 1, "null": 1},
                            "after": {"28": 1, "30": 1, "45": 1}
                        },
                        "salary": {
                            "before": {"50000": 1, "75000": 1, "120000": 1},
                            "after": {"50000": 1, "75000": 2}
                        }
                    }
                },
                "warnings": [
                    "Replaced 1 null value in 'age' column with mean (28.0)",
                    "Removed 1 outlier in 'salary' column (IQR method)"
                ],
                "errors": []
            },
            "error": null,
            "cache_hit": false
        }

    Performance Notes:
        - Sample size 10 rows: ~200-500ms
        - Sample size 100 rows (default): ~500ms - 1s
        - Sample size 500 rows: ~1-2s
        - Sample size 1000 rows: ~2-3s
        - S3 optimization: Loads only sample_size rows from file (memory efficient)
        - Frontend debouncing: 300ms delay reduces redundant API calls
    """
    try:
        logger.info(f"Previewing transformations for dataset {dataset_id} (user={current_user_id}, sample_size={request.sample_size})")

        # CRITICAL SECURITY CHECK: Verify user owns this dataset
        dataset = await DatasetMetadata.find_one({
            "dataset_id": dataset_id,
            "user_id": current_user_id
        })

        if not dataset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dataset {dataset_id} not found or not owned by user"
            )

        # Import PreviewService here to avoid circular imports
        from app.services.data_processing.preview_service_integration import (
            preview_service,
        )

        # Call PreviewService to generate preview
        preview_result = await preview_service.generate_preview(
            user_id=current_user_id,
            dataset_id=dataset_id,
            s3_file_path=dataset.s3_url,
            operations=request.operations,
            sample_size=request.sample_size
        )

        logger.info(f"Preview generated successfully for dataset {dataset_id}")

        return PreviewResponse(
            success=True,
            preview_result=preview_result,
            error=None,
            cache_hit=False  # PreviewService tracks this internally
        )

    except HTTPException:
        # Re-raise HTTPExceptions from PreviewService (429, 408)
        raise
    except Exception as e:
        logger.error(f"Preview generation failed for dataset {dataset_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during preview generation. Please try again or contact support."
        )


# ==================== Feature Selection Endpoints ====================


@router.post(
    "/datasets/{dataset_id}/features/select",
    response_model=FeatureSelectionResult,
    tags=["Feature Selection"],
    summary="Run feature selection algorithm",
    description="Select the most important features from a dataset using various algorithms (correlation, mutual info, random forest, RFE, LASSO, statistical tests)"
)
async def select_features(
    dataset_id: str = Path(..., description="Dataset ID"),
    request: FeatureSelectionRequest = Body(...),
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Run feature selection on a dataset using the specified algorithm.

    Supported methods:
    - correlation: Pearson correlation with target
    - mutual_info: Mutual information (captures non-linear relationships)
    - random_forest: Tree-based feature importance
    - rfe: Recursive Feature Elimination
    - lasso: LASSO regularization (L1 penalty)
    - statistical: Chi-squared or F-test

    Args:
        dataset_id: Dataset identifier
        request: Feature selection configuration
        current_user_id: Authenticated user ID

    Returns:
        Feature selection results with scores and explanations
    """
    try:
        logger.info(
            f"Feature selection for dataset {dataset_id} (user={current_user_id}, "
            f"method={request.method}, target={request.target_column})"
        )

        service = FeatureSelectionService()

        # Create configuration
        config = FeatureSelectionConfig(
            top_k=request.top_k,
            threshold=request.threshold,
            correlation_threshold=request.correlation_threshold or 0.7,
            problem_type=request.problem_type,
            sample_size=request.sample_size,
            algorithm_params=request.algorithm_params or {}
        )

        # Run feature selection
        result = await service.select_features(
            dataset_id=dataset_id,
            user_id=current_user_id,
            target_column=request.target_column,
            method=request.method,
            config=config
        )

        logger.info(
            f"Feature selection complete for dataset {dataset_id}: "
            f"selected {len(result['selected_features'])} features"
        )

        return FeatureSelectionResult(**result)

    except ValueError as e:
        logger.error(f"Invalid request for feature selection: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Feature selection failed for dataset {dataset_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during feature selection. Please try again or contact support."
        )


@router.post(
    "/datasets/{dataset_id}/features/importance",
    response_model=FeatureImportanceResponse,
    tags=["Feature Selection"],
    summary="Calculate feature importance",
    description="Calculate and rank feature importance scores without applying selection criteria"
)
async def calculate_feature_importance(
    dataset_id: str = Path(..., description="Dataset ID"),
    request: FeatureImportanceRequest = Body(...),
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Calculate feature importance scores without selecting features.

    Returns importance scores for all features ranked by importance.

    Args:
        dataset_id: Dataset identifier
        request: Importance calculation configuration
        current_user_id: Authenticated user ID

    Returns:
        Feature importance scores and rankings
    """
    try:
        logger.info(
            f"Calculating feature importance for dataset {dataset_id} "
            f"(method={request.method}, target={request.target_column})"
        )

        service = FeatureSelectionService()

        # Track execution time
        start_time = time.perf_counter()

        feature_scores = await service.calculate_importance(
            dataset_id=dataset_id,
            user_id=current_user_id,
            target_column=request.target_column,
            method=request.method,
            problem_type=request.problem_type,
            algorithm_params=request.algorithm_params
        )

        # Calculate execution time in milliseconds
        execution_time_ms = (time.perf_counter() - start_time) * 1000

        return FeatureImportanceResponse(
            dataset_id=dataset_id,
            method=request.method,
            feature_scores=feature_scores,
            execution_time_ms=execution_time_ms
        )

    except ValueError as e:
        logger.error(f"Invalid request for importance calculation: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Importance calculation failed for dataset {dataset_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during feature importance calculation. Please try again or contact support."
        )


@router.post(
    "/datasets/{dataset_id}/features/redundancy",
    response_model=RedundancyDetectionResponse,
    tags=["Feature Selection"],
    summary="Detect redundant features",
    description="Identify pairs of highly correlated features that provide redundant information"
)
async def detect_redundant_features(
    dataset_id: str = Path(..., description="Dataset ID"),
    request: RedundancyDetectionRequest = Body(...),
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Detect pairs of highly correlated (redundant) features.

    Identifies features that may cause multicollinearity issues in models.

    Args:
        dataset_id: Dataset identifier
        request: Redundancy detection configuration
        current_user_id: Authenticated user ID

    Returns:
        Redundant feature pairs with correlations and recommendations
    """
    try:
        logger.info(
            f"Detecting redundant features for dataset {dataset_id} "
            f"(threshold={request.correlation_threshold})"
        )

        service = FeatureSelectionService()

        # Load dataset
        df, _ = await service._load_dataset(dataset_id, current_user_id)

        # Get numeric columns only
        numeric_df = df.select_dtypes(include=[np.number])

        # Detect redundancy
        redundant_pairs = await service.detect_redundancy(
            numeric_df,
            request.correlation_threshold
        )

        # Calculate full correlation matrix
        from app.services.data_processing.statistics_engine import StatisticsEngine
        stats_engine = StatisticsEngine()
        correlation_matrix = stats_engine._calculate_correlation_matrix(numeric_df)

        # Generate recommendations
        recommendations = []
        if redundant_pairs:
            recommendations.append(
                f"Found {len(redundant_pairs)} pairs of highly correlated features. "
                "Consider removing one feature from each pair to reduce multicollinearity."
            )
        else:
            recommendations.append(
                f"No highly correlated features found (threshold={request.correlation_threshold}). "
                "Dataset shows good feature independence."
            )

        return RedundancyDetectionResponse(
            dataset_id=dataset_id,
            redundant_pairs=redundant_pairs,
            correlation_matrix=correlation_matrix,
            recommendations=recommendations
        )

    except ValueError as e:
        logger.error(f"Invalid request for redundancy detection: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Redundancy detection failed for dataset {dataset_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during redundancy detection. Please try again or contact support."
        )


@router.post(
    "/datasets/{dataset_id}/features/compare",
    response_model=MethodComparisonResponse,
    tags=["Feature Selection"],
    summary="Compare selection methods",
    description="Run multiple feature selection algorithms and identify consensus features across methods"
)
async def compare_selection_methods(
    dataset_id: str = Path(..., description="Dataset ID"),
    request: MethodComparisonRequest = Body(...),
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Compare multiple feature selection methods side-by-side.

    Runs multiple selection algorithms and identifies consensus features.
    Useful for understanding which features are consistently important
    across different selection approaches.

    Args:
        dataset_id: Dataset identifier
        request: Method comparison configuration
        current_user_id: Authenticated user ID

    Returns:
        Comparison results with consensus features and overlap matrix
    """
    try:
        logger.info(
            f"Comparing feature selection methods for dataset {dataset_id} "
            f"(methods={request.methods}, target={request.target_column})"
        )

        if len(request.methods) < 2:
            raise ValueError("At least 2 methods required for comparison")

        if len(request.methods) > 6:
            raise ValueError("Maximum 6 methods allowed for comparison")

        service = FeatureSelectionService()

        result = await service.compare_methods(
            dataset_id=dataset_id,
            user_id=current_user_id,
            target_column=request.target_column,
            methods=request.methods,
            top_k=request.top_k if request.top_k is not None else 10,
            problem_type=request.problem_type
        )

        logger.info(
            f"Method comparison complete for dataset {dataset_id}: "
            f"{len(result['consensus_features'])} consensus features"
        )

        return MethodComparisonResponse(**result)

    except ValueError as e:
        logger.error(f"Invalid request for method comparison: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Method comparison failed for dataset {dataset_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during method comparison. Please try again or contact support."
        )


@router.get(
    "/datasets/{dataset_id}/features/selected",
    response_model=SelectedFeaturesResponse,
    tags=["Feature Selection"],
    summary="Get selected features",
    description="Retrieve previously selected features for a dataset from cache or metadata"
)
async def get_selected_features(
    dataset_id: str = Path(..., description="Dataset ID"),
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Get previously selected features for a dataset.

    Returns cached feature selection results if available.

    Args:
        dataset_id: Dataset identifier
        current_user_id: Authenticated user ID

    Returns:
        Previously selected features or empty list

    Raises:
        HTTPException: 404 if the dataset is not the caller's or does not exist
    """
    logger.info(f"Retrieving selected features for dataset {dataset_id}")

    dataset = await _callers_dataset(dataset_id, current_user_id)

    # Check if feature selection results are stored in metadata
    selected_features = dataset.metadata.get("selected_features", []) if hasattr(dataset, "metadata") else []

    return SelectedFeaturesResponse(
        dataset_id=dataset_id,
        selected_features=selected_features,
        has_selection=len(selected_features) > 0
    )
