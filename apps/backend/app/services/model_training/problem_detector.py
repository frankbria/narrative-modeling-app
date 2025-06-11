"""
Problem type detection for AutoML
"""

from enum import Enum
from typing import Dict, Any, Optional, Tuple
import pandas as pd
import numpy as np
from dataclasses import dataclass


class ProblemType(Enum):
    """Types of ML problems supported"""
    BINARY_CLASSIFICATION = "binary_classification"
    MULTICLASS_CLASSIFICATION = "multiclass_classification"
    REGRESSION = "regression"
    TIME_SERIES_REGRESSION = "time_series_regression"
    TIME_SERIES_CLASSIFICATION = "time_series_classification"
    CLUSTERING = "clustering"
    UNKNOWN = "unknown"


@dataclass
class ProblemDetectionResult:
    """Result of problem type detection"""
    problem_type: ProblemType
    target_column: Optional[str]
    confidence: float
    reasoning: str
    metadata: Dict[str, Any]


class ProblemDetector:
    """Automatically detect the type of ML problem from data"""
    
    def __init__(self):
        self.min_samples = 10
        self.categorical_threshold = 0.05  # 5% of total samples
        self.time_series_freq_threshold = 0.8  # 80% regular intervals
    
    async def detect_problem_type(
        self,
        df: pd.DataFrame,
        target_column: Optional[str] = None,
        datetime_column: Optional[str] = None
    ) -> ProblemDetectionResult:
        """
        Detect the type of ML problem based on data characteristics
        
        Args:
            df: Input dataframe
            target_column: Target column if specified
            datetime_column: Datetime column if specified
            
        Returns:
            ProblemDetectionResult with detected problem type
        """
        # If no target specified, try to infer it
        if not target_column:
            target_column = self._infer_target_column(df)
        
        # Check if we have enough data
        if len(df) < self.min_samples:
            return ProblemDetectionResult(
                problem_type=ProblemType.UNKNOWN,
                target_column=target_column,
                confidence=0.0,
                reasoning=f"Not enough samples ({len(df)} < {self.min_samples})",
                metadata={"sample_count": len(df)}
            )
        
        # If no target column, consider clustering
        if not target_column:
            return ProblemDetectionResult(
                problem_type=ProblemType.CLUSTERING,
                target_column=None,
                confidence=0.8,
                reasoning="No target column specified or inferred - suggesting clustering",
                metadata={"features": list(df.columns)}
            )
        
        # Check if target exists
        if target_column not in df.columns:
            return ProblemDetectionResult(
                problem_type=ProblemType.UNKNOWN,
                target_column=target_column,
                confidence=0.0,
                reasoning=f"Target column '{target_column}' not found in data",
                metadata={"available_columns": list(df.columns)}
            )
        
        # Analyze target column
        target_series = df[target_column]
        is_numeric = pd.api.types.is_numeric_dtype(target_series)
        unique_count = target_series.nunique()
        
        # Check for time series
        if datetime_column or self._has_datetime_index(df):
            if is_numeric:
                return ProblemDetectionResult(
                    problem_type=ProblemType.TIME_SERIES_REGRESSION,
                    target_column=target_column,
                    confidence=0.9,
                    reasoning="Numeric target with datetime information suggests time series regression",
                    metadata={
                        "datetime_column": datetime_column,
                        "target_type": str(target_series.dtype),
                        "has_datetime_index": self._has_datetime_index(df)
                    }
                )
            else:
                return ProblemDetectionResult(
                    problem_type=ProblemType.TIME_SERIES_CLASSIFICATION,
                    target_column=target_column,
                    confidence=0.85,
                    reasoning="Categorical target with datetime information suggests time series classification",
                    metadata={
                        "datetime_column": datetime_column,
                        "unique_values": unique_count,
                        "has_datetime_index": self._has_datetime_index(df)
                    }
                )
        
        # Classification vs Regression
        if is_numeric:
            # Check if it's actually categorical (e.g., 0/1, class IDs)
            if self._is_numeric_categorical(target_series):
                if unique_count == 2:
                    return ProblemDetectionResult(
                        problem_type=ProblemType.BINARY_CLASSIFICATION,
                        target_column=target_column,
                        confidence=0.95,
                        reasoning="Numeric target with 2 unique values suggests binary classification",
                        metadata={
                            "unique_values": unique_count,
                            "value_counts": target_series.value_counts().to_dict()
                        }
                    )
                else:
                    return ProblemDetectionResult(
                        problem_type=ProblemType.MULTICLASS_CLASSIFICATION,
                        target_column=target_column,
                        confidence=0.9,
                        reasoning=f"Numeric target with {unique_count} discrete values suggests multiclass classification",
                        metadata={
                            "unique_values": unique_count,
                            "value_counts": target_series.value_counts().to_dict()
                        }
                    )
            else:
                # Continuous numeric target
                return ProblemDetectionResult(
                    problem_type=ProblemType.REGRESSION,
                    target_column=target_column,
                    confidence=0.95,
                    reasoning="Continuous numeric target suggests regression",
                    metadata={
                        "target_stats": {
                            "mean": float(target_series.mean()),
                            "std": float(target_series.std()),
                            "min": float(target_series.min()),
                            "max": float(target_series.max())
                        }
                    }
                )
        else:
            # Categorical target
            if unique_count == 2:
                return ProblemDetectionResult(
                    problem_type=ProblemType.BINARY_CLASSIFICATION,
                    target_column=target_column,
                    confidence=0.95,
                    reasoning="Categorical target with 2 unique values suggests binary classification",
                    metadata={
                        "unique_values": unique_count,
                        "value_counts": target_series.value_counts().to_dict()
                    }
                )
            else:
                return ProblemDetectionResult(
                    problem_type=ProblemType.MULTICLASS_CLASSIFICATION,
                    target_column=target_column,
                    confidence=0.95,
                    reasoning=f"Categorical target with {unique_count} unique values suggests multiclass classification",
                    metadata={
                        "unique_values": unique_count,
                        "value_counts": target_series.value_counts().head(10).to_dict()
                    }
                )
    
    def _infer_target_column(self, df: pd.DataFrame) -> Optional[str]:
        """Try to infer the target column from column names"""
        # Common target column names
        target_patterns = [
            'target', 'label', 'class', 'outcome', 'result',
            'y', 'dependent', 'response', 'output'
        ]
        
        # Check exact matches first
        for col in df.columns:
            if col.lower() in target_patterns:
                return col
        
        # Check partial matches
        for col in df.columns:
            col_lower = col.lower()
            for pattern in target_patterns:
                if pattern in col_lower:
                    return col
        
        # Check if last column might be target (common convention)
        if len(df.columns) > 1:
            last_col = df.columns[-1]
            # Only if it has reasonable cardinality
            if df[last_col].nunique() < len(df) * 0.5:
                return last_col
        
        return None
    
    def _has_datetime_index(self, df: pd.DataFrame) -> bool:
        """Check if dataframe has datetime index"""
        return isinstance(df.index, pd.DatetimeIndex)
    
    def _is_numeric_categorical(self, series: pd.Series) -> bool:
        """Check if numeric column is actually categorical"""
        if not pd.api.types.is_numeric_dtype(series):
            return False
        
        unique_count = series.nunique()
        total_count = len(series)
        
        # Check if values are integers
        if series.dtype in ['int64', 'int32', 'int16', 'int8']:
            # Check cardinality ratio
            if unique_count / total_count < self.categorical_threshold:
                return True
            # Check if sequential (0, 1, 2, ...)
            if unique_count < 50:  # Reasonable upper limit for classes
                unique_vals = sorted(series.dropna().unique())
                if unique_vals == list(range(len(unique_vals))):
                    return True
        
        # Check for binary 0/1
        if set(series.dropna().unique()) == {0, 1}:
            return True
        
        return False