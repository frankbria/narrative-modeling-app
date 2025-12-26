"""
Feature Engineering API routes.

Provides endpoints for AI-powered feature suggestions, feedback recording,
and feature application.
"""

from fastapi import APIRouter, HTTPException, Depends, status, Query, Path
from typing import Optional, List
import logging
import pandas as pd
import io
import uuid
from datetime import datetime

from app.schemas.feature_engineering import (
    FeatureSuggestionRequest,
    FeatureSuggestionResponse,
    FeatureFeedbackRequest,
    FeatureFeedbackResponse,
    GenerateMoreRequest,
    ApplyFeatureRequest,
    ApplyMultipleFeaturesRequest,
    ApplyFeatureResponse,
    FeatureExplanationResponse,
    FeatureFeedbackRecord,
    FeatureType
)
from app.services.feature_engineering_service import feature_engineering_service
from app.services.dataset_service import DatasetService
from app.services.s3_service import download_file_from_s3
from app.auth.nextauth_auth import get_current_user_id
from app.models.dataset import DatasetMetadata

logger = logging.getLogger(__name__)

router = APIRouter()


async def _load_dataset_dataframe(dataset_id: str, user_id: str) -> pd.DataFrame:
    """Load dataset as DataFrame from S3"""
    service = DatasetService()
    dataset = await service.get_dataset(dataset_id=dataset_id)

    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {dataset_id} not found"
        )

    if dataset.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this dataset"
        )

    # Download and parse file
    try:
        file_path = download_file_from_s3(dataset.s3_url)
        file_type = dataset.file_type.lower()

        if file_type == 'csv':
            df = pd.read_csv(file_path)
        elif file_type in ['xlsx', 'xls']:
            df = pd.read_excel(file_path)
        elif file_type == 'json':
            df = pd.read_json(file_path)
        elif file_type == 'parquet':
            df = pd.read_parquet(file_path)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type: {file_type}"
            )

        return df
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading dataset {dataset_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error loading dataset: {str(e)}"
        )


@router.post(
    "/datasets/{dataset_id}/features/suggest",
    response_model=FeatureSuggestionResponse,
    summary="Generate AI-powered feature suggestions",
    description="""
    Analyze a dataset and generate feature engineering suggestions using
    a combination of rule-based heuristics and AI (GPT-4).

    The endpoint will:
    1. Auto-detect problem type (classification/regression) if not provided
    2. Auto-detect data domain (financial, healthcare, etc.)
    3. Generate rule-based suggestions (polynomial, interaction, aggregation, etc.)
    4. Generate AI-powered creative suggestions
    5. Estimate importance scores for each suggestion
    6. Return ranked suggestions

    **Performance Notes:**
    - Suggestions are cached for 1 hour per dataset/target combination
    - AI suggestion generation may take 2-5 seconds
    - Large datasets are sampled for importance estimation
    """
)
async def suggest_features(
    dataset_id: str = Path(..., description="Dataset identifier"),
    request: FeatureSuggestionRequest = None,
    current_user_id: str = Depends(get_current_user_id)
) -> FeatureSuggestionResponse:
    """Generate feature suggestions for a dataset"""
    try:
        logger.info(f"Generating feature suggestions for dataset {dataset_id}")

        # Handle case where request body is not provided
        if request is None:
            request = FeatureSuggestionRequest()

        # Load dataset
        df = await _load_dataset_dataframe(dataset_id, current_user_id)

        # Generate suggestions
        response = await feature_engineering_service.suggest_features(
            df=df,
            dataset_id=dataset_id,
            target_column=request.target_column,
            problem_type=request.problem_type,
            max_suggestions=request.max_suggestions,
            include_ai=request.include_ai_suggestions,
            feature_types=request.feature_types
        )

        logger.info(f"Generated {response.total_suggestions} suggestions for dataset {dataset_id}")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating suggestions for dataset {dataset_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating suggestions: {str(e)}"
        )


@router.get(
    "/datasets/{dataset_id}/features/suggestions/{suggestion_id}",
    response_model=FeatureExplanationResponse,
    summary="Get detailed explanation for a suggestion",
    description="Retrieve detailed explanation, example calculations, and use cases for a specific feature suggestion."
)
async def get_suggestion_explanation(
    dataset_id: str = Path(..., description="Dataset identifier"),
    suggestion_id: str = Path(..., description="Suggestion identifier"),
    current_user_id: str = Depends(get_current_user_id)
) -> FeatureExplanationResponse:
    """Get detailed explanation for a feature suggestion"""
    try:
        # First regenerate suggestions to find the one we need
        df = await _load_dataset_dataframe(dataset_id, current_user_id)

        # Generate suggestions (should hit cache)
        suggestions_response = await feature_engineering_service.suggest_features(
            df=df,
            dataset_id=dataset_id
        )

        # Find the specific suggestion
        suggestion = None
        for s in suggestions_response.suggestions:
            if s.id == suggestion_id:
                suggestion = s
                break

        if not suggestion:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Suggestion {suggestion_id} not found"
            )

        # Generate explanation
        analysis = await feature_engineering_service._analyze_dataset(df, None, None)
        explanation = await feature_engineering_service.explain_feature(suggestion, analysis)

        return FeatureExplanationResponse(**explanation)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting explanation for suggestion {suggestion_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting explanation: {str(e)}"
        )


@router.post(
    "/features/suggestions/{suggestion_id}/feedback",
    response_model=FeatureFeedbackResponse,
    summary="Record feedback on a suggestion",
    description="Record whether a user accepted or rejected a feature suggestion. This feedback is used to improve future suggestions."
)
async def record_suggestion_feedback(
    suggestion_id: str = Path(..., description="Suggestion identifier"),
    request: FeatureFeedbackRequest = None,
    dataset_id: str = Query(..., description="Dataset identifier"),
    current_user_id: str = Depends(get_current_user_id)
) -> FeatureFeedbackResponse:
    """Record user feedback on a feature suggestion"""
    try:
        logger.info(f"Recording feedback for suggestion {suggestion_id}: accepted={request.accepted}")

        # Create feedback record
        feedback = FeatureFeedbackRecord(
            feedback_id=f"fb_{uuid.uuid4().hex[:12]}",
            suggestion_id=suggestion_id,
            user_id=current_user_id,
            dataset_id=dataset_id,
            feature_type=FeatureType.MATHEMATICAL,  # Default, would be looked up in production
            accepted=request.accepted,
            modified_parameters=request.modified_parameters,
            reason=request.reason,
            created_at=datetime.utcnow()
        )

        # Record feedback
        success = await feature_engineering_service.record_feedback(feedback)

        if success:
            return FeatureFeedbackResponse(
                suggestion_id=suggestion_id,
                accepted=request.accepted,
                recorded_at=datetime.utcnow(),
                message="Feedback recorded successfully"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to record feedback"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error recording feedback for suggestion {suggestion_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error recording feedback: {str(e)}"
        )


@router.post(
    "/datasets/{dataset_id}/features/suggest-more",
    response_model=FeatureSuggestionResponse,
    summary="Generate additional suggestions",
    description="Generate additional feature suggestions, excluding previously shown suggestions."
)
async def suggest_more_features(
    dataset_id: str = Path(..., description="Dataset identifier"),
    request: GenerateMoreRequest = None,
    current_user_id: str = Depends(get_current_user_id)
) -> FeatureSuggestionResponse:
    """Generate additional feature suggestions"""
    try:
        logger.info(f"Generating additional suggestions for dataset {dataset_id}")

        # Load dataset
        df = await _load_dataset_dataframe(dataset_id, current_user_id)

        # Generate more suggestions with higher AI temperature for creativity
        response = await feature_engineering_service.suggest_features(
            df=df,
            dataset_id=dataset_id,
            target_column=request.target_column,
            problem_type=request.problem_type,
            max_suggestions=request.count + len(request.excluded_suggestion_ids),
            include_ai=True,
            feature_types=request.prefer_feature_types
        )

        # Filter out excluded suggestions
        filtered_suggestions = [
            s for s in response.suggestions
            if s.id not in request.excluded_suggestion_ids
        ][:request.count]

        response.suggestions = filtered_suggestions
        response.total_suggestions = len(filtered_suggestions)

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating more suggestions for dataset {dataset_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating suggestions: {str(e)}"
        )


@router.post(
    "/datasets/{dataset_id}/features/apply",
    response_model=ApplyFeatureResponse,
    summary="Apply a feature suggestion",
    description="Apply a single feature suggestion to the dataset, creating a new column."
)
async def apply_feature(
    dataset_id: str = Path(..., description="Dataset identifier"),
    request: ApplyFeatureRequest = None,
    current_user_id: str = Depends(get_current_user_id)
) -> ApplyFeatureResponse:
    """Apply a single feature suggestion to the dataset"""
    try:
        logger.info(f"Applying feature {request.suggestion_id} to dataset {dataset_id}")

        # Load dataset
        df = await _load_dataset_dataframe(dataset_id, current_user_id)

        # Get the suggestion
        suggestions_response = await feature_engineering_service.suggest_features(
            df=df,
            dataset_id=dataset_id
        )

        suggestion = None
        for s in suggestions_response.suggestions:
            if s.id == request.suggestion_id:
                suggestion = s
                break

        if not suggestion:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Suggestion {request.suggestion_id} not found"
            )

        # Apply the feature (simplified implementation)
        applied_features = []
        failed_features = []

        try:
            # Apply based on feature type
            new_col = await _apply_single_feature(df, suggestion, request.parameters)
            if new_col is not None:
                applied_features.append(suggestion.name)
            else:
                failed_features.append({
                    "name": suggestion.name,
                    "error": "Feature application not implemented for this type"
                })
        except Exception as e:
            failed_features.append({
                "name": suggestion.name,
                "error": str(e)
            })

        # Get preview data
        preview = df.head(5).to_dict(orient="records") if applied_features else None

        return ApplyFeatureResponse(
            dataset_id=dataset_id,
            applied_features=applied_features,
            failed_features=failed_features,
            new_column_count=len(applied_features),
            preview_data=preview,
            message=f"Applied {len(applied_features)} feature(s)"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error applying feature to dataset {dataset_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error applying feature: {str(e)}"
        )


@router.post(
    "/datasets/{dataset_id}/features/apply-multiple",
    response_model=ApplyFeatureResponse,
    summary="Apply multiple feature suggestions",
    description="Apply multiple feature suggestions to the dataset at once."
)
async def apply_multiple_features(
    dataset_id: str = Path(..., description="Dataset identifier"),
    request: ApplyMultipleFeaturesRequest = None,
    current_user_id: str = Depends(get_current_user_id)
) -> ApplyFeatureResponse:
    """Apply multiple feature suggestions to the dataset"""
    try:
        logger.info(f"Applying {len(request.suggestion_ids)} features to dataset {dataset_id}")

        # Load dataset
        df = await _load_dataset_dataframe(dataset_id, current_user_id)

        # Get suggestions
        suggestions_response = await feature_engineering_service.suggest_features(
            df=df,
            dataset_id=dataset_id
        )

        suggestion_map = {s.id: s for s in suggestions_response.suggestions}

        applied_features = []
        failed_features = []

        for suggestion_id in request.suggestion_ids:
            suggestion = suggestion_map.get(suggestion_id)
            if not suggestion:
                failed_features.append({
                    "name": suggestion_id,
                    "error": "Suggestion not found"
                })
                continue

            try:
                params = None
                if request.parameter_overrides:
                    params = request.parameter_overrides.get(suggestion_id)

                new_col = await _apply_single_feature(df, suggestion, params)
                if new_col is not None:
                    applied_features.append(suggestion.name)
                else:
                    failed_features.append({
                        "name": suggestion.name,
                        "error": "Feature application not implemented"
                    })
            except Exception as e:
                failed_features.append({
                    "name": suggestion.name,
                    "error": str(e)
                })

        preview = df.head(5).to_dict(orient="records") if applied_features else None

        return ApplyFeatureResponse(
            dataset_id=dataset_id,
            applied_features=applied_features,
            failed_features=failed_features,
            new_column_count=len(applied_features),
            preview_data=preview,
            message=f"Applied {len(applied_features)} of {len(request.suggestion_ids)} feature(s)"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error applying features to dataset {dataset_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error applying features: {str(e)}"
        )


async def _apply_single_feature(
    df: pd.DataFrame,
    suggestion,
    parameters: Optional[dict] = None
) -> Optional[str]:
    """Apply a single feature suggestion to a dataframe"""
    import numpy as np

    params = suggestion.parameters.copy()
    if parameters:
        params.update(parameters)

    input_cols = suggestion.input_columns
    feature_type = suggestion.feature_type

    # Validate input columns exist
    for col in input_cols:
        if col not in df.columns:
            raise ValueError(f"Column '{col}' not found in dataset")

    try:
        if feature_type == FeatureType.POLYNOMIAL:
            col = input_cols[0]
            func = params.get("function", "")
            power = params.get("power", 2)

            if func == "sqrt":
                df[suggestion.name] = np.sqrt(df[col].clip(lower=0))
            elif func == "log":
                df[suggestion.name] = np.log1p(df[col].clip(lower=0))
            else:
                df[suggestion.name] = df[col] ** power
            return suggestion.name

        elif feature_type == FeatureType.INTERACTION:
            col1, col2 = input_cols[0], input_cols[1]
            operation = params.get("operation", "multiply")

            if operation == "multiply":
                df[suggestion.name] = df[col1] * df[col2]
            elif operation == "divide":
                df[suggestion.name] = df[col1] / (df[col2] + 1e-8)
            elif operation == "add":
                df[suggestion.name] = df[col1] + df[col2]
            elif operation == "subtract":
                df[suggestion.name] = df[col1] - df[col2]
            return suggestion.name

        elif feature_type == FeatureType.TIME_BASED:
            col = input_cols[0]
            extract = params.get("extract", "")

            # Convert to datetime if needed
            dt_col = pd.to_datetime(df[col], errors='coerce')

            if extract == "dayofweek":
                df[suggestion.name] = dt_col.dt.dayofweek
            elif extract == "month":
                df[suggestion.name] = dt_col.dt.month
            elif extract == "hour":
                df[suggestion.name] = dt_col.dt.hour
            elif extract == "quarter":
                df[suggestion.name] = dt_col.dt.quarter
            elif extract == "is_weekend":
                df[suggestion.name] = dt_col.dt.dayofweek.isin([5, 6]).astype(int)
            return suggestion.name

        elif feature_type == FeatureType.TEXT:
            col = input_cols[0]
            operation = params.get("operation", "")

            if operation == "char_count":
                df[suggestion.name] = df[col].astype(str).str.len()
            elif operation == "word_count":
                df[suggestion.name] = df[col].astype(str).str.split().str.len()
            elif operation == "has_special":
                df[suggestion.name] = df[col].astype(str).str.contains(r'[!@#$%^&*]', regex=True).astype(int)
            return suggestion.name

        elif feature_type == FeatureType.BINNING:
            col = input_cols[0]
            method = params.get("method", "equal_width")
            bins = params.get("bins", 5)

            if method == "quantile":
                df[suggestion.name] = pd.qcut(df[col], q=bins, labels=False, duplicates='drop')
            else:
                df[suggestion.name] = pd.cut(df[col], bins=bins, labels=False)
            return suggestion.name

        elif feature_type == FeatureType.AGGREGATION:
            aggregation = params.get("aggregation", "mean")
            group_by = params.get("group_by")

            if not group_by or group_by not in df.columns:
                return None

            if aggregation == "mean" and len(input_cols) > 0:
                num_col = input_cols[0]
                df[suggestion.name] = df.groupby(group_by)[num_col].transform("mean")
            elif aggregation == "count":
                df[suggestion.name] = df.groupby(group_by)[group_by].transform("count")
            return suggestion.name

        else:
            # Feature type not yet implemented
            return None

    except Exception as e:
        raise ValueError(f"Failed to apply feature: {str(e)}")
