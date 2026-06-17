"""
Pydantic schemas for the transformation preview system.

These schemas define request/response models for the preview API endpoint,
used to show users what transformations will do before applying them.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# Import TransformationStepRequest from existing transformation schemas
from app.schemas.transformation import TransformationStepRequest

# Request Schemas


class PreviewRequest(BaseModel):
    """
    Request schema for transformation preview.

    Used by POST /api/datasets/{dataset_id}/transformations/preview
    Note: dataset_id comes from the URL path, not the request body.
    """

    operations: List[TransformationStepRequest] = Field(
        ..., description="List of transformation steps to preview"
    )
    sample_size: int = Field(
        default=100,
        ge=10,
        le=1000,
        description="Number of rows to sample for preview (10-1000)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "operations": [
                    {"transformation_type": "remove_nulls", "column": "age"},
                    {
                        "transformation_type": "remove_outliers",
                        "column": "salary",
                        "parameters": {"method": "iqr"},
                    },
                ],
                "sample_size": 100,
            }
        }


# Data Models


class ImpactStatistics(BaseModel):
    """
    Statistical impact of transformations on data.

    Calculated by comparing original vs transformed DataFrames.
    """

    rows_affected: int = Field(..., description="Number of rows with any changes")
    values_changed: int = Field(..., description="Total number of cells modified")
    columns_affected: List[str] = Field(
        ..., description="Columns that have changes"
    )
    quality_score_before: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall quality score before transformation (0-1)",
    )
    quality_score_after: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall quality score after transformation (0-1)",
    )
    value_distributions: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Value distribution changes per affected column (before/after)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "rows_affected": 45,
                "values_changed": 127,
                "columns_affected": ["age", "salary"],
                "quality_score_before": 0.72,
                "quality_score_after": 0.89,
                "value_distributions": {
                    "age": {
                        "before": {"25": 10, "30": 15, "null": 20},
                        "after": {"25": 10, "30": 15, "35": 20},
                    }
                },
            }
        }


class PreviewResult(BaseModel):
    """
    Result of transformation preview generation.

    Contains original data, transformed data, impact statistics, and any warnings/errors.
    """

    original_data: List[Dict[str, Any]] = Field(
        ..., description="Original dataset sample (before transformation)"
    )
    transformed_data: List[Dict[str, Any]] = Field(
        ..., description="Transformed dataset sample (after transformation)"
    )
    impact_stats: ImpactStatistics = Field(
        ..., description="Statistical impact of transformations"
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Non-fatal warnings during preview generation",
    )
    errors: List[str] = Field(
        default_factory=list, description="Errors encountered during transformation"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "original_data": [
                    {"id": 1, "age": None, "salary": 50000},
                    {"id": 2, "age": 30, "salary": 75000},
                ],
                "transformed_data": [
                    {"id": 1, "age": 28, "salary": 50000},
                    {"id": 2, "age": 30, "salary": 75000},
                ],
                "impact_stats": {
                    "rows_affected": 1,
                    "values_changed": 1,
                    "columns_affected": ["age"],
                    "quality_score_before": 0.75,
                    "quality_score_after": 0.85,
                    "value_distributions": {},
                },
                "warnings": ["Replaced 5 null values in 'age' column with mean"],
                "errors": [],
            }
        }


# Response Schemas


class PreviewResponse(BaseModel):
    """
    API response for transformation preview endpoint.

    Used by POST /api/datasets/{dataset_id}/transformations/preview
    """

    success: bool = Field(..., description="Whether preview generation succeeded")
    preview_result: Optional[PreviewResult] = Field(
        None, description="Preview result (null if success=false)"
    )
    error: Optional[str] = Field(
        None, description="Error message (null if success=true)"
    )
    cache_hit: bool = Field(
        default=False, description="Whether result was served from cache"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "preview_result": {
                    "original_data": [
                        {"id": 1, "age": None, "salary": 50000},
                        {"id": 2, "age": 30, "salary": 75000},
                    ],
                    "transformed_data": [
                        {"id": 1, "age": 28, "salary": 50000},
                        {"id": 2, "age": 30, "salary": 75000},
                    ],
                    "impact_stats": {
                        "rows_affected": 1,
                        "values_changed": 1,
                        "columns_affected": ["age"],
                        "quality_score_before": 0.75,
                        "quality_score_after": 0.85,
                        "value_distributions": {},
                    },
                    "warnings": ["Replaced 5 null values in 'age' column with mean"],
                    "errors": [],
                },
                "error": None,
                "cache_hit": False,
            }
        }
