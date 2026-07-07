"""
API routes for data processing functionality
"""

import io
import json
import logging
import os
from typing import Any

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.auth.nextauth_auth import get_current_user_id
from app.models.user_data import UserData
from app.schemas.quality import QualityReportResponse
from app.services.data_processing.data_processor import DataProcessor
from app.services.data_processing.quality_assessment import ActionableRecommendation
from app.services.quality_gate_service import evaluate_gates, overall_score
from app.services.s3_service import s3_service
from app.utils.json_encoder import NumpyJSONEncoder, convert_numpy_types
from app.utils.s3 import parse_s3_url

logger = logging.getLogger(__name__)

router = APIRouter()
data_processor = DataProcessor()


class ProcessingRequest(BaseModel):
    """Request model for data processing"""
    file_id: str = Field(..., description="ID of the uploaded file to process")
    options: dict[str, Any] | None = Field(default=None, description="Processing options")


class ProcessingResponse(BaseModel):
    """Response model for data processing"""
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        populate_by_name=True,
        json_encoders={
            np.integer: lambda v: int(v),
            np.floating: lambda v: float(v),
            np.ndarray: lambda v: v.tolist(),
            np.bool_: lambda v: bool(v)
        }
    )

    status: str
    file_id: str
    processing_id: str
    data_schema: dict[str, Any] = Field(alias="schema")
    statistics: dict[str, Any]
    quality_report: dict[str, Any]
    preview: dict[str, Any]


@router.post("/process", response_model=ProcessingResponse)
async def process_uploaded_file(
    request: ProcessingRequest,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Process an uploaded file to infer schema, calculate statistics, and assess quality
    """
    try:
        # Get file metadata from database
        # Try to convert string ID to PydanticObjectId
        from beanie import PydanticObjectId
        
        try:
            file_obj_id = PydanticObjectId(request.file_id)
            user_data = await UserData.find_one(
                UserData.id == file_obj_id,
                UserData.user_id == current_user_id
            )
        except Exception:
            # If conversion fails, try as string
            user_data = await UserData.find_one(
                UserData.id == request.file_id,
                UserData.user_id == current_user_id
            )
        
        if not user_data:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Download file from S3 (parse_s3_url handles all persisted URL shapes)
        try:
            _, file_key = parse_s3_url(user_data.s3_url)
        except ValueError as err:
            # Strip the query string before logging — presigned URLs carry
            # credentials; the error handler echoes exception text to clients
            sanitized_url = user_data.s3_url.split("?")[0]
            logger.error(f"Could not extract file key from S3 URL: {sanitized_url}")
            raise ValueError("Could not extract file key from stored S3 URL") from err

        file_bytes = await s3_service.download_file_bytes(file_key)
        
        # Process the file
        processed_data = await data_processor.process_bytes(
            file_bytes=file_bytes,
            filename=user_data.original_filename,
            file_type=user_data.file_type
        )
        
        # Store processing results in database
        try:
            user_data.schema = convert_numpy_types(processed_data.schema.model_dump())
        except Exception as e:
            print(f"Error dumping schema: {e}")
            raise
            
        try:
            user_data.statistics = convert_numpy_types(processed_data.statistics.model_dump())
        except Exception as e:
            print(f"Error dumping statistics: {e}")
            raise
            
        try:
            user_data.quality_report = convert_numpy_types(processed_data.quality_report.model_dump())
        except Exception as e:
            print(f"Error dumping quality_report: {e}")
            raise
        user_data.processed_at = processed_data.processed_at
        user_data.is_processed = True
        
        print("About to save user_data...")
        try:
            await user_data.save()
            print("user_data saved successfully")
        except Exception as e:
            print(f"Error saving user_data: {e}")
            raise
        
        # Return processing results
        # Convert all numpy types to Python types before returning
        response_data = {
            "status": "success",
            "file_id": str(user_data.id),
            "processing_id": str(user_data.id),  # Using same ID for now
            "schema": convert_numpy_types(processed_data.schema.model_dump()),
            "statistics": convert_numpy_types(processed_data.statistics.model_dump()),
            "quality_report": convert_numpy_types(processed_data.quality_report.model_dump()),
            "preview": convert_numpy_types(processed_data.get_preview())
        }
        
        # Use custom JSON encoder to handle any remaining numpy types
        return JSONResponse(
            content=json.loads(json.dumps(response_data, cls=NumpyJSONEncoder)),
            status_code=200
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions without wrapping
        raise
    except Exception as e:
        import traceback
        print(f"ERROR in process_data: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error processing dataset: {str(e)}")


@router.get("/{file_id}/schema")
async def get_file_schema(
    file_id: str = Path(..., description="File ID"),
    current_user_id: str = Depends(get_current_user_id)
):
    """Get inferred schema for a processed file"""
    user_data = await UserData.find_one(
        UserData.id == file_id,
        UserData.user_id == current_user_id
    )
    
    if not user_data:
        raise HTTPException(status_code=404, detail="File not found")
    
    if not user_data.is_processed or not user_data.schema:
        raise HTTPException(status_code=400, detail="File not processed yet")
    
    return {
        "file_id": str(user_data.id),
        "filename": user_data.original_filename,
        "schema": user_data.schema
    }


@router.get("/{file_id}/statistics")
async def get_file_statistics(
    file_id: str = Path(..., description="File ID"),
    current_user_id: str = Depends(get_current_user_id)
):
    """Get calculated statistics for a processed file"""
    user_data = await UserData.find_one(
        UserData.id == file_id,
        UserData.user_id == current_user_id
    )
    
    if not user_data:
        raise HTTPException(status_code=404, detail="File not found")
    
    if not user_data.is_processed or not user_data.statistics:
        raise HTTPException(status_code=400, detail="File not processed yet")
    
    return {
        "file_id": str(user_data.id),
        "filename": user_data.original_filename,
        "statistics": user_data.statistics
    }


@router.get("/{file_id}/quality")
async def get_quality_report(
    file_id: str = Path(..., description="File ID"),
    current_user_id: str = Depends(get_current_user_id)
):
    """Get quality assessment report for a processed file"""
    user_data = await UserData.find_one(
        UserData.id == file_id,
        UserData.user_id == current_user_id
    )
    
    if not user_data:
        raise HTTPException(status_code=404, detail="File not found")
    
    if not user_data.is_processed or not user_data.quality_report:
        raise HTTPException(status_code=400, detail="File not processed yet")
    
    return {
        "file_id": str(user_data.id),
        "filename": user_data.original_filename,
        "quality_report": user_data.quality_report
    }


@router.get("/{file_id}/quality-report", response_model=QualityReportResponse)
async def get_quality_report_consolidated(
    file_id: str = Path(..., description="File ID"),
    current_user_id: str = Depends(get_current_user_id)
):
    """Consolidated quality report: 0-100 score, components, actionable
    recommendations, and soft quality gates (issue #102, AC4/AC5).

    Built from the cached quality report. Pre-#102 caches degrade to ``partial=true``
    (gates derived from legacy dimension scores). Quality trend has its own endpoint
    (GET /api/v1/datasets/{dataset_id}/quality-trend). Never 500s on stale caches.
    """
    user_data = await UserData.find_one(
        UserData.id == file_id,
        UserData.user_id == current_user_id
    )
    if not user_data:
        raise HTTPException(status_code=404, detail="File not found")
    if not user_data.is_processed or not user_data.quality_report:
        raise HTTPException(status_code=400, detail="File not processed yet")

    report = user_data.quality_report
    # Pre-#102 cached reports lack the 0-100 score / actionable recs.
    partial = "score_0_100" not in report

    gates = evaluate_gates(report)
    actionable = [
        ActionableRecommendation(**rec)
        for rec in report.get("actionable_recommendations", [])
    ]

    return QualityReportResponse(
        file_id=str(user_data.id),
        filename=user_data.original_filename,
        score_0_100=overall_score(report),
        component_scores={
            str(k): float(v) for k, v in (report.get("component_scores") or {}).items()
        },
        recommendations=report.get("recommendations", []),
        actionable_recommendations=actionable,
        gates=gates,
        critical_issue_count=len(report.get("critical_issues", [])),
        warning_count=len(report.get("warnings", [])),
        partial=partial,
    )


@router.get("/{file_id}/preview")
async def get_data_preview(
    file_id: str = Path(..., description="File ID"),
    rows: int = Query(100, description="Number of rows to preview", ge=1, le=1000),
    offset: int = Query(0, description="Row offset", ge=0),
    current_user_id: str = Depends(get_current_user_id)
):
    """Get preview of processed data"""
    import io

    import pandas as pd
    
    user_data = await UserData.find_one(
        UserData.id == file_id,
        UserData.user_id == current_user_id
    )
    
    if not user_data:
        raise HTTPException(status_code=404, detail="File not found")
    
    if not user_data.is_processed:
        raise HTTPException(status_code=400, detail="File not processed yet")
    
    try:
        # Download file from S3 to get actual data
        # (parse_s3_url handles all persisted URL shapes)
        _, file_key = parse_s3_url(user_data.s3_url)
        file_bytes = await s3_service.download_file_bytes(file_key)
        
        # Read the file based on type
        if user_data.file_type == "csv" or user_data.original_filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(file_bytes))
        elif user_data.file_type == "excel" or user_data.original_filename.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(io.BytesIO(file_bytes))
        else:
            # Fall back to cached preview if file type unknown
            preview_data = user_data.data_preview or []
            paginated_data = preview_data[offset:offset + rows]
            return {
                "file_id": str(user_data.id),
                "filename": user_data.original_filename,
                "columns": user_data.columns or [],
                "data": paginated_data,
                "total_rows": user_data.row_count or len(preview_data),
                "offset": offset,
                "rows": len(paginated_data)
            }
        
        # Apply pagination to the actual data
        total_rows = len(df)
        paginated_df = df.iloc[offset:offset + rows]
        
        return {
            "file_id": str(user_data.id),
            "filename": user_data.original_filename,
            "columns": df.columns.tolist(),
            "data": paginated_df.to_dict('records'),
            "total_rows": total_rows,
            "offset": offset,
            "rows": len(paginated_df)
        }
        
    except Exception as e:
        # If S3 read fails, fall back to cached preview
        print(f"Error reading from S3: {e}")
        preview_data = user_data.data_preview or []
        paginated_data = preview_data[offset:offset + rows]
        
        return {
            "file_id": str(user_data.id),
            "filename": user_data.original_filename,
            "columns": user_data.columns or [],
            "data": paginated_data,
            "total_rows": user_data.row_count or len(preview_data),
            "offset": offset,
            "rows": len(paginated_data),
            "warning": "Using cached preview data"
        }


def _read_source_dataframe(user_data, file_bytes: bytes):
    """Read an uploaded source file into a DataFrame (matches the upload readers).

    Raises HTTPException(422) for source types we cannot read.
    """
    import pandas as pd

    name = user_data.original_filename or ""
    ftype = user_data.file_type
    if ftype == "csv" or name.endswith(".csv"):
        return pd.read_csv(io.BytesIO(file_bytes))
    if ftype == "txt" or name.endswith(".txt"):
        return pd.read_csv(io.BytesIO(file_bytes), sep="\t")  # upload stores txt as TSV
    if ftype in ("excel", "xls", "xlsx") or name.endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(file_bytes))
    if ftype == "parquet" or name.endswith(".parquet"):
        return pd.read_parquet(io.BytesIO(file_bytes))
    if ftype == "json" or name.endswith(".json"):
        return pd.read_json(io.BytesIO(file_bytes))
    raise HTTPException(
        status_code=422,
        detail=f"Cannot export unsupported source file type: {ftype}",
    )


def _serialize_dataframe(df, export_format: str) -> bytes:
    """Serialize a DataFrame to the requested export format's bytes."""
    if export_format == "csv":
        return df.to_csv(index=False).encode()
    if export_format == "json":
        return df.to_json(orient="records").encode()
    if export_format == "parquet":
        buf = io.BytesIO()
        df.to_parquet(buf, index=False)
        return buf.getvalue()
    if export_format == "excel":
        buf = io.BytesIO()
        df.to_excel(buf, index=False)
        return buf.getvalue()
    raise ValueError(f"Unsupported export format: {export_format}")


@router.post("/{file_id}/export")
async def export_processed_data(
    file_id: str = Path(..., description="File ID"),
    format: str = Query("csv", description="Export format", pattern="^(csv|excel|json|parquet)$"),
    current_user_id: str = Depends(get_current_user_id)
):
    """Export processed data as a real, downloadable file.

    Reads the source file from S3, converts it to the requested format, uploads
    the artifact, and returns a working presigned download URL (valid 1 hour).
    """
    user_data = await UserData.find_one(
        UserData.id == file_id,
        UserData.user_id == current_user_id
    )

    if not user_data:
        raise HTTPException(status_code=404, detail="File not found")

    if not user_data.is_processed:
        raise HTTPException(status_code=400, detail="File not processed yet")

    # original_filename is user-controlled; strip any path so a crafted name
    # (e.g. "../../x.csv") can't escape the exports/{user}/{file}/ key prefix.
    safe_stem = os.path.basename(user_data.original_filename or "export").rsplit(".", 1)[0] or "export"
    export_filename = f"{safe_stem}_processed.{format}"

    try:
        # Load the source file from S3 (same shapes the preview endpoint handles)
        _, file_key = parse_s3_url(user_data.s3_url)
        file_bytes = await s3_service.download_file_bytes(file_key)

        df = _read_source_dataframe(user_data, file_bytes)
        export_bytes = _serialize_dataframe(df, format)
        export_key = f"exports/{current_user_id}/{file_id}/{export_filename}"
        await s3_service.upload_file_obj(io.BytesIO(export_bytes), export_key)
        download_url = s3_service.generate_presigned_url(export_key, filename=export_filename)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Export failed for file %s: %s", file_id, e)
        raise HTTPException(status_code=500, detail="Export failed") from e

    return {
        "file_id": str(user_data.id),
        "export_format": format,
        "export_filename": export_filename,
        "status": "export_ready",
        "download_url": download_url,
    }
