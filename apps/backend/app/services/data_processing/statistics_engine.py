"""
Statistics calculation engine for comprehensive data profiling
"""

from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import pandas as pd
import numpy as np
from scipy import stats
from pydantic import BaseModel, Field


class ColumnStatistics(BaseModel):
    """Comprehensive statistics for a single column"""
    column_name: str
    data_type: str
    
    # Basic counts
    total_count: int
    null_count: int
    null_percentage: float
    unique_count: int
    unique_percentage: float
    
    # Numeric statistics (if applicable)
    mean: Optional[float] = None
    median: Optional[float] = None
    mode: Optional[Any] = None
    std_dev: Optional[float] = None
    variance: Optional[float] = None
    min_value: Optional[Union[float, str]] = None
    max_value: Optional[Union[float, str]] = None
    range: Optional[float] = None
    
    # Quartiles and percentiles
    q1: Optional[float] = None
    q3: Optional[float] = None
    iqr: Optional[float] = None
    percentile_5: Optional[float] = None
    percentile_95: Optional[float] = None
    
    # Distribution metrics
    skewness: Optional[float] = None
    kurtosis: Optional[float] = None
    
    # Outlier detection
    outlier_count: Optional[int] = None
    outlier_percentage: Optional[float] = None
    lower_fence: Optional[float] = None
    upper_fence: Optional[float] = None
    
    # String/categorical statistics
    avg_length: Optional[float] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    most_frequent_values: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Date/time statistics
    earliest_date: Optional[str] = None
    latest_date: Optional[str] = None
    date_range_days: Optional[int] = None


class DatasetStatistics(BaseModel):
    """Statistics for entire dataset"""
    row_count: int
    column_count: int
    memory_usage_mb: float
    column_statistics: List[ColumnStatistics]
    correlation_matrix: Optional[Dict[str, Dict[str, float]]] = None
    missing_value_summary: Dict[str, Any] = Field(default_factory=dict)
    calculated_at: datetime = Field(default_factory=datetime.utcnow)


class StatisticsEngine:
    """Engine for calculating comprehensive statistics on datasets"""
    
    def __init__(self, outlier_method: str = "iqr", correlation_threshold: float = 0.7):
        """
        Initialize statistics engine
        
        Args:
            outlier_method: Method for outlier detection ('iqr' or 'zscore')
            correlation_threshold: Threshold for flagging high correlations
        """
        self.outlier_method = outlier_method
        self.correlation_threshold = correlation_threshold

    async def calculate_statistics(self, df: pd.DataFrame, column_types: Dict[str, str]) -> DatasetStatistics:
        """
        Calculate comprehensive statistics for a dataset
        
        Args:
            df: Input DataFrame
            column_types: Dictionary mapping column names to data types
            
        Returns:
            DatasetStatistics object with all calculated metrics
        """
        column_stats = []
        
        for col_name in df.columns:
            col_type = column_types.get(col_name, "unknown")
            stats = await self._calculate_column_statistics(df[col_name], col_name, col_type)
            column_stats.append(stats)
        
        # Calculate correlation matrix for numeric columns
        numeric_cols = [col for col in df.columns 
                       if column_types.get(col, "").lower() in ["integer", "float", "currency", "percentage"]]
        
        correlation_matrix = None
        if len(numeric_cols) > 1:
            correlation_matrix = self._calculate_correlation_matrix(df[numeric_cols])
        
        # Missing value summary
        missing_summary = self._calculate_missing_value_summary(df)
        
        # Memory usage
        memory_usage_mb = df.memory_usage(deep=True).sum() / 1024 / 1024
        
        return DatasetStatistics(
            row_count=len(df),
            column_count=len(df.columns),
            memory_usage_mb=float(memory_usage_mb),
            column_statistics=column_stats,
            correlation_matrix=correlation_matrix,
            missing_value_summary=missing_summary
        )

    async def _calculate_column_statistics(self, series: pd.Series, col_name: str, col_type: str) -> ColumnStatistics:
        """Calculate statistics for a single column"""
        stats = ColumnStatistics(
            column_name=col_name,
            data_type=col_type,
            total_count=len(series),
            null_count=int(series.isna().sum()),
            null_percentage=float(series.isna().sum() / len(series) * 100),
            unique_count=int(series.nunique()),
            unique_percentage=float(series.nunique() / len(series) * 100)
        )
        
        # Get non-null series for further analysis
        non_null = series.dropna()
        
        if len(non_null) == 0:
            return stats
        
        # Calculate type-specific statistics
        if col_type.lower() in ["integer", "float", "currency", "percentage"]:
            await self._add_numeric_statistics(non_null, stats)
        elif col_type.lower() in ["date", "datetime"]:
            await self._add_datetime_statistics(non_null, stats)
        elif col_type.lower() in ["string", "text", "categorical", "email", "phone", "url"]:
            await self._add_string_statistics(non_null, stats)
        
        # Most frequent values for all types
        value_counts = non_null.value_counts().head(10)
        stats.most_frequent_values = [
            {"value": str(value), "count": int(count), "percentage": float(count / len(non_null) * 100)}
            for value, count in value_counts.items()
        ]
        
        # Mode (most common value)
        mode_values = non_null.mode()
        if len(mode_values) > 0:
            stats.mode = mode_values.iloc[0]
        
        return stats

    async def _add_numeric_statistics(self, series: pd.Series, stats: ColumnStatistics):
        """Add numeric-specific statistics"""
        try:
            # Convert to numeric if needed
            if stats.data_type.lower() == "currency":
                numeric_series = series.astype(str).str.replace(r'[$€£¥,]', '', regex=True)
                numeric_series = pd.to_numeric(numeric_series, errors='coerce').dropna()
            elif stats.data_type.lower() == "percentage":
                numeric_series = series.astype(str).str.replace('%', '', regex=False)
                numeric_series = pd.to_numeric(numeric_series, errors='coerce').dropna() / 100
            else:
                numeric_series = pd.to_numeric(series, errors='coerce').dropna()
            
            if len(numeric_series) == 0:
                return
            
            # Basic statistics
            stats.mean = float(numeric_series.mean())
            stats.median = float(numeric_series.median())
            stats.std_dev = float(numeric_series.std())
            stats.variance = float(numeric_series.var())
            stats.min_value = float(numeric_series.min())
            stats.max_value = float(numeric_series.max())
            stats.range = float(stats.max_value - stats.min_value)
            
            # Quartiles and percentiles
            stats.q1 = float(numeric_series.quantile(0.25))
            stats.q3 = float(numeric_series.quantile(0.75))
            stats.iqr = float(stats.q3 - stats.q1)
            stats.percentile_5 = float(numeric_series.quantile(0.05))
            stats.percentile_95 = float(numeric_series.quantile(0.95))
            
            # Distribution metrics
            if len(numeric_series) >= 3:
                stats.skewness = float(numeric_series.skew())
                stats.kurtosis = float(numeric_series.kurtosis())
            
            # Outlier detection
            if self.outlier_method == "iqr":
                stats.lower_fence = stats.q1 - 1.5 * stats.iqr
                stats.upper_fence = stats.q3 + 1.5 * stats.iqr
                outliers = (numeric_series < stats.lower_fence) | (numeric_series > stats.upper_fence)
            else:  # z-score method
                from scipy import stats as scipy_stats
                z_scores = np.abs(scipy_stats.zscore(numeric_series))
                outliers = z_scores > 3
                stats.lower_fence = stats.mean - 3 * stats.std_dev
                stats.upper_fence = stats.mean + 3 * stats.std_dev
            
            stats.outlier_count = int(outliers.sum())
            stats.outlier_percentage = float(outliers.sum() / len(numeric_series) * 100)
            
        except Exception as e:
            # Log error but don't fail
            print(f"Error calculating numeric statistics for {stats.column_name}: {e}")

    async def _add_datetime_statistics(self, series: pd.Series, stats: ColumnStatistics):
        """Add datetime-specific statistics"""
        try:
            # Convert to datetime
            datetime_series = pd.to_datetime(series, errors='coerce').dropna()
            
            if len(datetime_series) == 0:
                return
            
            stats.earliest_date = datetime_series.min().isoformat()
            stats.latest_date = datetime_series.max().isoformat()
            
            # Calculate date range in days
            date_range = datetime_series.max() - datetime_series.min()
            stats.date_range_days = date_range.days
            
            # For numeric statistics on datetime, convert to timestamp
            timestamp_series = datetime_series.astype(np.int64) / 10**9  # Convert to seconds
            
            stats.mean = float(pd.to_datetime(timestamp_series.mean(), unit='s').isoformat())
            stats.median = float(pd.to_datetime(timestamp_series.median(), unit='s').isoformat())
            
        except Exception as e:
            print(f"Error calculating datetime statistics for {stats.column_name}: {e}")

    async def _add_string_statistics(self, series: pd.Series, stats: ColumnStatistics):
        """Add string-specific statistics"""
        try:
            str_series = series.astype(str)
            lengths = str_series.str.len()
            
            stats.avg_length = float(lengths.mean())
            stats.min_length = int(lengths.min())
            stats.max_length = int(lengths.max())
            
        except Exception as e:
            print(f"Error calculating string statistics for {stats.column_name}: {e}")

    def _calculate_correlation_matrix(self, df: pd.DataFrame) -> Dict[str, Dict[str, float]]:
        """Calculate correlation matrix for numeric columns"""
        try:
            # Calculate correlations
            corr_matrix = df.corr()
            
            # Convert to nested dictionary
            result = {}
            for col1 in corr_matrix.columns:
                result[col1] = {}
                for col2 in corr_matrix.columns:
                    correlation = corr_matrix.loc[col1, col2]
                    if not pd.isna(correlation):
                        result[col1][col2] = float(correlation)
            
            return result
        except:
            return {}

    def _calculate_missing_value_summary(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate summary of missing values across dataset"""
        missing_counts = df.isna().sum()
        missing_percentages = (missing_counts / len(df) * 100).round(2)
        
        return {
            "total_missing_values": int(missing_counts.sum()),
            "columns_with_missing": int((missing_counts > 0).sum()),
            "complete_columns": int((missing_counts == 0).sum()),
            "missing_by_column": {
                col: {
                    "count": int(count),
                    "percentage": float(missing_percentages[col])
                }
                for col, count in missing_counts.items() if count > 0
            },
            "missing_patterns": self._analyze_missing_patterns(df)
        }

    def _analyze_missing_patterns(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze patterns in missing data"""
        # Check for rows with all missing values
        all_missing_rows = df.isna().all(axis=1).sum()
        
        # Check for rows with any missing values
        any_missing_rows = df.isna().any(axis=1).sum()
        
        # Most common missing value combinations
        missing_mask = df.isna()
        pattern_counts = missing_mask.value_counts().head(5)
        
        patterns = []
        for pattern, count in pattern_counts.items():
            if any(pattern):  # Only include patterns with at least one missing value
                missing_cols = [col for col, is_missing in zip(df.columns, pattern) if is_missing]
                patterns.append({
                    "columns": missing_cols,
                    "count": int(count),
                    "percentage": float(count / len(df) * 100)
                })
        
        return {
            "rows_with_all_missing": int(all_missing_rows),
            "rows_with_any_missing": int(any_missing_rows),
            "complete_rows": int(len(df) - any_missing_rows),
            "common_patterns": patterns
        }