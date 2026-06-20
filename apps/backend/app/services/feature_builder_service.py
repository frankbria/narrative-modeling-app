"""
Feature Builder Service for Visual Feature Builder.

This service handles CRUD operations for feature definitions and
provides preview/validation functionality using safe expression evaluation.
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd

from app.models.feature import (
    ExpressionNode,
    FeatureDefinition,
    FeatureStatistics,
    NodeType,
    OutputType,
)
from app.services.base_service import BaseService
from app.services.dataset_service import DatasetService
from app.services.exceptions import ValidationError
from app.services.expression_evaluator import (
    ColumnNotFoundError,
    ExpressionError,
    ExpressionEvaluator,
)
from app.services.transformation_engine.data_utils import (
    get_dataframe_from_s3,
    upload_dataframe_to_s3,
)

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

    async def preview_feature(
        self,
        dataset_id: str,
        user_id: str,
        expression_tree: ExpressionNode,
        sample_size: int = 100
    ) -> dict[str, Any]:
        """
        Preview a feature computation on sample data.

        Args:
            dataset_id: Dataset to preview on
            user_id: User requesting the preview
            expression_tree: Expression tree to evaluate
            sample_size: Number of rows to sample

        Returns:
            Dictionary with preview data, statistics, distribution, etc.
        """
        # Get dataset
        dataset = await self.dataset_service.get_dataset_or_raise(
            dataset_id=dataset_id,
            user_id=user_id,
            check_ownership=True
        )

        try:
            # Load sample data from S3
            df = await get_dataframe_from_s3(dataset.s3_url, nrows=sample_size)

            # Evaluate expression
            result_series, warnings = self.evaluator.evaluate(
                expression_tree=expression_tree,
                dataframe=df,
                feature_name="preview_feature"
            )

            # Calculate statistics
            stats = self._calculate_statistics(result_series)

            # Calculate distribution
            distribution = self._calculate_distribution(result_series)

            # Get sample data with feature
            sample_data = self._get_sample_data(df, result_series)

            # Get formula string
            formula = expression_tree.to_formula_string()

            # Infer output type
            inferred_type = self._infer_output_type(result_series)

            return {
                "success": True,
                "values": result_series.head(sample_size).tolist(),
                "statistics": stats,
                "distribution": distribution,
                "formula": formula,
                "input_columns": expression_tree.get_input_columns(),
                "inferred_type": inferred_type,
                "sample_data": sample_data,
                "warnings": warnings,
                "error": None
            }

        except ColumnNotFoundError as e:
            return {
                "success": False,
                "values": [],
                "statistics": None,
                "distribution": [],
                "formula": expression_tree.to_formula_string(),
                "input_columns": expression_tree.get_input_columns(),
                "inferred_type": "unknown",
                "sample_data": None,
                "warnings": [],
                "error": str(e)
            }
        except ExpressionError as e:
            return {
                "success": False,
                "values": [],
                "statistics": None,
                "distribution": [],
                "formula": expression_tree.to_formula_string(),
                "input_columns": expression_tree.get_input_columns(),
                "inferred_type": "unknown",
                "sample_data": None,
                "warnings": [],
                "error": str(e)
            }
        except Exception as e:
            logger.exception(f"Error previewing feature: {e}")
            return {
                "success": False,
                "values": [],
                "statistics": None,
                "distribution": [],
                "formula": expression_tree.to_formula_string(),
                "input_columns": expression_tree.get_input_columns(),
                "inferred_type": "unknown",
                "sample_data": None,
                "warnings": [],
                "error": f"Preview failed: {str(e)}"
            }

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

    def _calculate_distribution(
        self,
        series: pd.Series,
        num_bins: int = 10
    ) -> list[dict[str, Any]]:
        """Calculate distribution bins for a series."""
        if series.empty or series.isna().all():
            return []

        # Handle non-numeric series
        if not pd.api.types.is_numeric_dtype(series):
            # Return value counts for categorical data
            value_counts = series.value_counts().head(num_bins)
            return [
                {
                    "bin_start": 0,
                    "bin_end": 0,
                    "count": int(count),
                    "label": str(value)
                }
                for value, count in value_counts.items()
            ]

        # Numeric series - create histogram bins
        non_null = series.dropna()
        if non_null.empty:
            return []

        try:
            counts, bin_edges = np.histogram(non_null, bins=num_bins)
            distribution = []
            for i in range(len(counts)):
                distribution.append({
                    "bin_start": float(bin_edges[i]),
                    "bin_end": float(bin_edges[i + 1]),
                    "count": int(counts[i]),
                    "label": f"{bin_edges[i]:.2f} - {bin_edges[i + 1]:.2f}"
                })
            return distribution
        except Exception as e:
            logger.warning(f"Error calculating distribution: {e}")
            return []

    def _get_sample_data(
        self,
        df: pd.DataFrame,
        feature_series: pd.Series,
        max_rows: int = 10
    ) -> list[dict[str, Any]]:
        """Get sample data with computed feature column."""
        sample_df = df.head(max_rows).copy()
        sample_df["_computed_feature"] = feature_series.head(max_rows)

        # Convert to list of dicts, handling various types
        records = []
        for _, row in sample_df.iterrows():
            record = {}
            for col, val in row.items():
                if pd.isna(val):
                    record[col] = None
                elif isinstance(val, (np.integer, np.floating)):
                    record[col] = float(val) if isinstance(val, np.floating) else int(val)
                elif isinstance(val, (np.bool_)):
                    record[col] = bool(val)
                elif isinstance(val, pd.Timestamp):
                    record[col] = val.isoformat()
                else:
                    record[col] = str(val) if not isinstance(val, (str, int, float, bool)) else val
            records.append(record)
        return records

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

    async def validate_expression(
        self,
        dataset_id: str,
        user_id: str,
        expression_tree: ExpressionNode
    ) -> dict[str, Any]:
        """
        Validate an expression tree without full evaluation.

        Args:
            dataset_id: Dataset to validate against
            user_id: User requesting validation
            expression_tree: Expression tree to validate

        Returns:
            Validation result with errors, warnings, inferred type
        """
        # Get dataset
        dataset = await self.dataset_service.get_dataset_or_raise(
            dataset_id=dataset_id,
            user_id=user_id,
            check_ownership=True
        )

        # Build column type info from dataset schema
        column_info: dict[str, str] = {}
        for schema_field in dataset.data_schema:
            column_info[schema_field.field_name] = schema_field.field_type

        # Use evaluator's validation
        is_valid, errors, warnings, inferred_type = self.evaluator.validate_expression(
            expression_tree=expression_tree,
            column_info=column_info
        )

        # Additional validation: check columns exist
        missing_columns = self._validate_columns_exist(expression_tree, dataset.columns)
        if missing_columns:
            errors.extend(missing_columns)
            is_valid = False

        # Check for potential runtime issues
        potential_issues = self._check_potential_issues(expression_tree)

        return {
            "is_valid": is_valid,
            "errors": errors,
            "warnings": warnings,
            "inferred_type": inferred_type,
            "input_columns": expression_tree.get_input_columns(),
            "column_types": column_info,
            "type_compatibility": {},  # Could be enhanced
            "potential_issues": potential_issues
        }

    def _check_potential_issues(self, expression_tree: ExpressionNode) -> list[str]:
        """Check for potential runtime issues in the expression."""
        issues = []

        def check_node(node: ExpressionNode):
            if node.node_type == NodeType.OPERATION:
                op = str(node.value).lower()
                if op == "divide":
                    issues.append("Division operation may cause division by zero")
            elif node.node_type == NodeType.FUNCTION:
                func = str(node.value).lower()
                if func == "log":
                    issues.append("log() on non-positive values will produce -inf or NaN")
                elif func == "sqrt":
                    issues.append("sqrt() on negative values will produce NaN")

            for child in node.children:
                check_node(child)

        check_node(expression_tree)
        return issues

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

        Args:
            feature_id: Feature to apply
            user_id: User requesting the application
            output_column_name: Name for the new column (defaults to feature name)
            create_new_dataset: If True, create a new dataset; otherwise update existing

        Returns:
            Dictionary with result details including dataset_id and s3_url
        """
        # Get feature
        feature = await self.get_by_id_or_raise(
            resource_id=feature_id,
            user_id=user_id,
            check_ownership=True
        )

        # Get dataset
        dataset = await self.dataset_service.get_dataset_or_raise(
            dataset_id=feature.dataset_id,
            user_id=user_id,
            check_ownership=True
        )

        # Use feature name if no column name specified
        column_name = output_column_name or feature.name

        try:
            # Load full dataset
            df = await get_dataframe_from_s3(dataset.s3_url)

            # Evaluate expression
            result_series, warnings = self.evaluator.evaluate(
                expression_tree=feature.expression_tree,
                dataframe=df,
                feature_name=column_name
            )

            # Add column to dataframe
            df[column_name] = result_series

            # Calculate statistics
            stats = self._calculate_statistics(result_series)

            # Generate S3 key for the updated dataframe
            timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            if create_new_dataset:
                new_dataset_id = str(uuid.uuid4())
                s3_key = f"datasets/{user_id}/{new_dataset_id}/data_{timestamp}.parquet"
            else:
                s3_key = f"datasets/{user_id}/{dataset.dataset_id}/data_{timestamp}.parquet"

            # Upload modified dataframe to S3
            try:
                new_s3_url = await upload_dataframe_to_s3(df, s3_key)
            except Exception as upload_error:
                logger.exception(f"Failed to upload dataframe to S3: {upload_error}")
                return {
                    "success": False,
                    "dataset_id": feature.dataset_id,
                    "column_name": column_name,
                    "rows_computed": 0,
                    "null_values": 0,
                    "warnings": warnings,
                    "error": f"Failed to upload to S3: {str(upload_error)}",
                    "s3_url": None
                }

            # Handle dataset creation or update
            final_dataset_id = feature.dataset_id
            if create_new_dataset:
                # Create new dataset with copied metadata
                new_columns = list(dataset.columns) + [column_name]
                new_schema = list(dataset.data_schema)
                # Add schema field for new column
                from app.models.dataset import SchemaField
                new_schema.append(SchemaField(
                    field_name=column_name,
                    field_type=self._infer_output_type(result_series),
                    nullable=bool(stats["null_count"] > 0),
                    unique=bool(stats["unique_count"] == stats["total_count"])
                ))

                await self.dataset_service.create_dataset(
                    user_id=user_id,
                    dataset_id=new_dataset_id,
                    filename=f"{dataset.original_filename.rsplit('.', 1)[0]}_with_{column_name}.parquet",
                    original_filename=f"{dataset.original_filename.rsplit('.', 1)[0]}_with_{column_name}",
                    file_type="parquet",
                    file_path=s3_key,
                    s3_url=new_s3_url,
                    num_rows=len(df),
                    num_columns=len(new_columns),
                    columns=new_columns,
                    data_schema=new_schema,
                    file_size=None,  # Will be calculated by S3
                )
                final_dataset_id = new_dataset_id

                # Update feature to point to new dataset
                feature.dataset_id = new_dataset_id
            else:
                # Update existing dataset
                dataset.s3_url = new_s3_url
                dataset.columns = list(dataset.columns) + [column_name]
                dataset.num_columns = len(dataset.columns)
                # Add schema field for new column
                from app.models.dataset import SchemaField
                dataset.data_schema.append(SchemaField(
                    field_name=column_name,
                    field_type=self._infer_output_type(result_series),
                    nullable=bool(stats["null_count"] > 0),
                    unique=bool(stats["unique_count"] == stats["total_count"])
                ))
                await dataset.save()

            # Update feature statistics
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

            return {
                "success": True,
                "dataset_id": final_dataset_id,
                "column_name": column_name,
                "rows_computed": len(result_series),
                "null_values": stats["null_count"],
                "warnings": warnings,
                "error": None,
                "s3_url": new_s3_url
            }

        except Exception as e:
            logger.exception(f"Error applying feature: {e}")
            return {
                "success": False,
                "dataset_id": feature.dataset_id,
                "column_name": column_name,
                "rows_computed": 0,
                "null_values": 0,
                "warnings": [],
                "error": str(e),
                "s3_url": None
            }


# Create singleton instance
feature_builder_service = FeatureBuilderService()
