"""
Core transformation engine for data pipeline
"""
from typing import Dict, Any, List, Optional, Tuple
from abc import ABC, abstractmethod
import pandas as pd
import numpy as np
from datetime import datetime
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
        df_copy = df.copy()
        
        if not self.columns:
            # Apply to all string columns
            string_cols = df.select_dtypes(include=['object']).columns.tolist()
        else:
            string_cols = self.columns
        
        for col in string_cols:
            if col in df.columns:
                df_copy[col] = df_copy[col].astype(str).str.strip()
        
        return df_copy
    
    def preview(self, df: pd.DataFrame, n_rows: int = 100) -> pd.DataFrame:
        return self.apply(df.head(n_rows).copy())
    
    def get_affected_columns(self, df: pd.DataFrame) -> List[str]:
        if not self.columns:
            return df.select_dtypes(include=['object']).columns.tolist()
        return [col for col in self.columns if col in df.columns]


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
        df_copy = df.copy()
        
        cols_to_fill = self.columns if self.columns else df.columns.tolist()
        
        for col in cols_to_fill:
            if col not in df.columns:
                continue
                
            if self.value is not None:
                df_copy[col] = df_copy[col].fillna(self.value)
            elif self.method == 'mean':
                if pd.api.types.is_numeric_dtype(df_copy[col]):
                    df_copy[col] = df_copy[col].fillna(df_copy[col].mean())
            elif self.method == 'median':
                if pd.api.types.is_numeric_dtype(df_copy[col]):
                    df_copy[col] = df_copy[col].fillna(df_copy[col].median())
            elif self.method == 'mode':
                mode_val = df_copy[col].mode()
                if len(mode_val) > 0:
                    df_copy[col] = df_copy[col].fillna(mode_val[0])
            elif self.method == 'ffill':
                df_copy[col] = df_copy[col].fillna(method='ffill')
            elif self.method == 'bfill':
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
        TransformationType.FILL_MISSING: FillMissingTransformation,
    }
    
    def __init__(self):
        self.history: List[Dict[str, Any]] = []
    
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
    
    def preview_transformation(
        self,
        df: pd.DataFrame,
        transformation_type: TransformationType,
        parameters: Dict[str, Any],
        n_rows: int = 100
    ) -> TransformationResult:
        """Preview a transformation on subset of data"""
        try:
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
            affected_rows = len(preview_df[preview_df.index != df.head(n_rows).index])
            
            return TransformationResult(
                success=True,
                preview_data=preview_df.to_dict('records'),
                affected_rows=affected_rows,
                affected_columns=transformation.get_affected_columns(df),
                stats_before=stats_before,
                stats_after=stats_after
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
            
            # Calculate changes
            affected_rows = abs(original_shape[0] - transformed_df.shape[0])
            affected_columns = transformation.get_affected_columns(df)
            
            # Add to history
            self.history.append({
                'timestamp': datetime.utcnow(),
                'type': transformation_type,
                'parameters': parameters,
                'affected_rows': affected_rows,
                'affected_columns': affected_columns
            })
            
            return TransformationResult(
                success=True,
                transformed_data=transformed_df.to_dict('records'),
                affected_rows=affected_rows,
                affected_columns=affected_columns
            )
            
        except Exception as e:
            logger.error(f"Apply transformation failed: {str(e)}")
            return TransformationResult(
                success=False,
                error=str(e)
            )
    
    def _calculate_stats(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate basic statistics for dataframe"""
        stats = {
            'row_count': len(df),
            'column_count': len(df.columns),
            'missing_values': df.isnull().sum().to_dict(),
            'dtypes': df.dtypes.astype(str).to_dict()
        }
        
        # Add numeric stats
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 0:
            stats['numeric_summary'] = df[numeric_cols].describe().to_dict()
        
        return stats
    
    def get_history(self) -> List[Dict[str, Any]]:
        """Get transformation history"""
        return self.history
    
    def clear_history(self) -> None:
        """Clear transformation history"""
        self.history = []