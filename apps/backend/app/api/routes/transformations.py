"""
API routes for data transformation pipeline
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
import pandas as pd
from datetime import datetime
import logging
import time

from app.auth.clerk_auth import get_current_user_id
from app.models.user_data import UserData
from app.schemas.transformation import (
    TransformationRequest,
    TransformationPreviewResponse,
    TransformationApplyResponse,
    TransformationPipelineRequest,
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
)
from app.services.transformation_service.transformation_engine import (
    TransformationEngine,
    TransformationType as EngineTransformationType
)
from app.services.transformation_service.validators import TransformationValidator
from app.services.transformation_service.recipe_manager import RecipeManager
from app.services.transformation_service.data_utils import get_dataframe_from_s3, upload_dataframe_to_s3
from app.services.redis_cache import cache_service

router = APIRouter(prefix="/transformations", tags=["transformations"])
logger = logging.getLogger(__name__)


@router.post("/preview", response_model=TransformationPreviewResponse)
async def preview_transformation(
    request: TransformationRequest,
    current_user_id: str = Depends(get_current_user_id)
):
    """Preview a transformation on a subset of data"""
    try:
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
        
        # Preview transformation
        result = engine.preview_transformation(
            df=df,
            transformation_type=EngineTransformationType(request.transformation_type),
            parameters=request.parameters,
            n_rows=request.preview_rows
        )
        
        return TransformationPreviewResponse(
            success=result.success,
            preview_data=result.preview_data,
            affected_rows=result.affected_rows,
            affected_columns=result.affected_columns,
            stats_before=result.stats_before,
            stats_after=result.stats_after,
            error=result.error,
            warnings=result.warnings
        )
        
    except Exception as e:
        logger.error(f"Preview transformation failed: {str(e)}")
        return TransformationPreviewResponse(
            success=False,
            error=str(e)
        )


@router.post("/apply", response_model=TransformationApplyResponse)
async def apply_transformation(
    request: TransformationRequest,
    current_user_id: str = Depends(get_current_user_id)
):
    """Apply a transformation to the full dataset"""
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
        
        # Apply transformation
        result = engine.apply_transformation(
            df=df,
            transformation_type=EngineTransformationType(request.transformation_type),
            parameters=request.parameters
        )
        
        if not result.success:
            return TransformationApplyResponse(
                success=False,
                dataset_id=request.dataset_id,
                transformation_id="",
                execution_time_ms=int((time.time() - start_time) * 1000),
                error=result.error
            )
        
        # Save transformed data back to S3
        transformed_df = pd.DataFrame(result.transformed_data)
        new_file_path = await upload_dataframe_to_s3(
            transformed_df,
            f"transformed/{current_user_id}/{request.dataset_id}_{datetime.utcnow().timestamp()}.parquet"
        )
        
        # Update user data with new file path
        user_data.file_path = new_file_path
        user_data.updated_at = datetime.utcnow()
        user_data.transformation_history.append({
            "timestamp": datetime.utcnow(),
            "type": request.transformation_type,
            "parameters": request.parameters,
            "affected_rows": result.affected_rows
        })
        await user_data.save()
        
        # Clear cached data
        await cache_service.delete_pattern(f"stats_{request.dataset_id}_*")
        
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        return TransformationApplyResponse(
            success=True,
            dataset_id=request.dataset_id,
            transformation_id=f"transform_{datetime.utcnow().timestamp()}",
            affected_rows=result.affected_rows,
            affected_columns=result.affected_columns,
            execution_time_ms=execution_time_ms
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
            transformations.append({
                "type": "drop_missing",
                "parameters": {"how": "any"}
            })
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