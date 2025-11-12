"""
Validators for transformation pipeline
"""
from typing import Dict, Any, List, Tuple, Optional
import pandas as pd
import numpy as np
from pydantic import BaseModel, Field


class ValidationRule(BaseModel):
    """A single validation rule"""
    rule_type: str
    parameters: Dict[str, Any]
    error_message: str
    severity: str = "error"  # error, warning, info


class ValidationResult(BaseModel):
    """Result of validation"""
    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    info: List[str] = Field(default_factory=list)
    affected_rows: List[int] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)


class TransformationValidator:
    """Validates transformations before applying"""
    
    @staticmethod
    def validate_remove_duplicates(
        df: pd.DataFrame,
        parameters: Dict[str, Any]
    ) -> ValidationResult:
        """Validate remove duplicates transformation"""
        result = ValidationResult(is_valid=True)
        
        subset = parameters.get('subset', None)
        
        if subset:
            # Check if columns exist
            missing_cols = [col for col in subset if col not in df.columns]
            if missing_cols:
                result.is_valid = False
                result.errors.append(f"Columns not found: {missing_cols}")
                return result
        
        # Check for duplicates
        if subset:
            duplicates = df.duplicated(subset=subset)
        else:
            duplicates = df.duplicated()
        
        n_duplicates = duplicates.sum()
        
        if n_duplicates == 0:
            result.warnings.append("No duplicate rows found")
        else:
            result.info.append(f"Found {n_duplicates} duplicate rows")
            result.affected_rows = df[duplicates].index.tolist()[:10]  # First 10
        
        return result
    
    @staticmethod
    def validate_fill_missing(
        df: pd.DataFrame,
        parameters: Dict[str, Any]
    ) -> ValidationResult:
        """Validate fill missing transformation"""
        result = ValidationResult(is_valid=True)
        
        columns = parameters.get('columns', [])
        value = parameters.get('value', None)
        method = parameters.get('method', None)
        
        # Check if columns exist
        if columns:
            missing_cols = [col for col in columns if col not in df.columns]
            if missing_cols:
                result.is_valid = False
                result.errors.append(f"Columns not found: {missing_cols}")
                return result
        
        # Check if method is applicable
        if method in ['mean', 'median']:
            cols_to_check = columns if columns else df.columns.tolist()
            for col in cols_to_check:
                if col in df.columns and not pd.api.types.is_numeric_dtype(df[col]):
                    result.warnings.append(
                        f"Column '{col}' is not numeric, {method} imputation will be skipped"
                    )
        
        # Check missing values
        if columns:
            missing_counts = {col: df[col].isnull().sum() 
                            for col in columns if col in df.columns}
        else:
            missing_counts = df.isnull().sum().to_dict()
        
        cols_with_missing = [col for col, count in missing_counts.items() if count > 0]
        
        if not cols_with_missing:
            result.warnings.append("No missing values found in specified columns")
        else:
            total_missing = sum(missing_counts.values())
            result.info.append(f"Found {total_missing} missing values across {len(cols_with_missing)} columns")
        
        return result
    
    @staticmethod
    def validate_trim_whitespace(
        df: pd.DataFrame,
        parameters: Dict[str, Any]
    ) -> ValidationResult:
        """Validate trim whitespace transformation"""
        result = ValidationResult(is_valid=True)
        
        columns = parameters.get('columns', [])
        
        # Check if columns exist
        if columns:
            missing_cols = [col for col in columns if col not in df.columns]
            if missing_cols:
                result.is_valid = False
                result.errors.append(f"Columns not found: {missing_cols}")
                return result
            
            # Check if columns are string type
            non_string_cols = []
            for col in columns:
                if col in df.columns and not pd.api.types.is_object_dtype(df[col]):
                    non_string_cols.append(col)
            
            if non_string_cols:
                result.warnings.append(
                    f"Non-string columns will be converted to string: {non_string_cols}"
                )
        
        # Check for whitespace
        string_cols = columns if columns else df.select_dtypes(include=['object']).columns.tolist()
        
        whitespace_found = False
        for col in string_cols:
            if col in df.columns:
                # Check for leading/trailing whitespace
                has_whitespace = df[col].astype(str).str.strip() != df[col].astype(str)
                if has_whitespace.any():
                    whitespace_found = True
                    n_affected = has_whitespace.sum()
                    result.info.append(f"Column '{col}' has {n_affected} values with whitespace")
        
        if not whitespace_found:
            result.warnings.append("No whitespace found in string columns")
        
        return result
    
    @staticmethod
    def validate_transformation_chain(
        df: pd.DataFrame,
        transformations: List[Dict[str, Any]]
    ) -> ValidationResult:
        """Validate a chain of transformations"""
        result = ValidationResult(is_valid=True)
        
        # Simulate applying transformations to check compatibility
        temp_df = df.copy()
        
        for i, transform in enumerate(transformations):
            # Here we would validate each transformation
            # This is a simplified version
            transform_type = transform.get('type')
            
            # Check if output of previous transformation is compatible with next
            if i > 0:
                # Add compatibility checks here
                pass
        
        return result
    
    @staticmethod
    def suggest_transformations(df: pd.DataFrame) -> List[str]:
        """Suggest transformations based on data quality"""
        suggestions = []
        
        # Check for duplicates
        if df.duplicated().any():
            suggestions.append("Consider removing duplicate rows")
        
        # Check for missing values
        missing_cols = df.columns[df.isnull().any()].tolist()
        if missing_cols:
            suggestions.append(f"Handle missing values in columns: {missing_cols[:5]}")
        
        # Check for whitespace in string columns
        string_cols = df.select_dtypes(include=['object']).columns
        for col in string_cols[:5]:  # Check first 5 string columns
            if df[col].astype(str).str.strip().ne(df[col].astype(str)).any():
                suggestions.append(f"Trim whitespace in column '{col}'")
                break
        
        # Check for mixed types
        for col in df.columns:
            if df[col].dtype == 'object':
                # Try to convert to numeric
                try:
                    pd.to_numeric(df[col], errors='coerce')
                    non_numeric = pd.to_numeric(df[col], errors='coerce').isnull().sum()
                    if non_numeric < len(df) * 0.1:  # Less than 10% non-numeric
                        suggestions.append(f"Consider converting '{col}' to numeric")
                except:
                    pass
        
        return suggestions[:10]  # Return top 10 suggestions