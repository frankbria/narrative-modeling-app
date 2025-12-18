"""
API routes for data transformation pipeline
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
import pandas as pd
from datetime import datetime
import logging
import time

from app.auth.nextauth_auth import get_current_user_id
from app.models.user_data import UserData
from app.schemas.transformation import (
    TransformationPreviewRequest,
    TransformationApplyRequest,
    TransformationPreviewResponse,
    TransformationApplyResponse,
    TransformationPipelineRequest,
    TransformationStepRequest,
    RecipeCreateRequest,
    RecipeResponse,
    RecipeListResponse,
    RecipeApplyRequest,
    RecipeExportRequest,
    RecipeExportResponse,
    TransformationHistoryResponse,
    AutoCleanRequest,
    TransformationSuggestionResponse,
    ValidationRequest,
    ValidationResponse,
    TransformationTypeInfo,
)
from app.services.transformation_engine.transformation_engine import (
    TransformationEngine,
    TransformationType as EngineTransformationType
)
from app.services.transformation_engine.validators import TransformationValidator
from app.services.transformation_engine.recipe_manager import RecipeManager
from app.services.transformation_engine.data_utils import get_dataframe_from_s3, upload_dataframe_to_s3
from app.services.redis_cache import cache_service
from app.services.exceptions import NotFoundError, OperationError

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/preview", response_model=TransformationPreviewResponse)
async def preview_transformation(
    request: TransformationPreviewRequest,
    current_user_id: str = Depends(get_current_user_id)
):
    """Preview a transformation on a subset of data using TransformationService"""
    try:
        # Extract transformation data from first step
        if not request.transformation_steps:
            raise HTTPException(status_code=400, detail="No transformation steps provided")

        first_step = request.transformation_steps[0]

        # Use TransformationService for preview
        from app.services.transformation_service import TransformationService
        service = TransformationService()

        result = await service.preview_transformation(
            dataset_id=request.dataset_id,
            transformation_type=first_step.transformation_type,
            parameters=first_step.parameters or {},
            preview_rows=request.preview_rows
        )

        return TransformationPreviewResponse(
            success=result["success"],
            preview_data=result["preview_data"],
            affected_rows=result["affected_rows"],
            affected_columns=result["affected_columns"],
            stats_before=result["stats_before"],
            stats_after=result["stats_after"],
            error=result.get("error"),
            warnings=result.get("warnings", [])
        )

    except NotFoundError as e:
        logger.error(f"Preview transformation failed: {str(e)}")
        raise HTTPException(status_code=404, detail=e.message)
    except OperationError as e:
        logger.error(f"Preview transformation failed: {str(e)}")
        return TransformationPreviewResponse(
            success=False,
            error=e.message
        )
    except Exception as e:
        logger.error(f"Preview transformation failed: {str(e)}")
        return TransformationPreviewResponse(
            success=False,
            error=str(e)
        )


@router.post("/apply", response_model=TransformationApplyResponse)
async def apply_transformation(
    request: TransformationApplyRequest,
    current_user_id: str = Depends(get_current_user_id)
):
    """Apply a transformation to the full dataset using TransformationService"""
    try:
        # Use TransformationService for apply
        from app.services.transformation_service import TransformationService
        service = TransformationService()

        result = await service.apply_transformation(
            user_id=current_user_id,
            dataset_id=request.dataset_id,
            transformation_type=request.transformation_type,
            parameters=request.parameters
        )

        return TransformationApplyResponse(
            success=result["success"],
            dataset_id=result["dataset_id"],
            transformation_id=result["transformation_id"],
            affected_rows=result.get("affected_rows", 0),
            affected_columns=result.get("affected_columns", []),
            execution_time_ms=result["execution_time_ms"],
            error=result.get("error"),
            warnings=result.get("warnings", [])
        )

    except NotFoundError as e:
        logger.error(f"Apply transformation failed: {str(e)}")
        raise HTTPException(status_code=404, detail=e.message)
    except OperationError as e:
        logger.error(f"Apply transformation failed: {str(e)}")
        return TransformationApplyResponse(
            success=False,
            dataset_id=request.dataset_id,
            transformation_id="",
            execution_time_ms=0,
            error=e.message
        )
    except Exception as e:
        logger.error(f"Apply transformation failed: {str(e)}")
        return TransformationApplyResponse(
            success=False,
            dataset_id=request.dataset_id,
            transformation_id="",
            execution_time_ms=0,
            error=str(e)
        )


@router.post("/pipeline/apply", response_model=TransformationApplyResponse)
async def apply_transformation_pipeline(
    request: TransformationPipelineRequest,
    current_user_id: str = Depends(get_current_user_id)
):
    """Apply multiple transformations in sequence"""
    try:
        start_time = time.time()
        
        # Get dataset
        user_data = await UserData.find_one({
            "user_id": current_user_id,
            "_id": request.dataset_id
        })
        
        if not user_data:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        # Load data from S3
        file_path = user_data.file_path or user_data.s3_url
        df = await get_dataframe_from_s3(file_path)
        
        # Create transformation engine
        engine = TransformationEngine()
        
        total_affected_rows = 0
        all_affected_columns = set()
        
        # Apply each transformation in sequence
        for step in request.transformations:
            result = engine.apply_transformation(
                df=df,
                transformation_type=EngineTransformationType(step.type),
                parameters=step.parameters
            )
            
            if not result.success:
                return TransformationApplyResponse(
                    success=False,
                    dataset_id=request.dataset_id,
                    transformation_id="",
                    execution_time_ms=int((time.time() - start_time) * 1000),
                    error=f"Transformation '{step.type}' failed: {result.error}"
                )
            
            df = pd.DataFrame(result.transformed_data)
            total_affected_rows += result.affected_rows
            all_affected_columns.update(result.affected_columns)
        
        # Save transformed data
        new_file_path = await upload_dataframe_to_s3(
            df,
            f"transformed/{current_user_id}/{request.dataset_id}_{datetime.utcnow().timestamp()}.parquet"
        )
        
        # Update user data
        user_data.file_path = new_file_path
        user_data.updated_at = datetime.utcnow()
        await user_data.save()
        
        # Save as recipe if requested
        if request.save_as_recipe and request.recipe_name:
            recipe = await RecipeManager.create_recipe(
                name=request.recipe_name,
                steps=[{
                    "type": step.type,
                    "parameters": step.parameters,
                    "description": step.description
                } for step in request.transformations],
                user_id=current_user_id,
                description=request.recipe_description,
                dataset_id=request.dataset_id,
                schema_snapshot={col: str(dtype) for col, dtype in df.dtypes.items()}
            )
        
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        return TransformationApplyResponse(
            success=True,
            dataset_id=request.dataset_id,
            transformation_id=f"pipeline_{datetime.utcnow().timestamp()}",
            affected_rows=total_affected_rows,
            affected_columns=list(all_affected_columns),
            execution_time_ms=execution_time_ms
        )
        
    except Exception as e:
        logger.error(f"Apply pipeline failed: {str(e)}")
        return TransformationApplyResponse(
            success=False,
            dataset_id=request.dataset_id,
            transformation_id="",
            execution_time_ms=0,
            error=str(e)
        )


@router.post("/validate", response_model=ValidationResponse)
async def validate_transformations(
    request: ValidationRequest,
    current_user_id: str = Depends(get_current_user_id)
):
    """Validate transformations before applying"""
    try:
        # Get dataset
        user_data = await UserData.find_one({
            "user_id": current_user_id,
            "_id": request.dataset_id
        })
        
        if not user_data:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        # Load data sample
        file_path = user_data.file_path or user_data.s3_url
        df = await get_dataframe_from_s3(file_path, nrows=1000)
        
        # Validate each transformation
        all_errors = []
        all_warnings = []
        all_info = []
        
        for step in request.transformations:
            if step.type == "remove_duplicates":
                result = TransformationValidator.validate_remove_duplicates(df, step.parameters)
            elif step.type == "fill_missing":
                result = TransformationValidator.validate_fill_missing(df, step.parameters)
            elif step.type == "trim_whitespace":
                result = TransformationValidator.validate_trim_whitespace(df, step.parameters)
            else:
                continue
            
            all_errors.extend(result.errors)
            all_warnings.extend(result.warnings)
            all_info.extend(result.info)
        
        # Get suggestions
        suggestions = TransformationValidator.suggest_transformations(df)
        
        return ValidationResponse(
            is_valid=len(all_errors) == 0,
            errors=all_errors,
            warnings=all_warnings,
            info=all_info,
            suggestions=suggestions
        )
        
    except Exception as e:
        logger.error(f"Validation failed: {str(e)}")
        return ValidationResponse(
            is_valid=False,
            errors=[str(e)]
        )


@router.post("/auto-clean", response_model=TransformationApplyResponse)
async def auto_clean_dataset(
    request: AutoCleanRequest,
    current_user_id: str = Depends(get_current_user_id)
):
    """Apply automatic data cleaning based on detected issues"""
    try:
        # Get dataset
        user_data = await UserData.find_one({
            "user_id": current_user_id,
            "_id": request.dataset_id
        })
        
        if not user_data:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        # Build transformation pipeline based on options
        transformations = []
        
        if request.options.get("remove_duplicates", True):
            transformations.append({
                "type": "remove_duplicates",
                "parameters": {"keep": "first"}
            })
        
        if request.options.get("trim_whitespace", True):
            transformations.append({
                "type": "trim_whitespace",
                "parameters": {"columns": []}  # Apply to all string columns
            })
        
        if request.options.get("handle_missing") == "drop":
            # For now, we'll skip dropping missing values as it's not implemented
            # TODO: Implement drop_missing transformation
            pass
        elif request.options.get("handle_missing") == "impute":
            transformations.append({
                "type": "fill_missing",
                "parameters": {"method": "mean"}  # Smart imputation based on column type
            })
        
        # Apply pipeline
        pipeline_request = TransformationPipelineRequest(
            dataset_id=request.dataset_id,
            transformations=[
                TransformationStepRequest(
                    type=t["type"],
                    parameters=t["parameters"]
                ) for t in transformations
            ]
        )
        
        return await apply_transformation_pipeline(pipeline_request, current_user_id)
        
    except Exception as e:
        logger.error(f"Auto-clean failed: {str(e)}")
        return TransformationApplyResponse(
            success=False,
            dataset_id=request.dataset_id,
            transformation_id="",
            execution_time_ms=0,
            error=str(e)
        )


@router.get("/suggestions/{dataset_id}", response_model=TransformationSuggestionResponse)
async def get_transformation_suggestions(
    dataset_id: str,
    current_user_id: str = Depends(get_current_user_id)
):
    """Get AI-powered transformation suggestions"""
    try:
        # Get dataset
        user_data = await UserData.find_one({
            "user_id": current_user_id,
            "_id": dataset_id
        })
        
        if not user_data:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        # Load data sample
        file_path = user_data.file_path or user_data.s3_url
        df = await get_dataframe_from_s3(file_path, nrows=1000)
        
        # Get suggestions
        suggestions = TransformationValidator.suggest_transformations(df)
        
        # Calculate data quality score
        missing_ratio = df.isnull().sum().sum() / (len(df) * len(df.columns))
        duplicate_ratio = df.duplicated().sum() / len(df)
        quality_score = max(0, 1 - (missing_ratio + duplicate_ratio))
        
        # Identify critical issues
        critical_issues = []
        if missing_ratio > 0.3:
            critical_issues.append(f"High missing data ratio: {missing_ratio:.1%}")
        if duplicate_ratio > 0.1:
            critical_issues.append(f"High duplicate ratio: {duplicate_ratio:.1%}")
        
        return TransformationSuggestionResponse(
            suggestions=[{"suggestion": s} for s in suggestions],
            data_quality_score=quality_score,
            critical_issues=critical_issues
        )
        
    except Exception as e:
        logger.error(f"Get suggestions failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Recipe Management Routes

@router.post("/recipes", response_model=RecipeResponse)
async def create_recipe(
    request: RecipeCreateRequest,
    current_user_id: str = Depends(get_current_user_id)
):
    """Create a new transformation recipe"""
    try:
        recipe = await RecipeManager.create_recipe(
            name=request.name,
            steps=[{
                "type": step.type,
                "parameters": step.parameters,
                "description": step.description
            } for step in request.steps],
            user_id=current_user_id,
            description=request.description,
            dataset_id=request.dataset_id,
            is_public=request.is_public,
            tags=request.tags
        )
        
        return RecipeResponse(
            id=str(recipe.id),
            name=recipe.name,
            description=recipe.description,
            user_id=recipe.user_id,
            steps=[{
                "step_id": step.step_id,
                "type": step.transformation_type,
                "parameters": step.parameters,
                "description": step.description,
                "order": step.order
            } for step in recipe.steps],
            created_at=recipe.created_at,
            updated_at=recipe.updated_at,
            is_public=recipe.is_public,
            tags=recipe.tags,
            usage_count=recipe.usage_count,
            rating=recipe.rating
        )
        
    except Exception as e:
        logger.error(f"Create recipe failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recipes", response_model=RecipeListResponse)
async def list_recipes(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    include_public: bool = True,
    tags: Optional[List[str]] = Query(None),
    current_user_id: str = Depends(get_current_user_id)
):
    """List user's recipes and optionally public recipes"""
    try:
        # Get recipes
        if tags:
            recipes = await RecipeManager.search_recipes(
                query="",
                user_id=current_user_id,
                tags=tags
            )
        else:
            recipes = await RecipeManager.get_user_recipes(
                user_id=current_user_id,
                include_public=include_public
            )
        
        # Paginate
        total = len(recipes)
        start = (page - 1) * per_page
        end = start + per_page
        paginated_recipes = recipes[start:end]
        
        return RecipeListResponse(
            recipes=[
                RecipeResponse(
                    id=str(recipe.id),
                    name=recipe.name,
                    description=recipe.description,
                    user_id=recipe.user_id,
                    steps=[{
                        "step_id": step.step_id,
                        "type": step.transformation_type,
                        "parameters": step.parameters,
                        "description": step.description,
                        "order": step.order
                    } for step in recipe.steps],
                    created_at=recipe.created_at,
                    updated_at=recipe.updated_at,
                    is_public=recipe.is_public,
                    tags=recipe.tags,
                    usage_count=recipe.usage_count,
                    rating=recipe.rating
                ) for recipe in paginated_recipes
            ],
            total=total,
            page=page,
            per_page=per_page
        )
        
    except Exception as e:
        logger.error(f"List recipes failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recipes/popular", response_model=RecipeListResponse)
async def list_popular_recipes(
    limit: int = Query(10, ge=1, le=50)
):
    """List most popular public recipes"""
    try:
        recipes = await RecipeManager.get_popular_recipes(limit=limit)
        
        return RecipeListResponse(
            recipes=[
                RecipeResponse(
                    id=str(recipe.id),
                    name=recipe.name,
                    description=recipe.description,
                    user_id=recipe.user_id,
                    steps=[{
                        "step_id": step.step_id,
                        "type": step.transformation_type,
                        "parameters": step.parameters,
                        "description": step.description,
                        "order": step.order
                    } for step in recipe.steps],
                    created_at=recipe.created_at,
                    updated_at=recipe.updated_at,
                    is_public=recipe.is_public,
                    tags=recipe.tags,
                    usage_count=recipe.usage_count,
                    rating=recipe.rating
                ) for recipe in recipes
            ],
            total=len(recipes),
            page=1,
            per_page=limit
        )
        
    except Exception as e:
        logger.error(f"List popular recipes failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recipes/{recipe_id}", response_model=RecipeResponse)
async def get_recipe(
    recipe_id: str,
    current_user_id: str = Depends(get_current_user_id)
):
    """Get a specific recipe"""
    try:
        recipe = await RecipeManager.get_recipe(recipe_id)
        
        if not recipe:
            raise HTTPException(status_code=404, detail="Recipe not found")
        
        # Check access
        if not recipe.is_public and recipe.user_id != current_user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        return RecipeResponse(
            id=str(recipe.id),
            name=recipe.name,
            description=recipe.description,
            user_id=recipe.user_id,
            steps=[{
                "step_id": step.step_id,
                "type": step.transformation_type,
                "parameters": step.parameters,
                "description": step.description,
                "order": step.order
            } for step in recipe.steps],
            created_at=recipe.created_at,
            updated_at=recipe.updated_at,
            is_public=recipe.is_public,
            tags=recipe.tags,
            usage_count=recipe.usage_count,
            rating=recipe.rating
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get recipe failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recipes/{recipe_id}/apply", response_model=TransformationApplyResponse)
async def apply_recipe(
    recipe_id: str,
    request: RecipeApplyRequest,
    current_user_id: str = Depends(get_current_user_id)
):
    """Apply a saved recipe to a dataset"""
    try:
        start_time = time.time()
        
        # Get recipe
        recipe = await RecipeManager.get_recipe(recipe_id)
        
        if not recipe:
            raise HTTPException(status_code=404, detail="Recipe not found")
        
        # Check access
        if not recipe.is_public and recipe.user_id != current_user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Apply transformations
        pipeline_request = TransformationPipelineRequest(
            dataset_id=request.dataset_id,
            transformations=[
                TransformationStepRequest(
                    type=step.transformation_type,
                    parameters=step.parameters,
                    description=step.description
                ) for step in recipe.steps
            ]
        )
        
        result = await apply_transformation_pipeline(pipeline_request, current_user_id)
        
        # Record execution
        if result.success:
            await RecipeManager.record_execution(
                recipe_id=recipe_id,
                user_id=current_user_id,
                dataset_id=request.dataset_id,
                success=True,
                rows_affected=result.affected_rows,
                execution_time_ms=result.execution_time_ms
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Apply recipe failed: {str(e)}")
        await RecipeManager.record_execution(
            recipe_id=recipe_id,
            user_id=current_user_id,
            dataset_id=request.dataset_id,
            success=False,
            rows_affected=0,
            execution_time_ms=int((time.time() - start_time) * 1000),
            error_message=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recipes/{recipe_id}/export", response_model=RecipeExportResponse)
async def export_recipe(
    recipe_id: str,
    request: RecipeExportRequest,
    current_user_id: str = Depends(get_current_user_id)
):
    """Export a recipe as executable code"""
    try:
        # Get recipe
        recipe = await RecipeManager.get_recipe(recipe_id)
        
        if not recipe:
            raise HTTPException(status_code=404, detail="Recipe not found")
        
        # Check access
        if not recipe.is_public and recipe.user_id != current_user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Export to code
        code = RecipeManager.export_recipe_to_code(recipe, language=request.language)
        
        return RecipeExportResponse(
            recipe_name=recipe.name,
            language=request.language,
            code=code
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Export recipe failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/recipes/{recipe_id}")
async def delete_recipe(
    recipe_id: str,
    current_user_id: str = Depends(get_current_user_id)
):
    """Delete a recipe"""
    try:
        success = await RecipeManager.delete_recipe(recipe_id, current_user_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Recipe not found or unauthorized")
        
        return {"message": "Recipe deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete recipe failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Transformation History Routes

@router.get("/{config_id}/history", response_model=TransformationHistoryResponse)
async def get_transformation_history(
    config_id: str,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Get transformation history with lineage information.

    Returns transformation steps, timestamps, parent/child relationships,
    and configuration details for a specific transformation config.
    """
    try:
        # Use TransformationService to get history
        from app.services.transformation_service import TransformationService
        service = TransformationService()

        history = await service.get_transformation_history(config_id)

        # Verify user has access to this transformation config
        if history["user_id"] != current_user_id:
            raise HTTPException(status_code=403, detail="Access denied to this transformation config")

        return TransformationHistoryResponse(
            config_id=history["config_id"],
            dataset_id=history["dataset_id"],
            user_id=history["user_id"],
            transformation_steps=history["transformation_steps"],
            is_applied=history["is_applied"],
            applied_at=history.get("applied_at"),
            current_file_path=history.get("current_file_path"),
            total_transformations=history["total_transformations"],
            total_data_loss=history["total_data_loss"],
            parent_config_id=history.get("parent_config_id"),
            version=history["version"],
            created_at=history["created_at"],
            updated_at=history["updated_at"]
        )

    except NotFoundError as e:
        logger.error(f"Get transformation history failed: {str(e)}")
        raise HTTPException(status_code=404, detail=e.message)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get transformation history failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/available", response_model=List[TransformationTypeInfo])
async def get_available_transformations():
    """
    Get list of all available transformation types with metadata.

    Returns transformation types grouped by category with parameter schemas
    and usage information for the frontend transformation library.
    """
    from app.models.transformation import TransformationType

    # Define transformation metadata by category
    transformations = []

    # Data Cleaning
    transformations.extend([
        TransformationTypeInfo(
            type=TransformationType.REMOVE_DUPLICATES.value,
            category="Data Cleaning",
            label="Remove Duplicates",
            description="Remove duplicate rows from dataset",
            parameters_schema={},
            requires_columns=False
        ),
        TransformationTypeInfo(
            type=TransformationType.TRIM_WHITESPACE.value,
            category="Data Cleaning",
            label="Trim Whitespace",
            description="Remove leading and trailing whitespace from text columns",
            parameters_schema={"columns": {"type": "array", "items": {"type": "string"}}},
            requires_columns=True
        ),
        TransformationTypeInfo(
            type=TransformationType.FIX_CASING.value,
            category="Data Cleaning",
            label="Fix Casing",
            description="Standardize text casing (lower, upper, title)",
            parameters_schema={
                "columns": {"type": "array", "items": {"type": "string"}},
                "casing": {"type": "string", "enum": ["lower", "upper", "title"]}
            },
            requires_columns=True
        ),
        TransformationTypeInfo(
            type=TransformationType.REMOVE_SPECIAL_CHARS.value,
            category="Data Cleaning",
            label="Remove Special Characters",
            description="Remove or replace special characters from text",
            parameters_schema={"columns": {"type": "array", "items": {"type": "string"}}},
            requires_columns=True
        ),
    ])

    # Missing Values
    transformations.extend([
        TransformationTypeInfo(
            type=TransformationType.DROP_MISSING.value,
            category="Missing Values",
            label="Drop Missing",
            description="Remove rows with missing values",
            parameters_schema={"columns": {"type": "array", "items": {"type": "string"}}},
            requires_columns=False
        ),
        TransformationTypeInfo(
            type=TransformationType.FILL_MISSING.value,
            category="Missing Values",
            label="Fill Missing",
            description="Fill missing values with a specified value",
            parameters_schema={
                "columns": {"type": "array", "items": {"type": "string"}},
                "fill_value": {"type": "string"}
            },
            requires_columns=True
        ),
        TransformationTypeInfo(
            type=TransformationType.IMPUTE_MEAN.value,
            category="Missing Values",
            label="Impute with Mean",
            description="Replace missing values with column mean",
            parameters_schema={"columns": {"type": "array", "items": {"type": "string"}}},
            requires_columns=True
        ),
        TransformationTypeInfo(
            type=TransformationType.IMPUTE_MEDIAN.value,
            category="Missing Values",
            label="Impute with Median",
            description="Replace missing values with column median",
            parameters_schema={"columns": {"type": "array", "items": {"type": "string"}}},
            requires_columns=True
        ),
        TransformationTypeInfo(
            type=TransformationType.IMPUTE_MODE.value,
            category="Missing Values",
            label="Impute with Mode",
            description="Replace missing values with most common value",
            parameters_schema={"columns": {"type": "array", "items": {"type": "string"}}},
            requires_columns=True
        ),
    ])

    # Type Conversions
    transformations.extend([
        TransformationTypeInfo(
            type=TransformationType.TO_NUMERIC.value,
            category="Type Conversion",
            label="To Numeric",
            description="Convert columns to numeric type",
            parameters_schema={"columns": {"type": "array", "items": {"type": "string"}}},
            requires_columns=True
        ),
        TransformationTypeInfo(
            type=TransformationType.TO_STRING.value,
            category="Type Conversion",
            label="To String",
            description="Convert columns to string type",
            parameters_schema={"columns": {"type": "array", "items": {"type": "string"}}},
            requires_columns=True
        ),
        TransformationTypeInfo(
            type=TransformationType.TO_DATETIME.value,
            category="Type Conversion",
            label="To DateTime",
            description="Parse columns as date/time values",
            parameters_schema={
                "columns": {"type": "array", "items": {"type": "string"}},
                "format": {"type": "string"}
            },
            requires_columns=True
        ),
        TransformationTypeInfo(
            type=TransformationType.TO_BOOLEAN.value,
            category="Type Conversion",
            label="To Boolean",
            description="Convert columns to true/false values",
            parameters_schema={"columns": {"type": "array", "items": {"type": "string"}}},
            requires_columns=True
        ),
        TransformationTypeInfo(
            type=TransformationType.ONE_HOT_ENCODE.value,
            category="Type Conversion",
            label="One-Hot Encode",
            description="Create dummy variables for categorical columns",
            parameters_schema={"columns": {"type": "array", "items": {"type": "string"}}},
            requires_columns=True
        ),
        TransformationTypeInfo(
            type=TransformationType.LABEL_ENCODE.value,
            category="Type Conversion",
            label="Label Encode",
            description="Convert categories to integer labels",
            parameters_schema={"columns": {"type": "array", "items": {"type": "string"}}},
            requires_columns=True
        ),
    ])

    # Date/Time
    transformations.extend([
        TransformationTypeInfo(
            type=TransformationType.EXTRACT_DATE_PARTS.value,
            category="Date/Time",
            label="Extract Date Parts",
            description="Extract year, month, day, etc. from datetime columns",
            parameters_schema={
                "columns": {"type": "array", "items": {"type": "string"}},
                "parts": {"type": "array", "items": {"type": "string", "enum": ["year", "month", "day", "hour", "minute", "second"]}}
            },
            requires_columns=True
        ),
        TransformationTypeInfo(
            type=TransformationType.CALCULATE_AGE.value,
            category="Date/Time",
            label="Calculate Age",
            description="Calculate age from date of birth column",
            parameters_schema={
                "column": {"type": "string"},
                "reference_date": {"type": "string"}
            },
            requires_columns=True
        ),
    ])

    # Scaling/Normalization
    transformations.extend([
        TransformationTypeInfo(
            type=TransformationType.SCALE.value,
            category="Scaling",
            label="Scale",
            description="Scale numeric columns to a specific range",
            parameters_schema={
                "columns": {"type": "array", "items": {"type": "string"}},
                "min": {"type": "number"},
                "max": {"type": "number"}
            },
            requires_columns=True
        ),
        TransformationTypeInfo(
            type=TransformationType.NORMALIZE.value,
            category="Scaling",
            label="Normalize",
            description="Normalize numeric columns (L2 normalization)",
            parameters_schema={"columns": {"type": "array", "items": {"type": "string"}}},
            requires_columns=True
        ),
        TransformationTypeInfo(
            type=TransformationType.STANDARDIZE.value,
            category="Scaling",
            label="Standardize",
            description="Standardize numeric columns (z-score normalization)",
            parameters_schema={"columns": {"type": "array", "items": {"type": "string"}}},
            requires_columns=True
        ),
    ])

    return transformations