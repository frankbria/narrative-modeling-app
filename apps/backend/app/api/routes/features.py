"""
Feature Builder API routes.

Provides endpoints for the Visual Feature Builder - creating, previewing,
validating, and managing feature definitions.
"""

import logging

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status

from app.auth.nextauth_auth import get_current_user_id
from app.models.feature import (
    ExpressionNode,
    NodeType,
    OutputType,
)
from app.schemas.feature import (
    ApplyFeatureRequest,
    ApplyFeatureResponse,
    AvailableFunctionsResponse,
    AvailableOperationsResponse,
    ExpressionNodeRequest,
    ExpressionNodeResponse,
    FeatureDefinitionCreate,
    FeatureDefinitionResponse,
    FeatureDefinitionUpdate,
    FeatureDeleteResponse,
    FeatureListResponse,
    FeaturePreviewRequest,
    FeaturePreviewResponse,
    FeatureStatisticsResponse,
    FeatureValidationDetailedResponse,
    FeatureValidationRequest,
    FunctionInfo,
    OperationInfo,
)
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


@router.post(
    "/datasets/{dataset_id}/features/preview",
    response_model=FeaturePreviewResponse,
    summary="Preview feature computation",
    description="Preview the result of a feature expression on sample data."
)
async def preview_feature(
    dataset_id: str = Path(..., description="Dataset identifier"),
    request: FeaturePreviewRequest = Body(...),
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Preview a feature computation on sample data.

    This endpoint:
    1. Loads a sample of rows from the dataset
    2. Evaluates the expression tree safely (no eval())
    3. Returns sample values, statistics, and distribution

    Use this to test your expression before saving.
    """
    try:
        logger.info(f"Previewing feature for dataset {dataset_id}")

        # Convert expression tree
        expression_tree = _expression_node_to_model(request.expression_tree)

        result = await feature_builder_service.preview_feature(
            dataset_id=dataset_id,
            user_id=current_user_id,
            expression_tree=expression_tree,
            sample_size=request.sample_size
        )

        # Convert statistics if present
        stats_response = None
        if result.get("statistics"):
            stats = result["statistics"]
            stats_response = FeatureStatisticsResponse(
                mean=stats.get("mean"),
                median=stats.get("median"),
                std=stats.get("std"),
                min=stats.get("min"),
                max=stats.get("max"),
                null_count=stats.get("null_count", 0),
                unique_count=stats.get("unique_count", 0),
                total_count=stats.get("total_count", 0)
            )

        return FeaturePreviewResponse(
            success=result["success"],
            values=result.get("values", []),
            statistics=stats_response,
            distribution=result.get("distribution", []),
            formula=result.get("formula"),
            input_columns=result.get("input_columns", []),
            inferred_type=result.get("inferred_type", "unknown"),
            sample_data=result.get("sample_data"),
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
    except Exception as e:
        logger.exception(f"Error previewing feature: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error previewing feature: {str(e)}"
        )


@router.post(
    "/datasets/{dataset_id}/features/validate",
    response_model=FeatureValidationDetailedResponse,
    summary="Validate feature expression",
    description="Validate an expression tree without computing values."
)
async def validate_feature(
    dataset_id: str = Path(..., description="Dataset identifier"),
    request: FeatureValidationRequest = Body(...),
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Validate a feature expression without full evaluation.

    Checks:
    - Columns exist in the dataset
    - Type compatibility for operations
    - Complete expression tree structure
    - Potential runtime issues (division by zero, log of negatives)
    """
    try:
        logger.info(f"Validating feature expression for dataset {dataset_id}")

        # Convert expression tree
        expression_tree = _expression_node_to_model(request.expression_tree)

        result = await feature_builder_service.validate_expression(
            dataset_id=dataset_id,
            user_id=current_user_id,
            expression_tree=expression_tree
        )

        return FeatureValidationDetailedResponse(
            is_valid=result["is_valid"],
            errors=result["errors"],
            warnings=result["warnings"],
            inferred_type=result.get("inferred_type"),
            input_columns=result.get("input_columns", []),
            column_types=result.get("column_types", {}),
            type_compatibility=result.get("type_compatibility", {}),
            potential_issues=result.get("potential_issues", [])
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
        logger.exception(f"Error validating feature: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error validating feature: {str(e)}"
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


@router.get(
    "/datasets/{dataset_id}/features/{feature_id}",
    response_model=FeatureDefinitionResponse,
    summary="Get a specific feature",
    description="Get detailed information about a specific feature definition."
)
async def get_feature(
    dataset_id: str = Path(..., description="Dataset identifier"),
    feature_id: str = Path(..., description="Feature identifier"),
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Get a specific feature definition by ID.
    """
    try:
        logger.info(f"Getting feature {feature_id}")

        feature = await feature_builder_service.get_feature(
            feature_id=feature_id,
            user_id=current_user_id
        )

        # Verify feature belongs to requested dataset
        if feature.dataset_id != dataset_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Feature {feature_id} not found in dataset {dataset_id}"
            )

        return _feature_to_response(feature)

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
        logger.exception(f"Error getting feature: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting feature: {str(e)}"
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
async def apply_feature(
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

        result = await feature_builder_service.apply_feature_to_dataset(
            feature_id=feature_id,
            user_id=current_user_id,
            output_column_name=request.output_column_name,
            create_new_dataset=request.create_new_dataset
        )

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


@router.get(
    "/feature-builder/operations",
    response_model=AvailableOperationsResponse,
    summary="Get available operations",
    description="Get list of all available operations for the feature builder."
)
async def get_available_operations(
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Get all available operations for the feature builder.

    Returns operations grouped by category (arithmetic, comparison, logical).
    """
    operations = [
        # Arithmetic
        OperationInfo(type="add", symbol="+", label="Add", description="Add two values", category="arithmetic", num_operands=2, input_types=["numeric"], output_type="numeric"),
        OperationInfo(type="subtract", symbol="-", label="Subtract", description="Subtract right from left", category="arithmetic", num_operands=2, input_types=["numeric"], output_type="numeric"),
        OperationInfo(type="multiply", symbol="*", label="Multiply", description="Multiply two values", category="arithmetic", num_operands=2, input_types=["numeric"], output_type="numeric"),
        OperationInfo(type="divide", symbol="/", label="Divide", description="Divide left by right", category="arithmetic", num_operands=2, input_types=["numeric"], output_type="numeric"),
        OperationInfo(type="modulo", symbol="%", label="Modulo", description="Remainder of division", category="arithmetic", num_operands=2, input_types=["numeric"], output_type="numeric"),
        OperationInfo(type="power", symbol="**", label="Power", description="Raise to power", category="arithmetic", num_operands=2, input_types=["numeric"], output_type="numeric"),
        # Comparison
        OperationInfo(type="equal", symbol="==", label="Equal", description="Check equality", category="comparison", num_operands=2, input_types=["any"], output_type="boolean"),
        OperationInfo(type="not_equal", symbol="!=", label="Not Equal", description="Check inequality", category="comparison", num_operands=2, input_types=["any"], output_type="boolean"),
        OperationInfo(type="greater_than", symbol=">", label="Greater Than", description="Check if left > right", category="comparison", num_operands=2, input_types=["numeric"], output_type="boolean"),
        OperationInfo(type="less_than", symbol="<", label="Less Than", description="Check if left < right", category="comparison", num_operands=2, input_types=["numeric"], output_type="boolean"),
        OperationInfo(type="greater_than_or_equal", symbol=">=", label="Greater or Equal", description="Check if left >= right", category="comparison", num_operands=2, input_types=["numeric"], output_type="boolean"),
        OperationInfo(type="less_than_or_equal", symbol="<=", label="Less or Equal", description="Check if left <= right", category="comparison", num_operands=2, input_types=["numeric"], output_type="boolean"),
        # Logical
        OperationInfo(type="and", symbol="AND", label="And", description="Logical AND", category="logical", num_operands=2, input_types=["boolean"], output_type="boolean"),
        OperationInfo(type="or", symbol="OR", label="Or", description="Logical OR", category="logical", num_operands=2, input_types=["boolean"], output_type="boolean"),
        OperationInfo(type="not", symbol="NOT", label="Not", description="Logical NOT", category="logical", num_operands=1, input_types=["boolean"], output_type="boolean"),
    ]

    by_category = {}
    for op in operations:
        if op.category not in by_category:
            by_category[op.category] = []
        by_category[op.category].append(op)

    return AvailableOperationsResponse(
        operations=operations,
        by_category=by_category
    )


@router.get(
    "/feature-builder/functions",
    response_model=AvailableFunctionsResponse,
    summary="Get available functions",
    description="Get list of all available functions for the feature builder."
)
async def get_available_functions(
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Get all available functions for the feature builder.

    Returns functions grouped by category (mathematical, statistical, string, date).
    """
    functions = [
        # Mathematical
        FunctionInfo(type="abs", label="Absolute Value", signature="abs(x)", description="Absolute value", category="mathematical", num_args=1, input_types=["numeric"], output_type="numeric"),
        FunctionInfo(type="log", label="Natural Log", signature="log(x)", description="Natural logarithm (ln)", category="mathematical", num_args=1, input_types=["numeric"], output_type="numeric"),
        FunctionInfo(type="log10", label="Log Base 10", signature="log10(x)", description="Base-10 logarithm", category="mathematical", num_args=1, input_types=["numeric"], output_type="numeric"),
        FunctionInfo(type="sqrt", label="Square Root", signature="sqrt(x)", description="Square root", category="mathematical", num_args=1, input_types=["numeric"], output_type="numeric"),
        FunctionInfo(type="exp", label="Exponential", signature="exp(x)", description="e raised to power x", category="mathematical", num_args=1, input_types=["numeric"], output_type="numeric"),
        FunctionInfo(type="round", label="Round", signature="round(x, decimals=0)", description="Round to decimal places", category="mathematical", num_args=1, parameters=[{"name": "decimals", "type": "integer", "default": 0}], input_types=["numeric"], output_type="numeric"),
        FunctionInfo(type="ceil", label="Ceiling", signature="ceil(x)", description="Round up to nearest integer", category="mathematical", num_args=1, input_types=["numeric"], output_type="numeric"),
        FunctionInfo(type="floor", label="Floor", signature="floor(x)", description="Round down to nearest integer", category="mathematical", num_args=1, input_types=["numeric"], output_type="numeric"),
        FunctionInfo(type="sin", label="Sine", signature="sin(x)", description="Sine (radians)", category="mathematical", num_args=1, input_types=["numeric"], output_type="numeric"),
        FunctionInfo(type="cos", label="Cosine", signature="cos(x)", description="Cosine (radians)", category="mathematical", num_args=1, input_types=["numeric"], output_type="numeric"),
        FunctionInfo(type="tan", label="Tangent", signature="tan(x)", description="Tangent (radians)", category="mathematical", num_args=1, input_types=["numeric"], output_type="numeric"),
        # Statistical
        FunctionInfo(type="mean", label="Mean", signature="mean(x)", description="Mean value of column", category="statistical", num_args=1, input_types=["numeric"], output_type="numeric"),
        FunctionInfo(type="median", label="Median", signature="median(x)", description="Median value of column", category="statistical", num_args=1, input_types=["numeric"], output_type="numeric"),
        FunctionInfo(type="std", label="Standard Deviation", signature="std(x)", description="Standard deviation", category="statistical", num_args=1, input_types=["numeric"], output_type="numeric"),
        FunctionInfo(type="min", label="Minimum", signature="min(x)", description="Minimum value", category="statistical", num_args=1, input_types=["numeric"], output_type="numeric"),
        FunctionInfo(type="max", label="Maximum", signature="max(x)", description="Maximum value", category="statistical", num_args=1, input_types=["numeric"], output_type="numeric"),
        FunctionInfo(type="sum", label="Sum", signature="sum(x)", description="Sum of values", category="statistical", num_args=1, input_types=["numeric"], output_type="numeric"),
        # String
        FunctionInfo(type="upper", label="Uppercase", signature="upper(x)", description="Convert to uppercase", category="string", num_args=1, input_types=["string"], output_type="string"),
        FunctionInfo(type="lower", label="Lowercase", signature="lower(x)", description="Convert to lowercase", category="string", num_args=1, input_types=["string"], output_type="string"),
        FunctionInfo(type="trim", label="Trim", signature="trim(x)", description="Remove leading/trailing whitespace", category="string", num_args=1, input_types=["string"], output_type="string"),
        FunctionInfo(type="length", label="Length", signature="length(x)", description="String length", category="string", num_args=1, input_types=["string"], output_type="numeric"),
        # Date
        FunctionInfo(type="year", label="Year", signature="year(x)", description="Extract year", category="date", num_args=1, input_types=["datetime"], output_type="numeric"),
        FunctionInfo(type="month", label="Month", signature="month(x)", description="Extract month (1-12)", category="date", num_args=1, input_types=["datetime"], output_type="numeric"),
        FunctionInfo(type="day", label="Day", signature="day(x)", description="Extract day of month", category="date", num_args=1, input_types=["datetime"], output_type="numeric"),
        FunctionInfo(type="hour", label="Hour", signature="hour(x)", description="Extract hour", category="date", num_args=1, input_types=["datetime"], output_type="numeric"),
        FunctionInfo(type="minute", label="Minute", signature="minute(x)", description="Extract minute", category="date", num_args=1, input_types=["datetime"], output_type="numeric"),
        FunctionInfo(type="weekday", label="Weekday", signature="weekday(x)", description="Day of week (0=Monday)", category="date", num_args=1, input_types=["datetime"], output_type="numeric"),
        # Utility
        FunctionInfo(type="to_numeric", label="To Numeric", signature="to_numeric(x)", description="Convert to numeric", category="utility", num_args=1, input_types=["any"], output_type="numeric"),
        FunctionInfo(type="to_string", label="To String", signature="to_string(x)", description="Convert to string", category="utility", num_args=1, input_types=["any"], output_type="string"),
        FunctionInfo(type="fill_null", label="Fill Null", signature="fill_null(x, value)", description="Replace null values", category="utility", num_args=2, input_types=["any"], output_type="any"),
        FunctionInfo(type="is_null", label="Is Null", signature="is_null(x)", description="Check if null", category="utility", num_args=1, input_types=["any"], output_type="boolean"),
    ]

    by_category = {}
    for func in functions:
        if func.category not in by_category:
            by_category[func.category] = []
        by_category[func.category].append(func)

    return AvailableFunctionsResponse(
        functions=functions,
        by_category=by_category
    )
