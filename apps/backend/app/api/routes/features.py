"""
Feature Builder API routes.

Provides endpoints for the Visual Feature Builder - creating, previewing,
validating, and managing feature definitions.
"""

import logging

from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
    Path,
    Query,
    Request,
    status,
)

from app.auth.nextauth_auth import get_current_user_id
from app.billing.enforcement import release, reserve
from app.billing.storage import enforce_storage_ceiling
from app.middleware.upload_cleanup import discards_uploads_on_reported_failure
from app.models.feature import (
    ExpressionNode,
    NodeType,
    OutputType,
)
from app.schemas.feature import (
    ApplyFeatureRequest,
    ApplyFeatureResponse,
    ExpressionNodeRequest,
    ExpressionNodeResponse,
    FeatureDefinitionCreate,
    FeatureDefinitionResponse,
    FeatureDefinitionUpdate,
    FeatureDeleteResponse,
    FeatureListResponse,
    FeatureStatisticsResponse,
)
from app.services.dataset_link import DATASET_BUSY, holds_the_dataset
from app.services.exceptions import (
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.services.feature_builder_service import feature_builder_service

logger = logging.getLogger(__name__)

router = APIRouter()


def _expression_node_to_model(node_request: ExpressionNodeRequest) -> ExpressionNode:
    """Convert ExpressionNodeRequest to ExpressionNode model."""
    children = [_expression_node_to_model(child) for child in node_request.children]
    return ExpressionNode(
        node_id=node_request.node_id,
        node_type=NodeType(node_request.node_type),
        value=node_request.value,
        children=children,
        parameters=node_request.parameters,
        position=node_request.position
    )


def _expression_node_to_response(node: ExpressionNode) -> ExpressionNodeResponse:
    """Convert ExpressionNode model to response schema."""
    children = [_expression_node_to_response(child) for child in node.children]
    return ExpressionNodeResponse(
        node_id=node.node_id,
        node_type=node.node_type.value,
        value=node.value,
        children=children,
        parameters=node.parameters,
        position=node.position
    )


def _feature_to_response(feature) -> FeatureDefinitionResponse:
    """Convert FeatureDefinition model to response schema."""
    validation_response = None
    if feature.validation_result:
        validation_response = {
            "is_valid": feature.validation_result.is_valid,
            "errors": feature.validation_result.errors,
            "warnings": feature.validation_result.warnings,
            "inferred_type": feature.validation_result.inferred_type.value if feature.validation_result.inferred_type else None,
            "validated_at": feature.validation_result.validated_at
        }

    statistics_response = None
    if feature.statistics:
        statistics_response = FeatureStatisticsResponse(
            mean=feature.statistics.mean,
            median=feature.statistics.median,
            std=feature.statistics.std,
            min=feature.statistics.min_value,
            max=feature.statistics.max_value,
            null_count=feature.statistics.null_count,
            unique_count=feature.statistics.unique_count,
            total_count=feature.statistics.total_count
        )

    return FeatureDefinitionResponse(
        id=str(feature.id),
        feature_id=feature.feature_id,
        user_id=feature.user_id,
        dataset_id=feature.dataset_id,
        name=feature.name,
        description=feature.description,
        tags=feature.tags,
        expression_tree=_expression_node_to_response(feature.expression_tree),
        formula_string=feature.formula_string,
        input_columns=feature.input_columns,
        output_type=feature.output_type.value if isinstance(feature.output_type, OutputType) else feature.output_type,
        is_valid=feature.is_valid,
        validation_result=validation_response,
        statistics=statistics_response,
        canvas_state=feature.canvas_state,
        created_at=feature.created_at,
        updated_at=feature.updated_at,
        version=feature.version
    )


@router.post(
    "/datasets/{dataset_id}/features",
    response_model=FeatureDefinitionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new feature definition",
    description="Create a new feature definition for a dataset using a visual expression tree."
)
async def create_feature(
    dataset_id: str = Path(..., description="Dataset identifier"),
    request: FeatureDefinitionCreate = Body(...),
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Create a new feature definition for a dataset.

    The expression tree represents the feature formula as a tree of nodes:
    - column: References a dataset column
    - operation: Binary operations (+, -, *, /, etc.)
    - function: Mathematical/statistical functions (log, sqrt, mean, etc.)
    - constant: Constant values
    - conditional: If-then-else logic
    """
    try:
        logger.info(f"Creating feature '{request.name}' for dataset {dataset_id}")

        # Convert expression tree
        expression_tree = _expression_node_to_model(request.expression_tree)

        # Determine output type
        output_type = OutputType.NUMERIC
        if request.output_type:
            output_type = OutputType(request.output_type)

        feature = await feature_builder_service.create_feature(
            user_id=current_user_id,
            dataset_id=dataset_id,
            name=request.name,
            expression_tree=expression_tree,
            description=request.description,
            tags=request.tags,
            output_type=output_type,
            canvas_state=request.canvas_state
        )

        logger.info(f"Feature {feature.feature_id} created successfully")
        return _feature_to_response(feature)

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except PermissionDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.exception(f"Error creating feature: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating feature: {str(e)}"
        )


@router.get(
    "/datasets/{dataset_id}/features",
    response_model=FeatureListResponse,
    summary="List features for a dataset",
    description="Get all feature definitions for a specific dataset."
)
async def list_features(
    dataset_id: str = Path(..., description="Dataset identifier"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user_id: str = Depends(get_current_user_id)
):
    """
    List all feature definitions for a dataset.

    Returns features sorted by created_at (newest first).
    """
    try:
        logger.info(f"Listing features for dataset {dataset_id}")

        skip = (page - 1) * limit

        features, total = await feature_builder_service.list_features(
            dataset_id=dataset_id,
            user_id=current_user_id,
            skip=skip,
            limit=limit
        )

        feature_responses = [_feature_to_response(f) for f in features]

        return FeatureListResponse(
            features=feature_responses,
            total=total,
            page=page,
            per_page=limit
        )

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except PermissionDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.exception(f"Error listing features: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing features: {str(e)}"
        )


@router.put(
    "/datasets/{dataset_id}/features/{feature_id}",
    response_model=FeatureDefinitionResponse,
    summary="Update a feature definition",
    description="Update an existing feature definition."
)
async def update_feature(
    dataset_id: str = Path(..., description="Dataset identifier"),
    feature_id: str = Path(..., description="Feature identifier"),
    request: FeatureDefinitionUpdate = Body(...),
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Update a feature definition.

    Can update name, description, tags, expression tree, output type, or canvas state.
    """
    try:
        logger.info(f"Updating feature {feature_id}")

        # Convert expression tree if provided
        expression_tree = None
        if request.expression_tree:
            expression_tree = _expression_node_to_model(request.expression_tree)

        # Convert output type if provided
        output_type = None
        if request.output_type:
            output_type = OutputType(request.output_type)

        feature = await feature_builder_service.update_feature(
            feature_id=feature_id,
            user_id=current_user_id,
            name=request.name,
            description=request.description,
            tags=request.tags,
            expression_tree=expression_tree,
            output_type=output_type,
            canvas_state=request.canvas_state
        )

        # Verify feature belongs to requested dataset
        if feature.dataset_id != dataset_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Feature {feature_id} not found in dataset {dataset_id}"
            )

        logger.info(f"Feature {feature_id} updated successfully")
        return _feature_to_response(feature)

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except PermissionDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error updating feature: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating feature: {str(e)}"
        )


@router.delete(
    "/datasets/{dataset_id}/features/{feature_id}",
    response_model=FeatureDeleteResponse,
    summary="Delete a feature definition",
    description="Delete a feature definition."
)
async def delete_feature(
    dataset_id: str = Path(..., description="Dataset identifier"),
    feature_id: str = Path(..., description="Feature identifier"),
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Delete a feature definition.
    """
    try:
        logger.info(f"Deleting feature {feature_id}")

        # First get the feature to verify dataset ownership
        feature = await feature_builder_service.get_feature(
            feature_id=feature_id,
            user_id=current_user_id
        )

        if feature.dataset_id != dataset_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Feature {feature_id} not found in dataset {dataset_id}"
            )

        success = await feature_builder_service.delete_feature(
            feature_id=feature_id,
            user_id=current_user_id
        )

        if success:
            logger.info(f"Feature {feature_id} deleted successfully")
            return FeatureDeleteResponse(
                status="success",
                feature_id=feature_id,
                message=f"Feature {feature_id} deleted successfully"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete feature"
            )

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except PermissionDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error deleting feature: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting feature: {str(e)}"
        )


@router.post(
    "/datasets/{dataset_id}/features/{feature_id}/apply",
    response_model=ApplyFeatureResponse,
    summary="Apply feature to dataset",
    description="Compute the feature and add it as a new column to the dataset."
)
@discards_uploads_on_reported_failure
@holds_the_dataset(
    lambda kw: kw["dataset_id"],
    lambda kw: ApplyFeatureResponse(
        success=False, dataset_id=kw["dataset_id"], column_name=kw["request"].output_column_name or "",
        rows_computed=0, error=DATASET_BUSY,
    ),
)
async def apply_feature(
    http_request: Request,
    dataset_id: str = Path(..., description="Dataset identifier"),
    feature_id: str = Path(..., description="Feature identifier"),
    request: ApplyFeatureRequest = Body(...),
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Apply a feature to the dataset, adding the computed column.
    """
    try:
        logger.info(f"Applying feature {feature_id} to dataset {dataset_id}")

        # Verify feature exists and belongs to this dataset
        feature = await feature_builder_service.get_feature(
            feature_id=feature_id,
            user_id=current_user_id
        )

        if feature.dataset_id != dataset_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Feature {feature_id} not found in dataset {dataset_id}"
            )

        # Charged only on the branch that creates one. `create_new_dataset` reaches the
        # same `DatasetService.create_dataset` as `/datasets/upload`, so leaving it
        # unmetered lets a tenant at their cap mint datasets here instead (#459). A
        # route dependency would be wrong in the other direction: the flag defaults to
        # false, and an in-place apply adds a column to a dataset already paid for.
        #
        # Inside the `try` is safe here only because this handler has an
        # `except HTTPException: raise` — without it the module's broad `except`
        # would turn the 402 into a 500 (the #453 trap).
        if request.create_new_dataset:
            await reserve(http_request, current_user_id, "uploads")
            # The derived dataset's size is only known once it is written, so this
            # refuses a tenant with no room left (#768).
            # ponytail: may overshoot by one derived dataset; its real size is
            # recorded, so the next upload sees it.
            await enforce_storage_ceiling(current_user_id, 1)

        result = await feature_builder_service.apply_feature_to_dataset(
            feature_id=feature_id,
            user_id=current_user_id,
            output_column_name=request.output_column_name,
            create_new_dataset=request.create_new_dataset
        )

        # `apply_feature_to_dataset` reports failure by RETURNING, not raising — both
        # its S3-upload path and its catch-all `return {"success": False, ...}` — and
        # this route answers 200 carrying that flag. The refund middleware only sees
        # >= 400, so without this the unit reserved above is kept for a dataset that
        # was never created: a tenant on their last upload burns it, receives nothing,
        # and is 402'd until the period rolls. Same shape as `/upload/secure`'s PII
        # branch, which is what `release()` exists for.
        # Keyed on `dataset_committed`, NOT on `success`. The two differ in a window
        # that matters: the service's catch-all wraps `create_dataset()` *and* the
        # `feature.save()` after it, so a raise in between returns `success: False`
        # with a real dataset already persisted in both id-spaces. Releasing on
        # `success` alone would hand that tenant a free dataset — the mirror of the
        # double-charge this issue set out to fix, and just as invisible.
        if request.create_new_dataset and not result.get("dataset_committed", False):
            await release(http_request)

        return ApplyFeatureResponse(
            success=result["success"],
            dataset_id=result["dataset_id"],
            column_name=result["column_name"],
            rows_computed=result["rows_computed"],
            null_values=result["null_values"],
            error=result.get("error"),
            warnings=result.get("warnings", [])
        )

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except PermissionDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error applying feature: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error applying feature: {str(e)}"
        )
