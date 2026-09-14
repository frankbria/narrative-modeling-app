"""
Feature Engineering API routes.

Provides endpoints for AI-powered feature suggestions, feedback recording,
and feature application.
"""

import asyncio
import logging
import uuid
from datetime import UTC, datetime

import pandas as pd
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
from app.billing import enforcement
from app.billing.enforcement import quota
from app.schemas.feature_engineering import (
    ApplyFeatureRequest,
    ApplyFeatureResponse,
    ApplyMultipleFeaturesRequest,
    FeatureExplanationResponse,
    FeatureFeedbackRecord,
    FeatureFeedbackRequest,
    FeatureFeedbackResponse,
    FeatureSuggestionRequest,
    FeatureSuggestionResponse,
    FeatureType,
    GenerateMoreRequest,
)
from app.services.dataset_service import DatasetService
from app.services.feature_engineering_service import feature_engineering_service
from app.services.s3_service import load_dataframe_from_s3

logger = logging.getLogger(__name__)

router = APIRouter()

# Allowed file types for dataset loading (security whitelist)
ALLOWED_FILE_TYPES = {'csv', 'xlsx', 'xls', 'json', 'parquet'}


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

    # Explicit whitelist validation for security (before any download)
    file_type = dataset.file_type.lower()
    if file_type not in ALLOWED_FILE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {file_type}. Allowed types: {', '.join(sorted(ALLOWED_FILE_TYPES))}"
        )

    # Centralized download+parse+cleanup off the event loop (#265/#280):
    # the helper always unlinks the temp file so /tmp doesn't accumulate copies.
    try:
        return await asyncio.to_thread(
            load_dataframe_from_s3, dataset.s3_url, file_type
        )
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
    dependencies=[Depends(quota("ai_calls"))],  # reaches suggest_features(include_ai) (#461)
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
    - Suggestions are cached ~1 hour per (user, dataset); each /suggest overwrites
      the set and /suggest-more appends to it, so apply/feedback/explain resolve by id
    - AI suggestion generation may take 2-5 seconds
    - Large datasets are sampled for importance estimation
    """
)
async def suggest_features(
    http_request: Request,
    dataset_id: str = Path(..., description="Dataset identifier"),
    request: FeatureSuggestionRequest | None = None,
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
            feature_types=request.feature_types,
            user_id=current_user_id,
            read_cache=False,  # generator: write through so consumers resolve this set (#522)
        )

        logger.info(f"Generated {response.total_suggestions} suggestions for dataset {dataset_id}")
        if not response.metadata.get("ai_used"):
            # AI off, no key, or breaker open: no model was called, the reserved unit goes back (#461)
            await enforcement.release(http_request)
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
    dependencies=[Depends(quota("ai_calls"))],  # reaches suggest_features(include_ai) (#461)
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
            dataset_id=dataset_id,
            user_id=current_user_id,  # same tenant+dataset key as /suggest (#522)
            read_cache=True,  # lookup: resolve /suggest's current set, don't recompute
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
    # No quota: since #523 this reads the suggestion from the cache only and never
    # reaches a model, so metering it would burn a finite ai_calls unit on every
    # thumbs-up and could 402 legitimate /suggest calls (exempt in
    # test_ai_routes_are_metered.py).
    response_model=FeatureFeedbackResponse,
    summary="Record feedback on a suggestion",
    description="Record whether a user accepted or rejected a feature suggestion. This feedback is used to improve future suggestions."
)
async def record_suggestion_feedback(
    suggestion_id: str = Path(..., description="Suggestion identifier"),
    request: FeatureFeedbackRequest = Body(...),
    dataset_id: str = Query(..., description="Dataset identifier"),
    current_user_id: str = Depends(get_current_user_id)
) -> FeatureFeedbackResponse:
    """Record user feedback on a feature suggestion"""
    try:
        logger.info(f"Recording feedback for suggestion {suggestion_id}: accepted={request.accepted}")

        # Recording feedback must NOT download the whole dataset just to read one
        # field (#523) — that made a thumbs-up among the most expensive operations
        # and a trivial S3-egress amplifier. The suggestion (and its feature_type)
        # is already in the tenant+dataset cache /suggest wrote (#522); read it
        # directly. An expired set means feedback on a stale suggestion, which is
        # meaningless — answer 404 rather than reload the dataset.
        suggestions_response = await feature_engineering_service.get_cached_suggestions(
            current_user_id, dataset_id
        )
        suggestion = None
        if suggestions_response:
            suggestion = next(
                (s for s in suggestions_response.suggestions if s.id == suggestion_id),
                None,
            )

        if not suggestion:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Suggestion {suggestion_id} not found"
            )

        # Create feedback record with actual feature_type from suggestion
        feedback = FeatureFeedbackRecord(
            feedback_id=f"fb_{uuid.uuid4().hex[:12]}",
            suggestion_id=suggestion_id,
            user_id=current_user_id,
            dataset_id=dataset_id,
            feature_type=suggestion.feature_type,
            accepted=request.accepted,
            modified_parameters=request.modified_parameters,
            reason=request.reason,
            created_at=datetime.now(UTC)
        )

        # Record feedback
        success = await feature_engineering_service.record_feedback(feedback)

        if success:
            return FeatureFeedbackResponse(
                suggestion_id=suggestion_id,
                accepted=request.accepted,
                recorded_at=datetime.now(UTC),
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
    dependencies=[Depends(quota("ai_calls"))],  # reaches suggest_features(include_ai) (#461)
    response_model=FeatureSuggestionResponse,
    summary="Generate additional suggestions",
    description="Generate additional feature suggestions, excluding previously shown suggestions."
)
async def suggest_more_features(
    dataset_id: str = Path(..., description="Dataset identifier"),
    request: GenerateMoreRequest = Body(...),
    current_user_id: str = Depends(get_current_user_id)
) -> FeatureSuggestionResponse:
    """Generate additional feature suggestions"""
    try:
        logger.info(f"Generating additional suggestions for dataset {dataset_id}")

        # Load dataset
        df = await _load_dataset_dataframe(dataset_id, current_user_id)

        # Ensure list fields have safe defaults
        excluded_ids = request.excluded_suggestion_ids or []
        prefer_types = request.prefer_feature_types or []

        # The set already shown to the user (from the prior /suggest). The UI
        # APPENDS this endpoint's result to that list, so both batches must stay
        # resolvable by apply/feedback/explain — we merge, not replace (#522).
        existing = await feature_engineering_service.get_cached_suggestions(
            current_user_id, dataset_id
        )
        existing_suggestions = existing.suggestions if existing else []
        existing_ids = {s.id for s in existing_suggestions}

        # Compute a fresh batch WITHOUT clobbering the cached set (write_cache=False).
        response = await feature_engineering_service.suggest_features(
            df=df,
            dataset_id=dataset_id,
            target_column=request.target_column,
            problem_type=request.problem_type,
            max_suggestions=request.count + len(excluded_ids) + len(existing_ids),
            include_ai=True,
            feature_types=prefer_types if prefer_types else None,
            user_id=current_user_id,
            read_cache=False,
            write_cache=False,
        )

        # New ones: not excluded by the client, not already shown.
        new_suggestions = [
            s for s in response.suggestions
            if s.id not in excluded_ids and s.id not in existing_ids
        ][:request.count]

        # Persist the UNION so the original batch's ids keep resolving alongside
        # the new ones; return only the new batch (the UI appends it).
        response.suggestions = existing_suggestions + new_suggestions
        await feature_engineering_service.cache_suggestions(
            current_user_id, dataset_id, response
        )

        response.suggestions = new_suggestions
        response.total_suggestions = len(new_suggestions)

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
    dependencies=[Depends(quota("ai_calls"))],  # reaches suggest_features(include_ai) (#461)
    response_model=ApplyFeatureResponse,
    summary="Preview a feature suggestion",
    description="Compute a preview of a single feature suggestion. The new "
                "column is NOT saved to the dataset (preview-only, #274); use "
                "the transformation pipeline to persist changes."
)
async def apply_feature(
    dataset_id: str = Path(..., description="Dataset identifier"),
    request: ApplyFeatureRequest = Body(...),
    current_user_id: str = Depends(get_current_user_id)
) -> ApplyFeatureResponse:
    """Preview a single feature suggestion (not persisted — see #274)."""
    try:
        logger.info(f"Applying feature {request.suggestion_id} to dataset {dataset_id}")

        # Load dataset
        df = await _load_dataset_dataframe(dataset_id, current_user_id)

        # Get the suggestion
        suggestions_response = await feature_engineering_service.suggest_features(
            df=df,
            dataset_id=dataset_id,
            user_id=current_user_id,  # same tenant+dataset key as /suggest (#522)
            read_cache=True,  # lookup: resolve /suggest's current set, don't recompute
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
            persisted=False,  # preview-only (#274)
            applied_features=applied_features,
            failed_features=failed_features,
            new_column_count=len(applied_features),
            preview_data=preview,
            message=(
                f"Previewed {len(applied_features)} feature(s). "
                "Not saved to the dataset — use the transformation pipeline to persist."
            )
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
    dependencies=[Depends(quota("ai_calls"))],  # reaches suggest_features(include_ai) (#461)
    response_model=ApplyFeatureResponse,
    summary="Preview multiple feature suggestions",
    description="Compute a preview of multiple feature suggestions at once. The "
                "new columns are NOT saved to the dataset (preview-only, #274); "
                "use the transformation pipeline to persist changes."
)
async def apply_multiple_features(
    dataset_id: str = Path(..., description="Dataset identifier"),
    request: ApplyMultipleFeaturesRequest = Body(...),
    current_user_id: str = Depends(get_current_user_id)
) -> ApplyFeatureResponse:
    """Preview multiple feature suggestions (not persisted — see #274)."""
    try:
        logger.info(f"Applying {len(request.suggestion_ids)} features to dataset {dataset_id}")

        # Load dataset
        df = await _load_dataset_dataframe(dataset_id, current_user_id)

        # Get suggestions (fetched once, cached by service via Redis)
        suggestions_response = await feature_engineering_service.suggest_features(
            df=df,
            dataset_id=dataset_id,
            user_id=current_user_id,  # same tenant+dataset key as /suggest (#522)
            read_cache=True,  # lookup: resolve /suggest's current set, don't recompute
        )

        # Build lookup map for O(1) access per suggestion
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
            persisted=False,  # preview-only (#274)
            applied_features=applied_features,
            failed_features=failed_features,
            new_column_count=len(applied_features),
            preview_data=preview,
            message=(
                f"Previewed {len(applied_features)} of {len(request.suggestion_ids)} feature(s). "
                "Not saved to the dataset — use the transformation pipeline to persist."
            )
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
    parameters: dict | None = None
) -> str | None:
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
                # Safe division: add small epsilon to prevent division by zero
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
            logger.warning(
                f"Feature type '{feature_type.value}' not yet implemented for feature '{suggestion.name}'"
            )
            return None

    except Exception as e:
        raise ValueError(f"Failed to apply feature '{suggestion.name}' ({feature_type.value}): {str(e)}")
