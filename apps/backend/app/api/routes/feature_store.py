"""
Feature Store API routes.

Provides REST endpoints for managing features, versions, and collections.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.auth.nextauth_auth import get_current_user_id
from app.services.exceptions import (
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.services.feature_store_service import FeatureStoreService

router = APIRouter()


# ============================================================================
# Pydantic Schemas
# ============================================================================

class FeatureCreateRequest(BaseModel):
    """Request schema for creating a feature."""
    name: str = Field(..., description="Feature name")
    description: str = Field(..., description="Feature description")
    category: str = Field(..., description="Feature category")
    tags: list[str] = Field(default_factory=list, description="Feature tags")
    definition_type: str = Field(..., description="transformation, aggregation, encoding, or custom")
    definition_code: str = Field(..., description="Feature definition code")
    input_requirements: dict[str, str] = Field(..., description="Required input columns and types")
    output_type: str = Field(..., description="Output data type")
    output_column_name: str = Field(..., description="Name of output column")
    is_public: bool = Field(default=False, description="Whether feature is public")


class FeatureUpdateRequest(BaseModel):
    """Request schema for updating a feature."""
    name: str | None = None
    description: str | None = None
    category: str | None = None
    tags: list[str] | None = None
    definition_code: str | None = None
    definition_type: str | None = None
    input_requirements: dict[str, str] | None = None
    output_type: str | None = None
    output_column_name: str | None = None
    changes_description: str | None = None


class FeatureResponse(BaseModel):
    """Response schema for feature data."""
    feature_id: str
    name: str
    description: str
    category: str
    tags: list[str]
    definition_type: str
    output_type: str
    output_column_name: str
    version: int
    is_public: bool
    usage_count: int
    created_at: str
    updated_at: str


class FeatureListResponse(BaseModel):
    """Response schema for paginated feature list."""
    items: list[FeatureResponse]
    total: int
    skip: int
    limit: int


class ApplyFeatureRequest(BaseModel):
    """Request schema for applying a feature."""
    dataset_id: str = Field(..., description="Dataset to apply feature to")


class ApplyFeatureResponse(BaseModel):
    """Response schema for feature application result."""
    success: bool
    feature_id: str
    dataset_id: str
    output_column: str
    message: str


class CompatibilityResponse(BaseModel):
    """Response schema for compatibility check."""
    is_compatible: bool
    missing_columns: list[str]
    type_mismatches: dict[str, dict[str, str]]
    suggestions: list[str]


class ShareFeatureRequest(BaseModel):
    """Request schema for sharing a feature."""
    user_ids: list[str] = Field(..., description="User IDs to share with")


class CollectionCreateRequest(BaseModel):
    """Request schema for creating a collection."""
    name: str
    description: str
    domain: str
    feature_ids: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    is_public: bool = Field(default=False)


class CollectionResponse(BaseModel):
    """Response schema for collection data."""
    collection_id: str
    name: str
    description: str
    domain: str
    feature_count: int
    is_public: bool
    created_at: str


class AddFeatureToCollectionRequest(BaseModel):
    """Request schema for adding feature to collection."""
    feature_id: str


# ============================================================================
# Feature CRUD Endpoints
# ============================================================================

@router.post("/features", response_model=FeatureResponse, status_code=status.HTTP_201_CREATED)
async def create_feature(
    feature_data: FeatureCreateRequest,
    user_id: str = Depends(get_current_user_id)
):
    """
    Create a new feature in the feature store.

    Creates both the feature definition and initial version (v1).
    """
    service = FeatureStoreService()
    try:
        feature = await service.save_feature(feature_data.model_dump(), user_id)
        return FeatureResponse(
            feature_id=feature.feature_id,
            name=feature.name,
            description=feature.description,
            category=feature.category,
            tags=feature.tags,
            definition_type=feature.definition_type,
            output_type=feature.output_type,
            output_column_name=feature.output_column_name,
            version=feature.version,
            is_public=feature.is_public,
            usage_count=feature.usage_count,
            created_at=feature.created_at.isoformat(),
            updated_at=feature.updated_at.isoformat()
        )
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.get("/features", response_model=FeatureListResponse)
async def list_features(
    q: str | None = Query(None, description="Search query"),
    category: str | None = Query(None, description="Filter by category"),
    tags: str | None = Query(None, description="Filter by tags (comma-separated)"),
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(20, ge=1, le=100, description="Number of items to return"),
    user_id: str = Depends(get_current_user_id)
):
    """
    List and search features.

    Returns features owned by user, shared with user, or public features.
    Supports text search and filtering by category/tags.
    """
    service = FeatureStoreService()

    filters: dict[str, Any] = {}
    if category:
        filters["category"] = category
    if tags:
        filters["tags"] = tags.split(",")

    result = await service.search_features(
        user_id=user_id,
        query=q,
        filters=filters,
        skip=skip,
        limit=limit
    )

    features = [
        FeatureResponse(
            feature_id=f.feature_id,
            name=f.name,
            description=f.description,
            category=f.category,
            tags=f.tags,
            definition_type=f.definition_type,
            output_type=f.output_type,
            output_column_name=f.output_column_name,
            version=f.version,
            is_public=f.is_public,
            usage_count=f.usage_count,
            created_at=f.created_at.isoformat(),
            updated_at=f.updated_at.isoformat()
        )
        for f in result["items"]
    ]

    return FeatureListResponse(
        items=features,
        total=result["total"],
        skip=skip,
        limit=limit
    )


@router.get("/features/{feature_id}", response_model=FeatureResponse)
async def get_feature(
    feature_id: str,
    version: int | None = Query(None, description="Specific version to retrieve"),
    user_id: str = Depends(get_current_user_id)
):
    """
    Get feature by ID.

    Optionally retrieve a specific version of the feature.
    """
    service = FeatureStoreService()
    try:
        feature = await service.get_feature(feature_id, user_id, version=version)
        return FeatureResponse(
            feature_id=feature.feature_id,
            name=feature.name,
            description=feature.description,
            category=feature.category,
            tags=feature.tags,
            definition_type=feature.definition_type,
            output_type=feature.output_type,
            output_column_name=feature.output_column_name,
            version=feature.version,
            is_public=feature.is_public,
            usage_count=feature.usage_count,
            created_at=feature.created_at.isoformat(),
            updated_at=feature.updated_at.isoformat()
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.put("/features/{feature_id}", response_model=FeatureResponse)
async def update_feature(
    feature_id: str,
    updates: FeatureUpdateRequest,
    user_id: str = Depends(get_current_user_id)
):
    """
    Update feature.

    If definition fields are updated, creates a new version automatically.
    """
    service = FeatureStoreService()
    try:
        # Filter out None values
        update_dict = {k: v for k, v in updates.model_dump().items() if v is not None}

        feature = await service.update_feature(feature_id, user_id, update_dict)
        return FeatureResponse(
            feature_id=feature.feature_id,
            name=feature.name,
            description=feature.description,
            category=feature.category,
            tags=feature.tags,
            definition_type=feature.definition_type,
            output_type=feature.output_type,
            output_column_name=feature.output_column_name,
            version=feature.version,
            is_public=feature.is_public,
            usage_count=feature.usage_count,
            created_at=feature.created_at.isoformat(),
            updated_at=feature.updated_at.isoformat()
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.delete("/features/{feature_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_feature(
    feature_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """Delete feature (soft delete)."""
    service = FeatureStoreService()
    try:
        await service.delete_feature(feature_id, user_id, soft_delete=True)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


# ============================================================================
# Feature Application Endpoints
# ============================================================================

@router.post("/features/{feature_id}/apply", response_model=ApplyFeatureResponse)
async def apply_feature(
    feature_id: str,
    request: ApplyFeatureRequest,
    user_id: str = Depends(get_current_user_id)
):
    """
    Apply feature to a dataset.

    Checks compatibility first, then applies the feature transformation.
    """
    service = FeatureStoreService()
    try:
        result = await service.apply_feature(feature_id, request.dataset_id, user_id)
        return ApplyFeatureResponse(**result)
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.get("/features/{feature_id}/compatibility/{dataset_id}", response_model=CompatibilityResponse)
async def check_compatibility(
    feature_id: str,
    dataset_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """
    Check if feature is compatible with dataset.

    Returns compatibility status, missing columns, type mismatches, and suggestions.
    """
    service = FeatureStoreService()
    try:
        result = await service.check_compatibility(feature_id, dataset_id, user_id)
        return CompatibilityResponse(**result)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


# ============================================================================
# Sharing and Collaboration Endpoints
# ============================================================================

@router.post("/features/{feature_id}/share", response_model=FeatureResponse)
async def share_feature(
    feature_id: str,
    request: ShareFeatureRequest,
    user_id: str = Depends(get_current_user_id)
):
    """Share feature with other users."""
    service = FeatureStoreService()
    try:
        feature = await service.share_feature(feature_id, user_id, request.user_ids)
        return FeatureResponse(
            feature_id=feature.feature_id,
            name=feature.name,
            description=feature.description,
            category=feature.category,
            tags=feature.tags,
            definition_type=feature.definition_type,
            output_type=feature.output_type,
            output_column_name=feature.output_column_name,
            version=feature.version,
            is_public=feature.is_public,
            usage_count=feature.usage_count,
            created_at=feature.created_at.isoformat(),
            updated_at=feature.updated_at.isoformat()
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.post("/features/{feature_id}/public", response_model=FeatureResponse)
async def make_feature_public(
    feature_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """Make feature publicly accessible."""
    service = FeatureStoreService()
    try:
        feature = await service.make_public(feature_id, user_id)
        return FeatureResponse(
            feature_id=feature.feature_id,
            name=feature.name,
            description=feature.description,
            category=feature.category,
            tags=feature.tags,
            definition_type=feature.definition_type,
            output_type=feature.output_type,
            output_column_name=feature.output_column_name,
            version=feature.version,
            is_public=feature.is_public,
            usage_count=feature.usage_count,
            created_at=feature.created_at.isoformat(),
            updated_at=feature.updated_at.isoformat()
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


# ============================================================================
# Collection Endpoints
# ============================================================================

@router.post("/collections", response_model=CollectionResponse, status_code=status.HTTP_201_CREATED)
async def create_collection(
    collection_data: CollectionCreateRequest,
    user_id: str = Depends(get_current_user_id)
):
    """Create a new feature collection."""
    service = FeatureStoreService()
    collection = await service.create_collection(collection_data.model_dump(), user_id)
    return CollectionResponse(
        collection_id=collection.collection_id,
        name=collection.name,
        description=collection.description,
        domain=collection.domain,
        feature_count=collection.feature_count,
        is_public=collection.is_public,
        created_at=collection.created_at.isoformat()
    )


@router.get("/collections/{collection_id}", response_model=CollectionResponse)
async def get_collection(
    collection_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """Get collection by ID."""
    service = FeatureStoreService()
    try:
        collection = await service.get_collection(collection_id, user_id)
        return CollectionResponse(
            collection_id=collection.collection_id,
            name=collection.name,
            description=collection.description,
            domain=collection.domain,
            feature_count=collection.feature_count,
            is_public=collection.is_public,
            created_at=collection.created_at.isoformat()
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.post("/collections/{collection_id}/features", response_model=CollectionResponse)
async def add_feature_to_collection(
    collection_id: str,
    request: AddFeatureToCollectionRequest,
    user_id: str = Depends(get_current_user_id)
):
    """Add a feature to a collection."""
    service = FeatureStoreService()
    try:
        collection = await service.add_to_collection(collection_id, request.feature_id, user_id)
        return CollectionResponse(
            collection_id=collection.collection_id,
            name=collection.name,
            description=collection.description,
            domain=collection.domain,
            feature_count=collection.feature_count,
            is_public=collection.is_public,
            created_at=collection.created_at.isoformat()
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
