"""
Feature Builder Service for Visual Feature Builder.

This service handles CRUD operations for feature definitions and
provides preview/validation functionality using safe expression evaluation.
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pandas as pd

from app.models.feature import (
    ExpressionNode,
    FeatureDefinition,
    FeatureStatistics,
    OutputType,
)
from app.services.base_service import BaseService
from app.services.dataset_service import DatasetService
from app.services.exceptions import ValidationError
from app.services.expression_evaluator import (
    ExpressionEvaluator,
)
from app.services.transformation_engine.data_utils import (
    get_dataframe_from_s3,
    upload_parquet_bytes,
)
from app.services.transformation_engine.transformation_engine import TransformationType
from app.services.transformation_service import TransformationService

logger = logging.getLogger(__name__)


class FeatureBuilderService(BaseService[FeatureDefinition]):
    """
    Service for feature builder operations.

    Provides CRUD operations for feature definitions, preview/validation
    using the ExpressionEvaluator, and feature application to datasets.
    """

    model_class = FeatureDefinition
    resource_name = "Feature"

    def __init__(self):
        """Initialize the feature builder service."""
        self.evaluator = ExpressionEvaluator()
        self.dataset_service = DatasetService()

    def _get_id_field(self) -> str:
        """Return the unique identifier field name."""
        return "feature_id"

    async def create_feature(
        self,
        user_id: str,
        dataset_id: str,
        name: str,
        expression_tree: ExpressionNode,
        description: str | None = None,
        tags: list[str] | None = None,
        output_type: OutputType = OutputType.NUMERIC,
        canvas_state: dict[str, Any] | None = None,
    ) -> FeatureDefinition:
        """
        Create a new feature definition.

        Args:
            user_id: User who owns the feature
            dataset_id: Dataset this feature is for
            name: Feature name
            expression_tree: Root node of the expression tree
            description: Optional description
            tags: Optional tags for categorization
            output_type: Expected output type
            canvas_state: Optional canvas state for UI persistence

        Returns:
            Created FeatureDefinition

        Raises:
            ValidationError: If feature name already exists for dataset
            NotFoundError: If dataset doesn't exist
        """
        # Verify dataset exists and user has access
        dataset = await self.dataset_service.get_dataset_or_raise(
            dataset_id=dataset_id,
            user_id=user_id,
            check_ownership=True
        )

        # Check for duplicate name
        existing = await self._get_feature_by_name(dataset_id, name)
        if existing:
            raise ValidationError(
                message=f"Feature with name '{name}' already exists for this dataset",
                details={"name": name, "dataset_id": dataset_id}
            )

        # Generate unique feature ID
        feature_id = str(uuid.uuid4())

        # Create feature definition
        feature = FeatureDefinition(
            user_id=user_id,
            dataset_id=dataset_id,
            feature_id=feature_id,
            name=name,
            description=description,
            tags=tags or [],
            expression_tree=expression_tree,
            output_type=output_type,
            canvas_state=canvas_state,
        )

        # Validate expression
        validation_result = feature.validate_expression()

        # Validate against dataset columns
        if validation_result.is_valid:
            column_errors = self._validate_columns_exist(
                expression_tree, dataset.columns
            )
            if column_errors:
                validation_result.errors.extend(column_errors)
                validation_result.is_valid = False
                feature.is_valid = False
                feature.validation_result = validation_result

        await feature.save()
        return feature

    async def _get_feature_by_name(
        self,
        dataset_id: str,
        name: str
    ) -> FeatureDefinition | None:
        """Get feature by name within a dataset."""
        query = {
            "dataset_id": dataset_id,
            "name": name
        }
        return await FeatureDefinition.find_one(query)

    def _validate_columns_exist(
        self,
        expression_tree: ExpressionNode,
        available_columns: list[str]
    ) -> list[str]:
        """Validate that all referenced columns exist in the dataset."""
        input_columns = expression_tree.get_input_columns()
        missing = [col for col in input_columns if col not in available_columns]
        if missing:
            return [f"Column(s) not found in dataset: {missing}"]
        return []

    def _calculate_statistics(self, series: pd.Series) -> dict[str, Any]:
        """Calculate statistics for a series."""
        # Handle non-numeric series
        if not pd.api.types.is_numeric_dtype(series):
            return {
                "mean": None,
                "median": None,
                "std": None,
                "min": None,
                "max": None,
                "null_count": int(series.isna().sum()),
                "unique_count": int(series.nunique()),
                "total_count": len(series)
            }

        return {
            "mean": float(series.mean()) if not series.empty else None,
            "median": float(series.median()) if not series.empty else None,
            "std": float(series.std()) if not series.empty else None,
            "min": float(series.min()) if not series.empty else None,
            "max": float(series.max()) if not series.empty else None,
            "null_count": int(series.isna().sum()),
            "unique_count": int(series.nunique()),
            "total_count": len(series)
        }

    def _infer_output_type(self, series: pd.Series) -> str:
        """Infer the output type from a computed series."""
        if series.empty:
            return "unknown"

        dtype = series.dtype

        if pd.api.types.is_bool_dtype(dtype):
            return "boolean"
        elif pd.api.types.is_numeric_dtype(dtype):
            return "numeric"
        elif pd.api.types.is_datetime64_any_dtype(dtype):
            return "datetime"
        elif pd.api.types.is_string_dtype(dtype) or dtype is object:
            return "string"
        else:
            return "unknown"

    async def get_feature(
        self,
        feature_id: str,
        user_id: str
    ) -> FeatureDefinition:
        """Get a feature by ID."""
        return await self.get_by_id_or_raise(
            resource_id=feature_id,
            user_id=user_id,
            check_ownership=True
        )

    async def list_features(
        self,
        dataset_id: str,
        user_id: str,
        skip: int = 0,
        limit: int = 20,
        sort_field: str = "created_at",
        sort_ascending: bool = False
    ) -> tuple[list[FeatureDefinition], int]:
        """
        List features for a dataset.

        Args:
            dataset_id: Dataset to list features for
            user_id: User requesting the list
            skip: Number of records to skip
            limit: Maximum records to return
            sort_field: Field to sort by
            sort_ascending: Sort direction

        Returns:
            Tuple of (features list, total count)
        """
        # Verify dataset access
        await self.dataset_service.get_dataset_or_raise(
            dataset_id=dataset_id,
            user_id=user_id,
            check_ownership=True
        )

        # Get features
        features = await self.list_for_user(
            user_id=user_id,
            skip=skip,
            limit=limit,
            sort_field=sort_field,
            sort_ascending=sort_ascending,
            dataset_id=dataset_id
        )

        total = await self.count_for_user(user_id=user_id, dataset_id=dataset_id)

        return features, total

    async def update_feature(
        self,
        feature_id: str,
        user_id: str,
        name: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
        expression_tree: ExpressionNode | None = None,
        output_type: OutputType | None = None,
        canvas_state: dict[str, Any] | None = None
    ) -> FeatureDefinition:
        """
        Update a feature definition.

        Args:
            feature_id: Feature to update
            user_id: User requesting the update
            name: New name (optional)
            description: New description (optional)
            tags: New tags (optional)
            expression_tree: New expression tree (optional)
            output_type: New output type (optional)
            canvas_state: New canvas state (optional)

        Returns:
            Updated FeatureDefinition
        """
        feature = await self.get_by_id_or_raise(
            resource_id=feature_id,
            user_id=user_id,
            check_ownership=True
        )

        # Check name uniqueness if changing
        if name and name != feature.name:
            existing = await self._get_feature_by_name(feature.dataset_id, name)
            if existing and str(existing.id) != str(feature.id):
                raise ValidationError(
                    message=f"Feature with name '{name}' already exists",
                    details={"name": name}
                )
            feature.name = name

        # Update fields
        if description is not None:
            feature.description = description
        if tags is not None:
            feature.tags = tags
        if output_type is not None:
            feature.output_type = output_type
        if canvas_state is not None:
            feature.canvas_state = canvas_state

        # If expression tree changed, revalidate
        if expression_tree is not None:
            feature.expression_tree = expression_tree
            feature.validate_expression()

            # Also validate columns
            dataset = await self.dataset_service.get_dataset(
                dataset_id=feature.dataset_id,
                check_ownership=False
            )
            if dataset:
                column_errors = self._validate_columns_exist(
                    expression_tree, dataset.columns
                )
                if column_errors and feature.validation_result:
                    feature.validation_result.errors.extend(column_errors)
                    feature.validation_result.is_valid = False
                    feature.is_valid = False

        feature.update_timestamp()
        await feature.save()

        return feature

    async def delete_feature(
        self,
        feature_id: str,
        user_id: str
    ) -> bool:
        """Delete a feature definition."""
        return await self.delete(
            resource_id=feature_id,
            user_id=user_id,
            soft_delete=False
        )

    async def apply_feature_to_dataset(
        self,
        feature_id: str,
        user_id: str,
        output_column_name: str | None = None,
        create_new_dataset: bool = False
    ) -> dict[str, Any]:
        """
        Apply a feature to the dataset, adding the computed column and persisting to S3.

        Added in place, the column is one step of the dataset's transformation history,
        so undo removes it (#923). With `create_new_dataset` it is a new dataset.

        Args:
            feature_id: Feature to apply
            user_id: User requesting the application
            output_column_name: Name for the new column (defaults to feature name)
            create_new_dataset: If True, create a new dataset; otherwise update existing

        Returns:
            Dictionary with result details including dataset_id and s3_url, built by
            `_apply_result`. `dataset_committed` says whether a NEW dataset has been
            persisted, apart from `success`: a failure after `create_dataset()` leaves a
            real dataset in both id-spaces, and the caller meters on it (#459).
        """
        feature = await self.get_by_id_or_raise(resource_id=feature_id, user_id=user_id, check_ownership=True)
        dataset = await self.dataset_service.get_dataset_or_raise(
            dataset_id=feature.dataset_id, user_id=user_id, check_ownership=True
        )
        column_name = output_column_name or feature.name
        try:
            before = await get_dataframe_from_s3(dataset.s3_url)
            result_series, warnings = self.evaluator.evaluate(
                expression_tree=feature.expression_tree, dataframe=before, feature_name=column_name
            )
            column = _Column(column_name, result_series, warnings, self._calculate_statistics(result_series))
            if create_new_dataset:
                return await self._apply_as_new_dataset(feature, dataset, user_id, before, column)
            return await self._apply_in_place(feature, dataset, user_id, before, column)
        except Exception as e:
            logger.exception(f"Error applying feature: {e}")
            return _apply_result(committed=False, dataset_id=feature.dataset_id, column_name=column_name, error=str(e))

    def _schema_field(self, column: "_Column") -> Any:
        from app.models.dataset import SchemaField

        return SchemaField(
            field_name=column.name,
            field_type=self._infer_output_type(column.series),
            inferred_dtype=str(column.series.dtype),
            unique_values=int(column.stats["unique_count"]),
            missing_values=int(column.stats["null_count"]),
        )

    async def _apply_in_place(
        self, feature: FeatureDefinition, dataset: Any, user_id: str, before: pd.DataFrame, column: "_Column"
    ) -> dict[str, Any]:
        """Add the column to the dataset as one history step (#923). The caller (the
        route) holds the dataset's lease; the move takes its twin along (#467)."""
        dataset.data_schema.append(self._schema_field(column))
        new_s3_url = await TransformationService().record_edit(
            dataset, user_id, (before, before.assign(**{column.name: column.series})),
            kind=TransformationType.FEATURE_COLUMN.value,
            parameters={"columns": [column.name], "feature_id": feature.feature_id},
            description=f"Added feature column {column.name}",
        )
        return await self._applied(feature, column, new_s3_url, committed=False)

    async def _apply_as_new_dataset(
        self, feature: FeatureDefinition, dataset: Any, user_id: str, before: pd.DataFrame, column: "_Column"
    ) -> dict[str, Any]:
        """A new dataset: the source's file with the column added."""
        df = before.assign(**{column.name: column.series})
        new_dataset_id = str(uuid.uuid4())
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        s3_key = f"datasets/{user_id}/{new_dataset_id}/data_{timestamp}.parquet"
        try:
            parquet = await asyncio.to_thread(df.to_parquet, index=False)
            new_s3_url = await upload_parquet_bytes(parquet, s3_key)
        except Exception as upload_error:
            logger.exception(f"Failed to upload dataframe to S3: {upload_error}")
            return _apply_result(
                committed=False, dataset_id=feature.dataset_id, column_name=column.name,
                warnings=column.warnings, error=f"Failed to upload to S3: {str(upload_error)}",
            )
        stem = dataset.original_filename.rsplit('.', 1)[0]
        await self.dataset_service.create_dataset(
            user_id=user_id,
            dataset_id=new_dataset_id,
            filename=f"{stem}_with_{column.name}.parquet",
            original_filename=f"{stem}_with_{column.name}",
            file_type="parquet",
            file_path=s3_key,
            s3_url=new_s3_url,
            num_rows=len(df),
            num_columns=len(dataset.columns) + 1,
            columns=list(dataset.columns) + [column.name],
            data_schema=list(dataset.data_schema) + [self._schema_field(column)],
            file_size=len(parquet),  # what the storage ceiling counts (#768)
        )
        # Update feature to point to new dataset
        feature.dataset_id = new_dataset_id
        try:
            return await self._applied(feature, column, new_s3_url, committed=True)
        except Exception as e:
            logger.exception(f"Error applying feature: {e}")
            return _apply_result(committed=True, dataset_id=new_dataset_id, column_name=column.name, error=str(e))

    async def _applied(
        self, feature: FeatureDefinition, column: "_Column", s3_url: str, *, committed: bool
    ) -> dict[str, Any]:
        """Record the column's statistics on the feature; the success answer."""
        stats = column.stats
        feature.statistics = FeatureStatistics(
            mean=stats["mean"],
            median=stats["median"],
            std=stats["std"],
            min_value=stats["min"],
            max_value=stats["max"],
            null_count=stats["null_count"],
            unique_count=stats["unique_count"],
            total_count=stats["total_count"]
        )
        await feature.save()
        return _apply_result(
            committed=committed, dataset_id=feature.dataset_id, column_name=column.name, warnings=column.warnings,
            rows_computed=len(column.series), null_values=stats["null_count"], s3_url=s3_url,
        )


@dataclass
class _Column:
    """The column a feature computed: its name, values, the evaluator's warnings, and statistics."""

    name: str
    series: pd.Series
    warnings: list[str]
    stats: dict[str, Any]


def _apply_result(
    *, committed: bool, dataset_id: str, column_name: str, warnings: list[str] | None = None,
    error: str | None = None, rows_computed: int = 0, null_values: int = 0, s3_url: str | None = None,
) -> dict[str, Any]:
    """What `apply_feature_to_dataset` answers. `committed` is required: the route meters
    on `dataset_committed`, so no answer may leave it to a default (#459)."""
    return {
        "success": error is None,
        "dataset_committed": committed,
        "dataset_id": dataset_id,
        "column_name": column_name,
        "rows_computed": rows_computed,
        "null_values": null_values,
        "warnings": warnings or [],
        "error": error,
        "s3_url": s3_url,
    }


# Create singleton instance
feature_builder_service = FeatureBuilderService()
