"""
Schema inference service for automatic data type detection and validation
"""

import re
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from enum import Enum
import pandas as pd
import numpy as np
from pydantic import BaseModel, Field, ConfigDict


class DataType(str, Enum):
    """Supported data types for schema inference"""
    INTEGER = "integer"
    FLOAT = "float"
    STRING = "string"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    TIME = "time"
    EMAIL = "email"
    PHONE = "phone"
    URL = "url"
    CURRENCY = "currency"
    PERCENTAGE = "percentage"
    CATEGORICAL = "categorical"
    TEXT = "text"
    JSON = "json"
    UNKNOWN = "unknown"


class ColumnSchema(BaseModel):
    """Schema definition for a single column"""
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={
            np.integer: lambda v: int(v),
            np.floating: lambda v: float(v),
            np.ndarray: lambda v: v.tolist(),
            np.bool_: lambda v: bool(v)
        }
    )
    
    name: str
    data_type: DataType
    nullable: bool = True
    unique: bool = False
    cardinality: int = 0
    sample_values: List[Any] = Field(default_factory=list)
    format_pattern: Optional[str] = None
    min_value: Optional[Union[float, str]] = None
    max_value: Optional[Union[float, str]] = None
    mean_value: Optional[float] = None
    most_common_value: Optional[Any] = None
    null_count: int = 0
    null_percentage: float = 0.0


class SchemaDefinition(BaseModel):
    """Complete schema definition for a dataset"""
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={
            np.integer: lambda v: int(v),
            np.floating: lambda v: float(v),
            np.ndarray: lambda v: v.tolist(),
            np.bool_: lambda v: bool(v)
        }
    )
    
    columns: List[ColumnSchema]
    row_count: int
    column_count: int
    file_type: str
    inferred_at: datetime = Field(default_factory=datetime.utcnow)
    inference_confidence: float = 0.0


class SchemaInferenceService:
    """Service for inferring data types and schema from datasets"""
    
    # Regex patterns for special data types
    EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    PHONE_PATTERN = re.compile(r'^[\+]?[(]?\d{1,4}[)]?[-\s\.]?\d{1,4}[-\s\.]?\d{1,4}[-\s\.]?\d{1,9}$')
    URL_PATTERN = re.compile(r'^https?://[^\s]+$')
    CURRENCY_PATTERN = re.compile(r'^[$€£¥]\s*[\d,]+\.?\d*$|^[\d,]+\.?\d*\s*[$€£¥]$')
    PERCENTAGE_PATTERN = re.compile(r'^\d+\.?\d*\s*%$')
    
    # Common date formats to try
    DATE_FORMATS = [
        '%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y/%m/%d',
        '%d-%m-%Y', '%m-%d-%Y', '%Y%m%d', '%d.%m.%Y',
        '%B %d, %Y', '%b %d, %Y', '%d %B %Y', '%d %b %Y'
    ]
    
    DATETIME_FORMATS = [
        '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%dT%H:%M:%S',
        '%d/%m/%Y %H:%M:%S', '%m/%d/%Y %H:%M:%S', '%Y/%m/%d %H:%M:%S',
        '%Y-%m-%d %I:%M:%S %p', '%Y-%m-%d %I:%M %p'
    ]
    
    TIME_FORMATS = [
        '%H:%M:%S', '%H:%M', '%I:%M:%S %p', '%I:%M %p'
    ]
    
    @staticmethod
    def _convert_numpy_type(value: Any) -> Any:
        """Convert numpy types to Python native types"""
        if isinstance(value, np.integer):
            return int(value)
        elif isinstance(value, np.floating):
            return float(value)
        elif isinstance(value, np.ndarray):
            return value.tolist()
        elif isinstance(value, np.bool_):
            return bool(value)
        return value

    def __init__(self, sample_size: int = 1000):
        """
        Initialize schema inference service
        
        Args:
            sample_size: Number of rows to sample for type inference
        """
        self.sample_size = sample_size

    async def infer_schema(self, df: pd.DataFrame, file_type: str = "csv") -> SchemaDefinition:
        """
        Infer schema from a pandas DataFrame
        
        Args:
            df: Input DataFrame
            file_type: Type of the original file
            
        Returns:
            SchemaDefinition with inferred types and metadata
        """
        columns = []
        total_confidence = 0.0
        
        for col_name in df.columns:
            col_schema = await self._infer_column_schema(df[col_name], col_name)
            columns.append(col_schema)
            total_confidence += self._calculate_type_confidence(df[col_name], col_schema.data_type)
        
        return SchemaDefinition(
            columns=columns,
            row_count=len(df),
            column_count=len(df.columns),
            file_type=file_type,
            inference_confidence=total_confidence / len(columns) if columns else 0.0
        )

    async def _infer_column_schema(self, series: pd.Series, col_name: str) -> ColumnSchema:
        """Infer schema for a single column"""
        # Basic statistics
        null_count = series.isna().sum()
        non_null_series = series.dropna()
        
        if len(non_null_series) == 0:
            return ColumnSchema(
                name=col_name,
                data_type=DataType.UNKNOWN,
                nullable=True,
                null_count=null_count,
                null_percentage=100.0
            )
        
        # Sample for type inference
        sample = non_null_series.head(self.sample_size)
        
        # Detect data type
        data_type = await self._detect_data_type(sample)
        
        # Calculate additional metadata
        unique_count = non_null_series.nunique()
        is_unique = unique_count == len(non_null_series)
        
        # Get sample values
        sample_values = [self._convert_numpy_type(val) for val in non_null_series.value_counts().head(5).index.tolist()]
        
        # Get min/max for numeric/date types
        min_value = None
        max_value = None
        mean_value = None
        
        if data_type in [DataType.INTEGER, DataType.FLOAT, DataType.CURRENCY, DataType.PERCENTAGE]:
            clean_series = self._clean_numeric_series(non_null_series, data_type)
            if len(clean_series) > 0:
                min_value = float(clean_series.min())
                max_value = float(clean_series.max())
                mean_value = float(clean_series.mean())
        elif data_type in [DataType.DATE, DataType.DATETIME]:
            date_series = pd.to_datetime(non_null_series, errors='coerce').dropna()
            if len(date_series) > 0:
                min_value = date_series.min().isoformat()
                max_value = date_series.max().isoformat()
        
        # Most common value
        most_common = non_null_series.mode()
        most_common_value = self._convert_numpy_type(most_common.iloc[0]) if len(most_common) > 0 else None
        
        return ColumnSchema(
            name=col_name,
            data_type=data_type,
            nullable=null_count > 0,
            unique=is_unique,
            cardinality=unique_count,
            sample_values=sample_values,
            min_value=min_value,
            max_value=max_value,
            mean_value=mean_value,
            most_common_value=most_common_value,
            null_count=int(null_count),
            null_percentage=float(null_count / len(series) * 100)
        )

    async def _detect_data_type(self, sample: pd.Series) -> DataType:
        """Detect the data type of a column based on sample values"""
        # Check for pandas datetime types first
        if pd.api.types.is_datetime64_any_dtype(sample):
            # Check if times are meaningful (not all midnight)
            if hasattr(sample, 'dt'):
                if (sample.dt.hour != 0).any() or (sample.dt.minute != 0).any():
                    return DataType.DATETIME
                else:
                    return DataType.DATE
            return DataType.DATETIME
        
        # Convert to string for pattern matching
        str_sample = sample.astype(str)
        
        # Check for boolean
        if self._is_boolean(sample):
            return DataType.BOOLEAN
        
        # Check for numeric types
        if self._is_integer(sample):
            return DataType.INTEGER
        elif self._is_float(sample):
            return DataType.FLOAT
        
        # Check for date/time types BEFORE pattern matching
        # This prevents dates like "2023-01-01" from being detected as phone numbers
        date_type = self._detect_datetime_type(sample)
        if date_type:
            return date_type
        
        # Check for special string patterns
        if self._matches_pattern(str_sample, self.EMAIL_PATTERN, 0.9):
            return DataType.EMAIL
        elif self._matches_pattern(str_sample, self.PHONE_PATTERN, 0.9):
            return DataType.PHONE
        elif self._matches_pattern(str_sample, self.URL_PATTERN, 0.9):
            return DataType.URL
        elif self._matches_pattern(str_sample, self.CURRENCY_PATTERN, 0.9):
            return DataType.CURRENCY
        elif self._matches_pattern(str_sample, self.PERCENTAGE_PATTERN, 0.9):
            return DataType.PERCENTAGE
        
        # Check for categorical vs text
        unique_ratio = sample.nunique() / len(sample)
        avg_length = str_sample.str.len().mean()
        
        if unique_ratio < 0.5 and avg_length < 50:
            return DataType.CATEGORICAL
        elif avg_length > 70:  # Lowered threshold for text detection
            return DataType.TEXT
        else:
            return DataType.STRING

    def _is_boolean(self, sample: pd.Series) -> bool:
        """Check if column contains boolean values"""
        try:
            # Check for explicit boolean values
            if sample.dtype == bool:
                return True
            
            # Check for boolean-like strings
            str_sample = sample.astype(str).str.lower()
            bool_values = {'true', 'false', 'yes', 'no', '1', '0', 't', 'f', 'y', 'n'}
            return all(val in bool_values for val in str_sample.unique())
        except:
            return False

    def _is_integer(self, sample: pd.Series) -> bool:
        """Check if column contains integer values"""
        try:
            # Skip datetime columns
            if pd.api.types.is_datetime64_any_dtype(sample):
                return False
            
            # Try to convert to numeric
            numeric = pd.to_numeric(sample, errors='coerce')
            if numeric.isna().sum() > len(sample) * 0.1:  # More than 10% failed
                return False
            
            # Check if all values are integers
            return (numeric.dropna() == numeric.dropna().astype(int)).all()
        except:
            return False

    def _is_float(self, sample: pd.Series) -> bool:
        """Check if column contains float values"""
        try:
            # Skip datetime columns
            if pd.api.types.is_datetime64_any_dtype(sample):
                return False
            
            numeric = pd.to_numeric(sample, errors='coerce')
            return numeric.isna().sum() <= len(sample) * 0.1  # Less than 10% failed
        except:
            return False

    def _matches_pattern(self, sample: pd.Series, pattern: re.Pattern, threshold: float = 0.9) -> bool:
        """Check if values match a regex pattern"""
        try:
            matches = sample.str.match(pattern)
            return matches.sum() / len(sample) >= threshold
        except:
            return False

    def _detect_datetime_type(self, sample: pd.Series) -> Optional[DataType]:
        """Detect if column contains date, datetime, or time values"""
        str_sample = sample.astype(str)
        
        # Try datetime formats first
        for fmt in self.DATETIME_FORMATS:
            try:
                parsed = pd.to_datetime(str_sample, format=fmt, errors='coerce')
                if parsed.notna().sum() / len(sample) >= 0.9:
                    return DataType.DATETIME
            except:
                continue
        
        # Try date formats
        for fmt in self.DATE_FORMATS:
            try:
                parsed = pd.to_datetime(str_sample, format=fmt, errors='coerce')
                if parsed.notna().sum() / len(sample) >= 0.9:
                    return DataType.DATE
            except:
                continue
        
        # Try time formats
        for fmt in self.TIME_FORMATS:
            try:
                # pandas doesn't have a direct time parser, so we check if format matches
                matches = str_sample.apply(lambda x: self._try_parse_time(x, fmt))
                if matches.sum() / len(sample) >= 0.9:
                    return DataType.TIME
            except:
                continue
        
        # Try pandas automatic datetime parsing
        try:
            parsed = pd.to_datetime(str_sample, errors='coerce')
            if parsed.notna().sum() / len(sample) >= 0.9:
                # Check if times are meaningful (not all midnight)
                if (parsed.dt.hour != 0).any() or (parsed.dt.minute != 0).any():
                    return DataType.DATETIME
                else:
                    return DataType.DATE
        except:
            pass
        
        return None

    def _try_parse_time(self, value: str, fmt: str) -> bool:
        """Try to parse a time value"""
        try:
            datetime.strptime(value, fmt)
            return True
        except:
            return False

    def _clean_numeric_series(self, series: pd.Series, data_type: DataType) -> pd.Series:
        """Clean numeric series based on data type"""
        if data_type == DataType.CURRENCY:
            # Remove currency symbols and convert
            cleaned = series.astype(str).str.replace(r'[$€£¥,]', '', regex=True)
            return pd.to_numeric(cleaned, errors='coerce').dropna()
        elif data_type == DataType.PERCENTAGE:
            # Remove % and divide by 100
            cleaned = series.astype(str).str.replace('%', '', regex=False)
            return pd.to_numeric(cleaned, errors='coerce').dropna() / 100
        else:
            return pd.to_numeric(series, errors='coerce').dropna()

    def _calculate_type_confidence(self, series: pd.Series, data_type: DataType) -> float:
        """Calculate confidence score for type inference"""
        non_null = series.dropna()
        if len(non_null) == 0:
            return 0.0
        
        # For numeric types, check how many values can be converted
        if data_type in [DataType.INTEGER, DataType.FLOAT]:
            numeric = pd.to_numeric(non_null, errors='coerce')
            return numeric.notna().sum() / len(non_null)
        
        # For date types, check parsing success
        elif data_type in [DataType.DATE, DataType.DATETIME]:
            parsed = pd.to_datetime(non_null, errors='coerce')
            return parsed.notna().sum() / len(non_null)
        
        # For pattern-based types, return match percentage
        elif data_type in [DataType.EMAIL, DataType.PHONE, DataType.URL]:
            # This is simplified - in production would re-check patterns
            return 0.95
        
        # For other types, return high confidence
        return 0.9