"""
Data Versioning API routes.

Provides endpoints for managing dataset versions and transformation lineage.
Implements Story 12.2: Data Versioning API.
"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional
import logging

from app.schemas.version import (
    DatasetVersionResponse,
    DatasetVersionCreate,
    LineageResponse,
    VersionComparisonRequest,
    VersionComparisonResponse,
    VersionListResponse,
    VersionPinRequest,
    TransformationStepResponse
)
from app.models.version import DatasetVersion, TransformationLineage
from app.models.dataset import DatasetMetadata
from app.services.versioning_service import versioning_service
from app.auth.nextauth_auth import get_current_user_id

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/datasets/{dataset_id}/versions", response_model=VersionListResponse)
async def list_dataset_versions(
    dataset_id: str,
    limit: int = 50,
    skip: int = 0,
    user_id: Optional[str] = None,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    List all versions for a dataset.

    Returns versions sorted by version_number (descending).
    Supports pagination via limit and skip parameters.
    """
    try:
        logger.info(f"Listing versions for dataset {dataset_id}")

        # Get versions from service
        versions = await versioning_service.list_versions(
            dataset_id=dataset_id,
            user_id=user_id,
            limit=limit,
            skip=skip
        )

        # Get total count
        total_count = await DatasetVersion.find(
            DatasetVersion.dataset_id == dataset_id
        ).count()

        # Convert to response models
        version_responses = [
            DatasetVersionResponse.model_validate(v)
            for v in versions
        ]

        return VersionListResponse(
            versions=version_responses,
            total=total_count,
            limit=limit,
            skip=skip,
            dataset_id=dataset_id
        )

    except Exception as e:
        logger.error(f"Error listing versions for dataset {dataset_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing versions: {str(e)}"
        )


@router.post("/datasets/{dataset_id}/versions", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_dataset_version(
    dataset_id: str,
    version_data: DatasetVersionCreate,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Create a new version for a dataset.

    This endpoint requires the transformed dataset content to be uploaded
    separately and referenced via file_path or s3_url.
    """
    try:
        logger.info(f"Creating new version for dataset {dataset_id}")

        # Get dataset metadata
        dataset_metadata = await DatasetMetadata.find_one(
            DatasetMetadata.dataset_id == dataset_id
        )
        if not dataset_metadata:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dataset {dataset_id} not found"
            )

        # Get the latest version to use as parent
        latest_version = await DatasetVersion.find(
            DatasetVersion.dataset_id == dataset_id
        ).sort(-DatasetVersion.version_number).first_or_none()

        if not latest_version:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No base version exists for this dataset. Upload dataset first."
            )

        # For now, we'll create a version by copying the latest version's content
        # In a real implementation, you'd get the actual transformed content
        version_content = await versioning_service.get_version_content(latest_version.version_id)

        # Create transformation version
        new_version, lineage = await versioning_service.create_transformation_version(
            parent_version_id=latest_version.version_id,
            transformed_content=version_content,
            transformation_steps=version_data.transformation_steps,
            dataset_metadata=dataset_metadata,
            user_id=current_user_id,
            description=version_data.description,
            transformation_config_id=version_data.transformation_config_id
        )

        # Update tags if provided
        if version_data.tags:
            new_version.tags = version_data.tags
            await new_version.save()

        # Convert to response models
        version_response = DatasetVersionResponse.model_validate(new_version)
        lineage_response = LineageResponse.model_validate(lineage)

        logger.info(f"Created version {new_version.version_id} for dataset {dataset_id}")

        return {
            "version": version_response.model_dump(),
            "lineage": lineage_response.model_dump()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating version for dataset {dataset_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating version: {str(e)}"
        )


@router.get("/versions/{version_id}", response_model=DatasetVersionResponse)
async def get_version(
    version_id: str,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Retrieve a specific dataset version by ID.

    Increments the access counter for the version.
    """
    try:
        logger.info(f"Retrieving version {version_id}")

        # Get version with access tracking
        version = await versioning_service.get_version(version_id, mark_accessed=True)

        if not version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Version {version_id} not found"
            )

        return DatasetVersionResponse.model_validate(version)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving version {version_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving version: {str(e)}"
        )


@router.get("/versions/{version_id}/lineage", response_model=dict)
async def get_version_lineage(
    version_id: str,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Get transformation lineage chain for a version.

    Returns the complete lineage from base version to the specified version.
    """
    try:
        logger.info(f"Retrieving lineage for version {version_id}")

        # Check if version exists
        version = await DatasetVersion.find_one(
            DatasetVersion.version_id == version_id
        )
        if not version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Version {version_id} not found"
            )

        # Get lineage chain
        lineage_chain = await versioning_service.get_lineage_chain(version_id)

        # Convert to response models
        lineage_responses = [
            LineageResponse.model_validate(lineage)
            for lineage in lineage_chain
        ]

        return {
            "lineage_chain": [lr.model_dump() for lr in lineage_responses],
            "version_id": version_id,
            "total_transformations": len(lineage_chain)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving lineage for version {version_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving lineage: {str(e)}"
        )


@router.post("/versions/compare", response_model=VersionComparisonResponse)
async def compare_versions(
    comparison_request: VersionComparisonRequest,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Compare two dataset versions.

    Returns detailed comparison including row/column differences,
    schema changes, and transformation lineage path between versions.
    """
    try:
        logger.info(
            f"Comparing versions {comparison_request.version1_id} "
            f"and {comparison_request.version2_id}"
        )

        # Perform comparison using service
        comparison = await versioning_service.compare_versions(
            version1_id=comparison_request.version1_id,
            version2_id=comparison_request.version2_id
        )

        return VersionComparisonResponse.model_validate(comparison)

    except ValueError as e:
        # Handle specific validation errors from service
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        elif "same dataset" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
    except Exception as e:
        logger.error(f"Error comparing versions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error comparing versions: {str(e)}"
        )


@router.delete("/versions/{version_id}", response_model=dict)
async def delete_version(
    version_id: str,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Soft delete a dataset version.

    Cannot delete:
    - Base versions (first upload)
    - Pinned versions
    """
    try:
        logger.info(f"Deleting version {version_id}")

        # Get version
        version = await DatasetVersion.find_one(
            DatasetVersion.version_id == version_id
        )
        if not version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Version {version_id} not found"
            )

        # Check if base version
        if version.is_base_version:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete base version"
            )

        # Check if pinned
        if version.is_pinned:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete pinned version. Unpin first."
            )

        # Delete version
        await version.delete()

        logger.info(f"Deleted version {version_id}")

        return {"message": "Version deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting version {version_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting version: {str(e)}"
        )


@router.patch("/versions/{version_id}/pin", response_model=DatasetVersionResponse)
async def pin_version(
    version_id: str,
    pin_request: VersionPinRequest,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Pin or unpin a dataset version.

    Pinned versions are protected from automatic deletion.
    """
    try:
        logger.info(f"{'Pinning' if pin_request.pinned else 'Unpinning'} version {version_id}")

        # Pin or unpin version using service
        if pin_request.pinned:
            version = await versioning_service.pin_version(version_id)
        else:
            version = await versioning_service.unpin_version(version_id)

        return DatasetVersionResponse.model_validate(version)

    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
    except Exception as e:
        logger.error(f"Error pinning version {version_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error pinning version: {str(e)}"
        )
