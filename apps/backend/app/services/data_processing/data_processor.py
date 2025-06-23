"""
Main data processor that orchestrates schema inference, statistics, and quality assessment
"""

import io
from typing import Dict, Any, Optional, Tuple
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime, timezone

from .schema_inference import SchemaInferenceService, SchemaDefinition
from .statistics_engine import StatisticsEngine, DatasetStatistics
from .quality_assessment import QualityAssessmentService, QualityReport


class ProcessedData:
    """Container for processed data and metadata"""
    
    def __init__(
        self,
        dataframe: pd.DataFrame,
        schema: SchemaDefinition,
        statistics: DatasetStatistics,
        quality_report: QualityReport,
        file_metadata: Dict[str, Any]
    ):
        self.dataframe = dataframe
        self.schema = schema
        self.statistics = statistics
        self.quality_report = quality_report
        self.file_metadata = file_metadata
        self.processed_at = datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "schema": self.schema.model_dump(),
            "statistics": self.statistics.model_dump(),
            "quality_report": self.quality_report.model_dump(),
            "file_metadata": self.file_metadata,
            "processed_at": self.processed_at.isoformat(),
            "preview": self.get_preview()
        }
    
    def get_preview(self, rows: int = 100) -> Dict[str, Any]:
        """Get preview of the data"""
        preview_df = self.dataframe.head(rows)
        
        # Convert numpy types to Python types in the preview data
        preview_data = []
        for record in preview_df.to_dict(orient="records"):
            converted_record = {}
            for key, value in record.items():
                # Handle pandas NaN/None values
                if pd.isna(value):
                    converted_record[key] = None
                elif isinstance(value, np.integer):
                    converted_record[key] = int(value)
                elif isinstance(value, np.floating):
                    converted_record[key] = float(value)
                elif isinstance(value, np.ndarray):
                    converted_record[key] = value.tolist()
                elif isinstance(value, np.bool_):
                    converted_record[key] = bool(value)
                elif hasattr(value, 'item'):  # Handle numpy scalars
                    converted_record[key] = value.item()
                else:
                    converted_record[key] = value
            preview_data.append(converted_record)
        
        return {
            "columns": [str(col) for col in preview_df.columns],  # Ensure column names are strings
            "data": preview_data,
            "total_rows": len(self.dataframe),
            "preview_rows": len(preview_df)
        }
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of the processed data"""
        column_types = {col.name: col.data_type for col in self.schema.columns}
        
        return {
            "filename": self.file_metadata.get("filename", "unknown"),
            "file_type": self.file_metadata.get("file_type", "unknown"),
            "row_count": len(self.dataframe),
            "column_count": len(self.dataframe.columns),
            "overall_quality_score": self.quality_report.overall_quality_score,
            "column_types": column_types,
            "processing_time_seconds": (datetime.now(timezone.utc) - self.processed_at).total_seconds()
        }


class DataProcessor:
    """Main data processing orchestrator"""
    
    def __init__(
        self,
        schema_sample_size: int = 1000,
        outlier_method: str = "iqr",
        correlation_threshold: float = 0.7
    ):
        """
        Initialize data processor with component services
        
        Args:
            schema_sample_size: Number of rows to sample for schema inference
            outlier_method: Method for outlier detection ('iqr' or 'zscore')
            correlation_threshold: Threshold for flagging high correlations
        """
        self.schema_service = SchemaInferenceService(sample_size=schema_sample_size)
        self.stats_engine = StatisticsEngine(
            outlier_method=outlier_method,
            correlation_threshold=correlation_threshold
        )
        self.quality_service = QualityAssessmentService()
    
    async def process_file(
        self,
        file_path: str,
        file_type: Optional[str] = None,
        encoding: str = "utf-8",
        delimiter: Optional[str] = None
    ) -> ProcessedData:
        """
        Process a file from disk
        
        Args:
            file_path: Path to the file
            file_type: Type of file (csv, excel, etc.)
            encoding: File encoding
            delimiter: CSV delimiter (auto-detected if None)
            
        Returns:
            ProcessedData object with all analysis results
        """
        # Detect file type if not provided
        if not file_type:
            file_type = self._detect_file_type(file_path)
        
        # Read the file into DataFrame
        df = await self._read_file(file_path, file_type, encoding, delimiter)
        
        # Get file metadata
        file_metadata = self._get_file_metadata(file_path, file_type)
        
        # Process the DataFrame
        return await self.process_dataframe(df, file_metadata)
    
    async def process_bytes(
        self,
        file_bytes: bytes,
        filename: str,
        file_type: Optional[str] = None,
        encoding: str = "utf-8",
        delimiter: Optional[str] = None
    ) -> ProcessedData:
        """
        Process file from bytes
        
        Args:
            file_bytes: File content as bytes
            filename: Original filename
            file_type: Type of file
            encoding: File encoding
            delimiter: CSV delimiter
            
        Returns:
            ProcessedData object
        """
        # Detect file type from filename if not provided
        if not file_type:
            file_type = self._detect_file_type(filename)
        
        # Create file-like object
        file_obj = io.BytesIO(file_bytes)
        
        # Read into DataFrame
        df = await self._read_file_object(file_obj, file_type, encoding, delimiter)
        
        # Create file metadata
        file_metadata = {
            "filename": filename,
            "file_type": file_type,
            "file_size": len(file_bytes),
            "encoding": encoding
        }
        
        return await self.process_dataframe(df, file_metadata)
    
    async def process_dataframe(
        self,
        df: pd.DataFrame,
        file_metadata: Optional[Dict[str, Any]] = None
    ) -> ProcessedData:
        """
        Process a pandas DataFrame
        
        Args:
            df: Input DataFrame
            file_metadata: Optional metadata about the source file
            
        Returns:
            ProcessedData object with all analysis results
        """
        if file_metadata is None:
            file_metadata = {}
        
        # Clean column names
        df = self._clean_column_names(df)
        
        # Infer schema
        print("Inferring schema...")
        schema = await self.schema_service.infer_schema(
            df, 
            file_type=file_metadata.get("file_type", "unknown")
        )
        
        # Create column type mapping
        column_types = {col.name: col.data_type.value for col in schema.columns}
        
        # Calculate statistics
        print("Calculating statistics...")
        statistics = await self.stats_engine.calculate_statistics(df, column_types)
        
        # Assess quality
        print("Assessing data quality...")
        quality_report = await self.quality_service.assess_quality(
            df, 
            column_types,
            column_stats=statistics.column_statistics
        )
        
        # Create processed data object
        return ProcessedData(
            dataframe=df,
            schema=schema,
            statistics=statistics,
            quality_report=quality_report,
            file_metadata=file_metadata
        )
    
    def _detect_file_type(self, file_path: str) -> str:
        """Detect file type from extension"""
        path = Path(file_path)
        extension = path.suffix.lower()
        
        if extension in ['.csv', '.tsv']:
            return 'csv'
        elif extension in ['.xlsx', '.xls']:
            return 'excel'
        elif extension == '.json':
            return 'json'
        elif extension == '.parquet':
            return 'parquet'
        else:
            return 'unknown'
    
    async def _read_file(
        self,
        file_path: str,
        file_type: str,
        encoding: str,
        delimiter: Optional[str]
    ) -> pd.DataFrame:
        """Read file from disk"""
        if file_type == 'csv':
            # Auto-detect delimiter if not provided
            if not delimiter:
                delimiter = self._detect_delimiter(file_path)
            
            return pd.read_csv(
                file_path,
                encoding=encoding,
                delimiter=delimiter,
                low_memory=False
            )
        
        elif file_type == 'excel':
            # Read first sheet by default
            return pd.read_excel(file_path, engine='openpyxl')
        
        elif file_type == 'json':
            return pd.read_json(file_path)
        
        elif file_type == 'parquet':
            return pd.read_parquet(file_path)
        
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
    
    async def _read_file_object(
        self,
        file_obj: io.BytesIO,
        file_type: str,
        encoding: str,
        delimiter: Optional[str]
    ) -> pd.DataFrame:
        """Read file from file-like object"""
        if file_type == 'csv':
            # Auto-detect delimiter if not provided
            if not delimiter:
                # Read first few lines to detect delimiter
                file_obj.seek(0)
                sample = file_obj.read(1024).decode(encoding)
                file_obj.seek(0)
                delimiter = self._detect_delimiter_from_sample(sample)
            
            return pd.read_csv(
                file_obj,
                encoding=encoding,
                delimiter=delimiter,
                low_memory=False
            )
        
        elif file_type == 'excel':
            return pd.read_excel(file_obj, engine='openpyxl')
        
        elif file_type == 'json':
            return pd.read_json(file_obj)
        
        elif file_type == 'parquet':
            return pd.read_parquet(file_obj)
        
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
    
    def _detect_delimiter(self, file_path: str) -> str:
        """Detect CSV delimiter from file"""
        with open(file_path, 'r') as f:
            sample = f.read(1024)
        
        return self._detect_delimiter_from_sample(sample)
    
    def _detect_delimiter_from_sample(self, sample: str) -> str:
        """Detect delimiter from sample text"""
        # Count occurrences of common delimiters
        delimiters = [',', '\t', ';', '|']
        delimiter_counts = {}
        
        for delimiter in delimiters:
            delimiter_counts[delimiter] = sample.count(delimiter)
        
        # Return delimiter with most occurrences
        if delimiter_counts:
            return max(delimiter_counts, key=delimiter_counts.get)
        else:
            return ','  # Default to comma
    
    def _clean_column_names(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and standardize column names"""
        # Remove leading/trailing whitespace
        df.columns = df.columns.str.strip()
        
        # Replace spaces with underscores
        df.columns = df.columns.str.replace(' ', '_')
        
        # Remove special characters (keep alphanumeric and underscore)
        df.columns = df.columns.str.replace(r'[^a-zA-Z0-9_]', '', regex=True)
        
        # Ensure column names are unique
        cols = pd.Series(df.columns)
        for dup in cols[cols.duplicated()].unique():
            dup_indices = np.where(cols == dup)[0]
            for i, idx in enumerate(dup_indices[1:], 1):
                cols.iloc[idx] = f"{dup}_{i}"
        
        df.columns = cols
        
        return df
    
    def _get_file_metadata(self, file_path: str, file_type: str) -> Dict[str, Any]:
        """Get metadata about the file"""
        path = Path(file_path)
        
        return {
            "filename": path.name,
            "file_type": file_type,
            "file_size": path.stat().st_size,
            "created_at": datetime.fromtimestamp(path.stat().st_ctime).isoformat(),
            "modified_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat()
        }