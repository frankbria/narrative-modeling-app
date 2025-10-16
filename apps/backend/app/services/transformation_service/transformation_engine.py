"""
Core transformation engine for data pipeline
"""
from typing import Dict, Any, List, Optional, Tuple
from abc import ABC, abstractmethod
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from enum import Enum
import logging
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class TransformationType(str, Enum):
    """Types of transformations available"""
    # Data Cleaning
    REMOVE_DUPLICATES = "remove_duplicates"
    TRIM_WHITESPACE = "trim_whitespace"
    FIX_CASING = "fix_casing"
    REMOVE_SPECIAL_CHARS = "remove_special_chars"
    STANDARDIZE_FORMAT = "standardize_format"
    
    # Missing Values
    DROP_MISSING = "drop_missing"
    FILL_MISSING = "fill_missing"
    IMPUTE_MEAN = "impute_mean"
    IMPUTE_MEDIAN = "impute_median"
    IMPUTE_MODE = "impute_mode"
    IMPUTE_FORWARD = "impute_forward"
    IMPUTE_BACKWARD = "impute_backward"
    
    # Type Conversions
    TO_NUMERIC = "to_numeric"
    TO_STRING = "to_string"
    TO_DATETIME = "to_datetime"
    TO_BOOLEAN = "to_boolean"
    ONE_HOT_ENCODE = "one_hot_encode"
    LABEL_ENCODE = "label_encode"
    
    # Date/Time
    EXTRACT_DATE_PARTS = "extract_date_parts"
    CALCULATE_AGE = "calculate_age"
    CREATE_CYCLICAL = "create_cyclical"
    
    # Custom
    FORMULA = "formula"
    CONDITIONAL = "conditional"
    REGEX_REPLACE = "regex_replace"


class TransformationResult(BaseModel):
    """Result of a transformation operation"""
    success: bool
    transformed_data: Optional[List[Dict[str, Any]]] = None
    affected_rows: int = 0
    affected_columns: List[str] = Field(default_factory=list)
    preview_data: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    stats_before: Optional[Dict[str, Any]] = None
    stats_after: Optional[Dict[str, Any]] = None


class BaseTransformation(ABC):
    """Base class for all transformations"""
    
    def __init__(self, parameters: Dict[str, Any]):
        self.parameters = parameters
        self.validate_parameters()
    
    @abstractmethod
    def validate_parameters(self) -> None:
        """Validate transformation parameters"""
        pass
    
    @abstractmethod
    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply transformation to dataframe"""
        pass
    
    @abstractmethod
    def preview(self, df: pd.DataFrame, n_rows: int = 100) -> pd.DataFrame:
        """Preview transformation on subset of data"""
        pass
    
    def get_affected_columns(self, df: pd.DataFrame) -> List[str]:
        """Get list of columns that will be affected"""
        return []
    
    def validate_data(self, df: pd.DataFrame) -> Tuple[bool, Optional[str]]:
        """Validate if transformation can be applied to data"""
        return True, None


class RemoveDuplicatesTransformation(BaseTransformation):
    """Remove duplicate rows from dataset"""
    
    def validate_parameters(self) -> None:
        self.subset = self.parameters.get('subset', None)
        self.keep = self.parameters.get('keep', 'first')
        
        if self.keep not in ['first', 'last', False]:
            raise ValueError("keep must be 'first', 'last', or False")
    
    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        return df.drop_duplicates(subset=self.subset, keep=self.keep)
    
    def preview(self, df: pd.DataFrame, n_rows: int = 100) -> pd.DataFrame:
        preview_df = df.head(n_rows).copy()
        return self.apply(preview_df)
    
    def get_affected_columns(self, df: pd.DataFrame) -> List[str]:
        return self.subset if self.subset else df.columns.tolist()


class TrimWhitespaceTransformation(BaseTransformation):
    """Trim whitespace from string columns"""

    def validate_parameters(self) -> None:
        self.columns = self.parameters.get('columns', [])

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        # Optimization: Use copy-on-write and vectorized operations
        df_copy = df.copy()

        if not self.columns:
            # Apply to all string columns
            string_cols = df.select_dtypes(include=['object']).columns.tolist()
        else:
            string_cols = self.columns

        # Optimization: Vectorize string operations across all columns at once
        for col in string_cols:
            if col in df.columns:
                # Vectorized string strip - faster than iterating
                df_copy[col] = df_copy[col].astype(str).str.strip()

        return df_copy
    
    def preview(self, df: pd.DataFrame, n_rows: int = 100) -> pd.DataFrame:
        return self.apply(df.head(n_rows).copy())
    
    def get_affected_columns(self, df: pd.DataFrame) -> List[str]:
        if not self.columns:
            return df.select_dtypes(include=['object']).columns.tolist()
        return [col for col in self.columns if col in df.columns]


class DropMissingTransformation(BaseTransformation):
    """Drop rows with missing values"""

    def validate_parameters(self) -> None:
        self.columns = self.parameters.get('columns', None)
        self.threshold = self.parameters.get('threshold', None)
        self.how = self.parameters.get('how', 'any')

        if self.threshold is not None:
            if not isinstance(self.threshold, (int, float)):
                raise ValueError("threshold must be numeric")
            if self.threshold < 0 or self.threshold > 100:
                raise ValueError("threshold must be between 0 and 100")

        if self.how not in ['any', 'all']:
            raise ValueError("how must be 'any' or 'all'")

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df

        # Optimization: Use vectorized operations for threshold-based dropping
        if self.threshold is not None:
            cols_to_check = self.columns if self.columns else df.columns.tolist()

            # Vectorized calculation of missing percentage per row
            missing_pct = (df[cols_to_check].isnull().sum(axis=1) / len(cols_to_check)) * 100

            # Vectorized boolean indexing - faster than iteration
            return df[missing_pct < self.threshold].copy()

        # Optimization: Use pandas built-in dropna for standard strategies (already optimized)
        return df.dropna(subset=self.columns, how=self.how)

    def preview(self, df: pd.DataFrame, n_rows: int = 100) -> pd.DataFrame:
        preview_df = df.head(n_rows).copy()
        return self.apply(preview_df)

    def get_affected_columns(self, df: pd.DataFrame) -> List[str]:
        if not self.columns:
            return [col for col in df.columns if df[col].isnull().any()]
        return [col for col in self.columns if col in df.columns and df[col].isnull().any()]

    def validate_data(self, df: pd.DataFrame) -> Tuple[bool, Optional[str]]:
        """Validate if transformation can be applied to data"""
        if df.empty:
            return False, "Cannot drop missing values from empty dataset"

        # Calculate how many rows would be dropped
        if self.threshold is not None:
            cols_to_check = self.columns if self.columns else df.columns.tolist()
            missing_pct = (df[cols_to_check].isnull().sum(axis=1) / len(cols_to_check)) * 100
            rows_to_drop = (missing_pct >= self.threshold).sum()
        else:
            if self.how == 'any':
                rows_to_drop = df[self.columns if self.columns else df.columns].isnull().any(axis=1).sum()
            else:  # 'all'
                rows_to_drop = df[self.columns if self.columns else df.columns].isnull().all(axis=1).sum()

        data_loss_pct = (rows_to_drop / len(df)) * 100

        # Warn if data loss is significant
        if data_loss_pct > 50:
            return False, f"Dropping missing values would result in {data_loss_pct:.1f}% data loss ({rows_to_drop}/{len(df)} rows). This exceeds the 50% safety threshold."

        if rows_to_drop == len(df):
            return False, "Dropping missing values would remove all rows from the dataset"

        return True, None


class FillMissingTransformation(BaseTransformation):
    """Fill missing values with specified value or strategy"""

    def validate_parameters(self) -> None:
        self.columns = self.parameters.get('columns', [])
        self.value = self.parameters.get('value', None)
        self.method = self.parameters.get('method', None)

        if self.value is None and self.method is None:
            raise ValueError("Either 'value' or 'method' must be specified")

        if self.method and self.method not in ['mean', 'median', 'mode', 'ffill', 'bfill']:
            raise ValueError(f"Invalid method: {self.method}")

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        # Optimization: Use copy-on-write
        df_copy = df.copy()

        cols_to_fill = self.columns if self.columns else df.columns.tolist()

        # Optimization: Batch similar operations together
        if self.value is not None:
            # Vectorized fill for all columns at once
            for col in cols_to_fill:
                if col in df.columns:
                    df_copy[col] = df_copy[col].fillna(self.value)
        elif self.method in ['mean', 'median']:
            # Optimization: Calculate statistics once for numeric columns
            numeric_cols = [col for col in cols_to_fill if col in df.columns and pd.api.types.is_numeric_dtype(df_copy[col])]
            if numeric_cols:
                if self.method == 'mean':
                    fill_values = df_copy[numeric_cols].mean()
                else:  # median
                    fill_values = df_copy[numeric_cols].median()
                df_copy[numeric_cols] = df_copy[numeric_cols].fillna(fill_values)
        elif self.method == 'mode':
            for col in cols_to_fill:
                if col in df.columns:
                    mode_val = df_copy[col].mode()
                    if len(mode_val) > 0:
                        df_copy[col] = df_copy[col].fillna(mode_val[0])
        elif self.method == 'ffill':
            # Vectorized forward fill
            for col in cols_to_fill:
                if col in df.columns:
                    df_copy[col] = df_copy[col].fillna(method='ffill')
        elif self.method == 'bfill':
            # Vectorized backward fill
            for col in cols_to_fill:
                if col in df.columns:
                    df_copy[col] = df_copy[col].fillna(method='bfill')

        return df_copy

    def preview(self, df: pd.DataFrame, n_rows: int = 100) -> pd.DataFrame:
        return self.apply(df.head(n_rows).copy())

    def get_affected_columns(self, df: pd.DataFrame) -> List[str]:
        if not self.columns:
            return [col for col in df.columns if df[col].isnull().any()]
        return [col for col in self.columns if col in df.columns and df[col].isnull().any()]


class TransformationEngine:
    """Main engine for executing transformations"""

    TRANSFORMATION_CLASSES = {
        TransformationType.REMOVE_DUPLICATES: RemoveDuplicatesTransformation,
        TransformationType.TRIM_WHITESPACE: TrimWhitespaceTransformation,
        TransformationType.DROP_MISSING: DropMissingTransformation,
        TransformationType.FILL_MISSING: FillMissingTransformation,
    }

    def __init__(self):
        self.history: List[Dict[str, Any]] = []
        # Optimization: Cache for preview statistics to avoid recalculation
        self._stats_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_max_size = 100  # Limit cache size to prevent memory bloat
    
    def create_transformation(
        self,
        transformation_type: TransformationType,
        parameters: Dict[str, Any]
    ) -> BaseTransformation:
        """Create a transformation instance"""
        if transformation_type not in self.TRANSFORMATION_CLASSES:
            raise ValueError(f"Unknown transformation type: {transformation_type}")
        
        transformation_class = self.TRANSFORMATION_CLASSES[transformation_type]
        return transformation_class(parameters)
    
    def validate_transformation(
        self,
        df: pd.DataFrame,
        transformation_type: TransformationType,
        parameters: Dict[str, Any]
    ) -> TransformationResult:
        """
        Validate transformation configuration before application.

        Validates:
        - Parameter correctness
        - Data type compatibility
        - Column existence
        - Data loss implications
        """
        try:
            # Create transformation to validate parameters
            transformation = self.create_transformation(transformation_type, parameters)

            # Validate data compatibility
            is_valid, error = transformation.validate_data(df)
            if not is_valid:
                return TransformationResult(
                    success=False,
                    error=error
                )

            warnings = []

            # Validate column existence
            affected_columns = transformation.get_affected_columns(df)
            missing_columns = [col for col in affected_columns if col not in df.columns]
            if missing_columns:
                return TransformationResult(
                    success=False,
                    error=f"Columns not found in dataset: {', '.join(missing_columns)}"
                )

            # Check data types for type-specific transformations
            if transformation_type in [TransformationType.IMPUTE_MEAN, TransformationType.IMPUTE_MEDIAN]:
                columns_param = parameters.get('columns', [])
                for col in columns_param:
                    if col in df.columns and not pd.api.types.is_numeric_dtype(df[col]):
                        return TransformationResult(
                            success=False,
                            error=f"Column '{col}' must be numeric for {transformation_type.value}"
                        )

            # Estimate data loss for drop operations
            if transformation_type == TransformationType.DROP_MISSING:
                threshold = parameters.get('threshold')
                how = parameters.get('how', 'any')
                columns = parameters.get('columns')

                if threshold is not None:
                    cols_to_check = columns if columns else df.columns.tolist()
                    missing_pct = (df[cols_to_check].isnull().sum(axis=1) / len(cols_to_check)) * 100
                    rows_to_drop = (missing_pct >= threshold).sum()
                else:
                    if how == 'any':
                        rows_to_drop = df[columns if columns else df.columns].isnull().any(axis=1).sum()
                    else:
                        rows_to_drop = df[columns if columns else df.columns].isnull().all(axis=1).sum()

                data_loss_pct = (rows_to_drop / len(df)) * 100 if len(df) > 0 else 0
                if data_loss_pct > 25:
                    warnings.append(f"Warning: This operation will drop {data_loss_pct:.1f}% of rows ({rows_to_drop}/{len(df)})")

            return TransformationResult(
                success=True,
                affected_columns=affected_columns,
                warnings=warnings
            )

        except ValueError as e:
            return TransformationResult(
                success=False,
                error=f"Invalid parameters: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Transformation validation failed: {str(e)}")
            return TransformationResult(
                success=False,
                error=f"Validation error: {str(e)}"
            )

    def preview_transformation(
        self,
        df: pd.DataFrame,
        transformation_type: TransformationType,
        parameters: Dict[str, Any],
        n_rows: int = 100
    ) -> TransformationResult:
        """Preview a transformation on subset of data"""
        try:
            # Validate transformation first
            validation_result = self.validate_transformation(df, transformation_type, parameters)
            if not validation_result.success:
                return validation_result

            # Create transformation
            transformation = self.create_transformation(transformation_type, parameters)

            # Validate data
            is_valid, error = transformation.validate_data(df)
            if not is_valid:
                return TransformationResult(
                    success=False,
                    error=error
                )

            # Get stats before
            stats_before = self._calculate_stats(df.head(n_rows))

            # Apply transformation to preview
            preview_df = transformation.preview(df, n_rows)

            # Get stats after
            stats_after = self._calculate_stats(preview_df)

            # Calculate affected rows
            affected_rows = abs(len(df.head(n_rows)) - len(preview_df))

            return TransformationResult(
                success=True,
                preview_data=preview_df.to_dict('records'),
                affected_rows=affected_rows,
                affected_columns=transformation.get_affected_columns(df),
                stats_before=stats_before,
                stats_after=stats_after,
                warnings=validation_result.warnings
            )

        except Exception as e:
            logger.error(f"Preview transformation failed: {str(e)}")
            return TransformationResult(
                success=False,
                error=str(e)
            )
    
    def apply_transformation(
        self,
        df: pd.DataFrame,
        transformation_type: TransformationType,
        parameters: Dict[str, Any]
    ) -> TransformationResult:
        """Apply transformation to full dataset"""
        try:
            # Edge case: Empty dataset
            if df.empty:
                return TransformationResult(
                    success=False,
                    error="Cannot apply transformation to empty dataset"
                )

            # Edge case: Single row dataset
            if len(df) == 1:
                logger.warning("Applying transformation to single-row dataset")

            # Validate transformation configuration first
            validation_result = self.validate_transformation(df, transformation_type, parameters)
            if not validation_result.success:
                return validation_result

            # Create transformation
            transformation = self.create_transformation(transformation_type, parameters)

            # Validate data
            is_valid, error = transformation.validate_data(df)
            if not is_valid:
                return TransformationResult(
                    success=False,
                    error=error
                )

            # Store original shape
            original_shape = df.shape

            # Apply transformation
            transformed_df = transformation.apply(df)

            # Edge case: Check if transformation resulted in empty dataset
            if transformed_df.empty and not df.empty:
                return TransformationResult(
                    success=False,
                    error="Transformation removed all rows from dataset. Operation aborted."
                )

            # Calculate changes
            affected_rows = abs(original_shape[0] - transformed_df.shape[0])
            affected_columns = transformation.get_affected_columns(df)

            # Collect warnings from validation
            warnings = validation_result.warnings.copy() if validation_result.warnings else []

            # Add to history
            self.history.append({
                'timestamp': datetime.now(timezone.utc),
                'type': transformation_type,
                'parameters': parameters,
                'affected_rows': affected_rows,
                'affected_columns': affected_columns
            })

            return TransformationResult(
                success=True,
                transformed_data=transformed_df.to_dict('records'),
                affected_rows=affected_rows,
                affected_columns=affected_columns,
                warnings=warnings
            )

        except Exception as e:
            logger.error(f"Apply transformation failed: {str(e)}")
            return TransformationResult(
                success=False,
                error=str(e)
            )
    
    def _calculate_stats(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculate basic statistics for dataframe with caching.

        Optimization: Cache stats for small dataframes to avoid recalculation
        in preview operations.
        """
        # Create cache key based on dataframe shape and first few values
        cache_key = f"{df.shape}_{id(df)}"

        # Check cache first (optimization for repeated preview calls)
        if cache_key in self._stats_cache:
            return self._stats_cache[cache_key]

        # Optimization: Vectorized statistics calculation
        stats = {
            'row_count': len(df),
            'column_count': len(df.columns),
            'missing_values': df.isnull().sum().to_dict(),
            'dtypes': df.dtypes.astype(str).to_dict()
        }

        # Add numeric stats - only for numeric columns (optimization)
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 0:
            stats['numeric_summary'] = df[numeric_cols].describe().to_dict()

        # Cache for small dataframes (previews) - limit cache size
        if len(df) <= 1000:  # Only cache small dataframes
            if len(self._stats_cache) >= self._cache_max_size:
                # Remove oldest entry (simple FIFO eviction)
                self._stats_cache.pop(next(iter(self._stats_cache)))
            self._stats_cache[cache_key] = stats

        return stats
    
    def get_history(self) -> List[Dict[str, Any]]:
        """Get transformation history"""
        return self.history
    
    def clear_history(self) -> None:
        """Clear transformation history"""
        self.history = []