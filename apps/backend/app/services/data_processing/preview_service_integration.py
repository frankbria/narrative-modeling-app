"""
Preview Service Integration for transformation previews.

This service orchestrates the complete preview workflow:
1. Load sample data from S3
2. Apply transformations sequentially
3. Calculate impact statistics
4. Return preview result with before/after data

Integrates:
- TransformationEngine (for applying transformations)
- PreviewService (for calculating impact statistics)
- S3 data loading (for fetching dataset samples)
"""

import asyncio
import logging
from typing import List, Optional

from app.schemas.transformation import TransformationStepRequest
from app.schemas.preview import PreviewResult, ImpactStatistics
from app.services.transformation_engine.transformation_engine import TransformationEngine
from app.services.data_processing.preview_service import PreviewService
from app.services.transformation_engine.data_utils import get_dataframe_from_s3

logger = logging.getLogger(__name__)


class PreviewServiceIntegration:
    """
    Service for generating transformation previews.

    Orchestrates the complete preview workflow from data loading to impact calculation.
    """

    def __init__(
        self,
        transformation_engine: Optional[TransformationEngine] = None,
        preview_service: Optional[PreviewService] = None
    ):
        """
        Initialize preview service integration.

        Args:
            transformation_engine: Optional TransformationEngine instance
            preview_service: Optional PreviewService instance
        """
        self.transformation_engine = transformation_engine or TransformationEngine()
        self.preview_service = preview_service or PreviewService()

    async def generate_preview(
        self,
        user_id: str,
        dataset_id: str,
        s3_file_path: str,
        operations: List[TransformationStepRequest],
        sample_size: int = 100
    ) -> PreviewResult:
        """
        Generate a complete transformation preview.

        Workflow:
        1. Load sample data from S3 (limited by sample_size)
        2. Apply transformations sequentially via TransformationEngine
        3. Calculate impact statistics via PreviewService
        4. Return PreviewResult with original/transformed data and impact stats

        Args:
            user_id: User ID (for logging/caching)
            dataset_id: Dataset ID (for logging/caching)
            s3_file_path: S3 URL or path to the dataset file
            operations: List of transformation operations to apply
            sample_size: Number of rows to sample for preview (10-1000)

        Returns:
            PreviewResult with original_data, transformed_data, impact_stats, warnings, errors

        Raises:
            ValueError: If operations list is empty, sample_size is invalid, dataset not owned by user, or S3 path mismatch
            Exception: If data loading or transformation fails
        """
        logger.info(
            f"Generating preview for dataset {dataset_id} "
            f"(user={user_id}, operations={len(operations)}, sample_size={sample_size})"
        )

        # Validate inputs
        if not operations:
            raise ValueError("Operations list cannot be empty")

        if sample_size < 10 or sample_size > 1000:
            raise ValueError("Sample size must be between 10 and 1000")

        # CRITICAL SECURITY CHECK: Verify user owns this dataset
        from app.models.dataset import DatasetMetadata
        dataset = await DatasetMetadata.find_one({
            "dataset_id": dataset_id,
            "user_id": user_id
        })

        if not dataset:
            logger.error(f"Dataset {dataset_id} not found or not owned by user {user_id}")
            raise ValueError(f"Dataset {dataset_id} not found or not owned by user {user_id}")

        # Verify S3 path matches dataset's stored path
        expected_path = dataset.file_path or dataset.s3_url
        if expected_path != s3_file_path:
            logger.error(
                f"S3 path mismatch for dataset {dataset_id}: "
                f"expected {expected_path}, got {s3_file_path}"
            )
            raise ValueError("S3 path mismatch - potential security violation")

        warnings: List[str] = []
        errors: List[str] = []

        try:
            # SECURITY: Enforce 30-second timeout for entire preview generation to prevent DoS
            async with asyncio.timeout(30.0):
                # Step 1: Load sample data from S3
                logger.info(f"Loading {sample_size} rows from S3: {s3_file_path}")
                original_df = await get_dataframe_from_s3(s3_file_path, nrows=sample_size)

                if original_df.empty:
                    raise ValueError("Dataset is empty or could not be loaded")

                # Limit to sample_size if we got more rows than expected
                if len(original_df) > sample_size:
                    original_df = original_df.head(sample_size)

                logger.info(
                    f"Loaded {len(original_df)} rows, {len(original_df.columns)} columns"
                )

                # Step 2: Apply transformations sequentially
                transformed_df = original_df.copy()

                for idx, operation in enumerate(operations):
                    try:
                        logger.info(
                            f"Applying transformation {idx+1}/{len(operations)}: "
                            f"{operation.transformation_type}"
                        )

                        # Apply transformation with change tracking
                        transformed_df, changed_cells = (
                            await self.transformation_engine.preview_transformation_step(
                                transformed_df,
                                operation,
                                track_changes=True  # Enable change tracking for highlighting
                            )
                        )

                        # Note: changed_cells could be used for cell-level highlighting in UI
                        # For now, we don't include it in the response, but we could add it
                        # to PreviewResult if needed

                        logger.info(
                            f"Transformation {idx+1} applied successfully. "
                            f"Result: {len(transformed_df)} rows"
                        )

                    except Exception as e:
                        error_msg = (
                            f"Transformation '{operation.transformation_type}' failed: {str(e)}"
                        )
                        logger.error(error_msg)
                        errors.append(error_msg)
                        break  # Stop processing on first error

                # If all transformations failed, return early
                if errors and transformed_df.equals(original_df):
                    return PreviewResult(
                        original_data=original_df.to_dict('records'),
                        transformed_data=original_df.to_dict('records'),
                        impact_stats=ImpactStatistics(
                            rows_affected=0,
                            values_changed=0,
                            columns_affected=[],
                            quality_score_before=0.5,
                            quality_score_after=0.5,
                            value_distributions={}
                        ),
                        warnings=warnings,
                        errors=errors
                    )

                # Step 3: Calculate impact statistics
                logger.info("Calculating impact statistics")

                try:
                    impact_stats = await self.preview_service.calculate_impact(
                        original_df,
                        transformed_df
                    )
                except Exception as e:
                    logger.warning(f"Failed to calculate impact statistics: {e}")
                    # Provide fallback impact stats
                    impact_stats = ImpactStatistics(
                        rows_affected=0,
                        values_changed=0,
                        columns_affected=[],
                        quality_score_before=0.5,
                        quality_score_after=0.5,
                        value_distributions={}
                    )
                    warnings.append(f"Could not calculate detailed impact statistics: {str(e)}")

                # Step 4: Build and return PreviewResult
                logger.info("Preview generation complete")

                return PreviewResult(
                    original_data=original_df.to_dict('records'),
                    transformed_data=transformed_df.to_dict('records'),
                    impact_stats=impact_stats,
                    warnings=warnings,
                    errors=errors
                )

        except asyncio.TimeoutError:
            # Timeout exceeded - prevent DoS
            logger.error(f"Preview generation timeout (30s) for dataset {dataset_id}")
            raise ValueError(
                "Preview timeout (30s). Try reducing sample_size or simplifying transformations."
            )

        except ValueError as e:
            # Re-raise validation errors
            logger.error(f"Validation error in preview generation: {e}")
            raise

        except Exception as e:
            # Catch-all for unexpected errors
            logger.error(f"Unexpected error in preview generation: {e}")
            raise Exception(f"Preview generation failed: {str(e)}")


# Singleton instance for use in API routes
preview_service = PreviewServiceIntegration()
