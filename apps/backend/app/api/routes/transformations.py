"""
API routes for data transformation pipeline
"""
import asyncio
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
    RecipeCompatibilityRequest,
    RecipeCompatibilityResponse,
    RecipeVersionRequest,
    RecipeShareRequest,
    RecipeShareResponse,
    SharedRecipeListResponse,
    RecipeImportRequest,
    RecipeExportJSONResponse,
    RecipeDuplicateRequest,
    RecipeVersionHistoryResponse,
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
from app.services.transformation_engine.recipe_manager import RecipeManager, RecipeCompatibilityChecker
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

        # Validate transformation type against whitelist
        try:
            transformation_type = EngineTransformationType(first_step.transformation_type)
        except ValueError:
            valid_types = [t.value for t in EngineTransformationType]
            raise HTTPException(
                status_code=400,
                detail=f"Invalid transformation type '{first_step.transformation_type}'. Allowed types: {', '.join(valid_types)}"
            )

        # Use TransformationService for preview
        from app.services.transformation_service import TransformationService
        service = TransformationService()

        # SECURITY: Defense-in-depth timeout at API layer (service layer also has timeout)
        try:
            async with asyncio.timeout(30.0):
                # Use validated enum value to prevent bypass
                result = await service.preview_transformation(
                    user_id=current_user_id,
                    dataset_id=request.dataset_id,
                    transformation_type=transformation_type.value,
                    parameters=first_step.parameters or {},
                    preview_rows=request.preview_rows
                )
        except asyncio.TimeoutError:
            logger.error(f"Preview timeout at API layer for dataset {request.dataset_id}")
            raise HTTPException(
                status_code=408,
                detail="Preview timeout (30s). Try reducing preview_rows or simplifying transformations."
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

    except HTTPException:
        # Re-raise HTTP exceptions (including timeout) to let FastAPI handle them
        raise
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
            # Validate transformation type against whitelist
            try:
                transformation_type = EngineTransformationType(step.type)
            except ValueError:
                # Invalid transformation type - reject request
                valid_types = [t.value for t in EngineTransformationType]
                return TransformationApplyResponse(
                    success=False,
                    dataset_id=request.dataset_id,
                    transformation_id="",
                    execution_time_ms=int((time.time() - start_time) * 1000),
                    error=f"Invalid transformation type '{step.type}'. Allowed types: {', '.join(valid_types)}"
                )

            result = engine.apply_transformation(
                df=df,
                transformation_type=transformation_type,
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


@router.get("/recipes/shared", response_model=SharedRecipeListResponse)
async def get_shared_recipes(
    current_user_id: str = Depends(get_current_user_id)
):
    """Get all recipes shared with the current user"""
    try:
        shared_recipes = await RecipeManager.get_shared_recipes(current_user_id)

        return SharedRecipeListResponse(
            shared_recipes=[{
                "id": str(sr.id),
                "name": sr.name,
                "description": sr.description,
                "original_recipe_id": str(sr.original_recipe_id),
                "original_owner_id": sr.original_owner_id,
                "shared_at": sr.shared_at.isoformat(),
                "version": sr.version,
                "tags": sr.tags,
                "steps_count": len(sr.steps)
            } for sr in shared_recipes],
            total=len(shared_recipes)
        )

    except Exception as e:
        logger.error(f"Get shared recipes failed: {str(e)}")
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


# Enhanced Recipe Management Routes

@router.post("/recipes/{recipe_id}/check-compatibility", response_model=RecipeCompatibilityResponse)
async def check_recipe_compatibility(
    recipe_id: str,
    request: RecipeCompatibilityRequest,
    current_user_id: str = Depends(get_current_user_id)
):
    """Check if recipe can be applied to a dataset"""
    try:
        # Fetch recipe to check authorization
        recipe = await RecipeManager.get_recipe(recipe_id)

        if not recipe:
            raise HTTPException(status_code=404, detail="Recipe not found")

        # Check access - user must own the recipe or it must be public
        if not recipe.is_public and recipe.user_id != current_user_id:
            logger.warning(
                f"Access denied: User {current_user_id} attempted to check compatibility "
                f"for recipe {recipe_id} owned by {recipe.user_id}"
            )
            raise HTTPException(status_code=403, detail="Access denied")

        # Only proceed with compatibility check if authorized
        compatibility = await RecipeCompatibilityChecker.check_compatibility(
            recipe_id=recipe_id,
            dataset_schema=request.dataset_schema
        )

        return RecipeCompatibilityResponse(
            is_compatible=compatibility.is_compatible,
            missing_columns=compatibility.missing_columns,
            type_mismatches=compatibility.type_mismatches,
            warnings=compatibility.warnings,
            suggestions=compatibility.suggestions,
            compatibility_score=compatibility.compatibility_score
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Compatibility check failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recipes/{recipe_id}/versions", response_model=RecipeResponse)
async def create_recipe_version(
    recipe_id: str,
    request: RecipeVersionRequest,
    current_user_id: str = Depends(get_current_user_id)
):
    """Create a new version of a recipe"""
    try:
        new_version = await RecipeManager.create_version(
            recipe_id=recipe_id,
            user_id=current_user_id,
            changes=request.changes,
            version_notes=request.version_notes
        )

        if not new_version:
            raise HTTPException(status_code=404, detail="Recipe not found or unauthorized")

        return RecipeResponse(
            id=str(new_version.id),
            name=new_version.name,
            description=new_version.description,
            user_id=new_version.user_id,
            steps=[{
                "step_id": step.step_id,
                "type": step.transformation_type,
                "parameters": step.parameters,
                "description": step.description,
                "order": step.order
            } for step in new_version.steps],
            created_at=new_version.created_at,
            updated_at=new_version.updated_at,
            is_public=new_version.is_public,
            tags=new_version.tags,
            usage_count=new_version.usage_count,
            rating=new_version.rating
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create version failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recipes/{recipe_id}/versions", response_model=RecipeVersionHistoryResponse)
async def get_recipe_version_history(
    recipe_id: str,
    current_user_id: str = Depends(get_current_user_id)
):
    """Get version history for a recipe"""
    try:
        # Fetch recipe to check authorization
        recipe = await RecipeManager.get_recipe(recipe_id)

        if not recipe:
            raise HTTPException(status_code=404, detail="Recipe not found")

        # Check access - user must own the recipe or it must be public
        if not recipe.is_public and recipe.user_id != current_user_id:
            logger.warning(
                f"Access denied: User {current_user_id} attempted to view version history "
                f"for recipe {recipe_id} owned by {recipe.user_id}"
            )
            raise HTTPException(status_code=403, detail="Not authorized to view recipe versions")

        # Only proceed with fetching version history if authorized
        versions = await RecipeManager.get_version_history(recipe_id)

        return RecipeVersionHistoryResponse(
            versions=[{
                "id": str(v.id),
                "name": v.name,
                "version": v.version,
                "created_at": v.created_at.isoformat(),
                "updated_at": v.updated_at.isoformat(),
                "parent_recipe_id": str(v.parent_recipe_id) if v.parent_recipe_id else None,
                "metadata": v.metadata
            } for v in versions],
            total_versions=len(versions)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get version history failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recipes/{recipe_id}/duplicate", response_model=RecipeResponse)
async def duplicate_recipe(
    recipe_id: str,
    request: RecipeDuplicateRequest,
    current_user_id: str = Depends(get_current_user_id)
):
    """Duplicate a recipe as a template"""
    try:
        # Fetch source recipe to check authorization
        recipe = await RecipeManager.get_recipe(recipe_id)

        if not recipe:
            raise HTTPException(status_code=404, detail="Recipe not found")

        # Check access - user must own the recipe or it must be public
        if not recipe.is_public and recipe.user_id != current_user_id:
            logger.warning(
                f"Access denied: User {current_user_id} attempted to duplicate "
                f"recipe {recipe_id} owned by {recipe.user_id}"
            )
            raise HTTPException(status_code=403, detail="Access denied")

        # Only proceed with duplication if authorized
        duplicate = await RecipeManager.duplicate_recipe(
            recipe_id=recipe_id,
            user_id=current_user_id,
            new_name=request.new_name
        )

        if not duplicate:
            raise HTTPException(status_code=404, detail="Recipe not found")

        return RecipeResponse(
            id=str(duplicate.id),
            name=duplicate.name,
            description=duplicate.description,
            user_id=duplicate.user_id,
            steps=[{
                "step_id": step.step_id,
                "type": step.transformation_type,
                "parameters": step.parameters,
                "description": step.description,
                "order": step.order
            } for step in duplicate.steps],
            created_at=duplicate.created_at,
            updated_at=duplicate.updated_at,
            is_public=duplicate.is_public,
            tags=duplicate.tags,
            usage_count=duplicate.usage_count,
            rating=duplicate.rating
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Duplicate recipe failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recipes/{recipe_id}/share", response_model=RecipeShareResponse)
async def share_recipe(
    recipe_id: str,
    request: RecipeShareRequest,
    current_user_id: str = Depends(get_current_user_id)
):
    """Share a recipe with another user (creates independent copy)"""
    try:
        shared = await RecipeManager.share_recipe(
            recipe_id=recipe_id,
            owner_id=current_user_id,
            target_user_id=request.target_user_id
        )

        if not shared:
            raise HTTPException(status_code=404, detail="Recipe not found or unauthorized")

        return RecipeShareResponse(
            shared_recipe_id=str(shared.id),
            target_user_id=request.target_user_id,
            shared_at=shared.shared_at.isoformat(),
            message=f"Recipe shared successfully with user {request.target_user_id}"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Share recipe failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recipes/{recipe_id}/export/json", response_model=RecipeExportJSONResponse)
async def export_recipe_json(
    recipe_id: str,
    current_user_id: str = Depends(get_current_user_id)
):
    """Export recipe as JSON for portability"""
    try:
        recipe = await RecipeManager.get_recipe(recipe_id)

        if not recipe:
            raise HTTPException(status_code=404, detail="Recipe not found")

        # Check access
        if not recipe.is_public and recipe.user_id != current_user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        json_data = RecipeManager.export_recipe_to_json(recipe)

        return RecipeExportJSONResponse(
            format_version=json_data["format_version"],
            recipe=json_data["recipe"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Export recipe JSON failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recipes/import", response_model=RecipeResponse)
async def import_recipe(
    request: RecipeImportRequest,
    current_user_id: str = Depends(get_current_user_id)
):
    """Import recipe from JSON"""
    try:
        imported = await RecipeManager.import_recipe_from_json(
            json_data=request.json_data,
            user_id=current_user_id,
            name_override=request.name_override
        )

        if not imported:
            raise HTTPException(status_code=400, detail="Import failed - invalid recipe format")

        return RecipeResponse(
            id=str(imported.id),
            name=imported.name,
            description=imported.description,
            user_id=imported.user_id,
            steps=[{
                "step_id": step.step_id,
                "type": step.transformation_type,
                "parameters": step.parameters,
                "description": step.description,
                "order": step.order
            } for step in imported.steps],
            created_at=imported.created_at,
            updated_at=imported.updated_at,
            is_public=imported.is_public,
            tags=imported.tags,
            usage_count=imported.usage_count,
            rating=imported.rating
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Import recipe failed: {str(e)}")
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