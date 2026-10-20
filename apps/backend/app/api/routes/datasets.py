"""
Dataset API routes.

Provides endpoints for managing datasets using DatasetService.
Implements Story 12.1: API Integration for New Models (Dataset portion).
"""

import logging
import uuid

from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)

from app.auth.nextauth_auth import get_current_user_id
from app.billing.enforcement import quota
from app.billing.storage import enforce_storage_ceiling
from app.models.dataset import DatasetMetadata, PIIReport
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
from app.services.data_processing.data_processor import (
    DataProcessor,
    EmptyFileError,
    ProcessedData,
    UnreadableFileError,
)
from app.services.dataset_service import DatasetService
from app.services.erasure_service import dataset_erasure_service
from app.services.security.pii_detector import PIIDetector
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


def _scanned_for_pii(processed: ProcessedData) -> PIIReport:
    """The upload's PII report, from the same detector `/upload/secure` runs (#1124).

    High risk (matching values) is refused with a 400 before the S3 put: this route has
    no confirmation gate, and `/upload/secure` + `/confirm-pii-upload` is the only way to
    store such a file. A name-only match (medium) is stored with its report.
    """
    detector = PIIDetector()
    report = detector.generate_pii_report(detector.detect_pii_in_dataframe(processed.dataframe))
    if report["risk_level"] == "high":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The file contains high-risk personal data. Upload it through "
            "/upload/secure, which asks you to confirm before it is stored.",
        )
    return PIIReport(
        contains_pii=report["has_pii"],
        pii_fields=[d["column"] for d in report.get("detections", [])],
        risk_level=report["risk_level"],
        detection_details=report,
    )


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
        pii_report = _scanned_for_pii(processed_data)
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
            quality_report=processed_data.quality_report.model_dump(),
            pii_report=pii_report,
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
            file_type=dataset.file_type,
            pii_report=pii_report.detection_details,
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
