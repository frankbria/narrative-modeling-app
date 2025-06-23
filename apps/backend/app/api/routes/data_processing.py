"""
API routes for data processing functionality
"""

from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ConfigDict
import numpy as np
import json

from app.auth.nextauth_auth import get_current_user_id
from app.models.user_data import UserData
from app.services.data_processing.data_processor import DataProcessor
from app.services.s3_service import s3_service
from app.utils.json_encoder import convert_numpy_types, NumpyJSONEncoder


router = APIRouter()
data_processor = DataProcessor()


class ProcessingRequest(BaseModel):
    """Request model for data processing"""
    file_id: str = Field(..., description="ID of the uploaded file to process")
    options: Optional[Dict[str, Any]] = Field(default=None, description="Processing options")


class ProcessingResponse(BaseModel):
    """Response model for data processing"""
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
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
    schema: Dict[str, Any]
    statistics: Dict[str, Any]
    quality_report: Dict[str, Any]
    preview: Dict[str, Any]


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
        
        # Download file from S3
        # Extract file key from S3 URL (handle both s3:// and https:// formats)
        s3_url = user_data.s3_url
        if s3_url.startswith(f"s3://{s3_service.bucket_name}/"):
            file_key = s3_url.replace(f"s3://{s3_service.bucket_name}/", "")
        elif s3_url.startswith(f"https://{s3_service.bucket_name}.s3.amazonaws.com/"):
            file_key = s3_url.replace(f"https://{s3_service.bucket_name}.s3.amazonaws.com/", "")
        else:
            # Try to extract key from any S3 URL format
            import re
            match = re.search(r'/([^/]+)$', s3_url)
            if match:
                file_key = match.group(1)
            else:
                raise ValueError(f"Could not extract file key from S3 URL: {s3_url}")
        
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
        
    except Exception as e:
        import traceback
        print(f"ERROR in process_data: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


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


@router.get("/{file_id}/preview")
async def get_data_preview(
    file_id: str = Path(..., description="File ID"),
    rows: int = Query(100, description="Number of rows to preview", ge=1, le=1000),
    offset: int = Query(0, description="Row offset", ge=0),
    current_user_id: str = Depends(get_current_user_id)
):
    """Get preview of processed data"""
    import pandas as pd
    import io
    
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
        file_key = user_data.s3_url.replace(f"s3://{s3_service.bucket_name}/", "")
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


@router.post("/{file_id}/export")
async def export_processed_data(
    file_id: str = Path(..., description="File ID"),
    format: str = Query("csv", description="Export format", pattern="^(csv|excel|json|parquet)$"),
    include_stats: bool = Query(False, description="Include statistics in export"),
    current_user_id: str = Depends(get_current_user_id)
):
    """Export processed data in various formats"""
    user_data = await UserData.find_one(
        UserData.id == file_id,
        UserData.user_id == current_user_id
    )
    
    if not user_data:
        raise HTTPException(status_code=404, detail="File not found")
    
    if not user_data.is_processed:
        raise HTTPException(status_code=400, detail="File not processed yet")
    
    # TODO: Implement actual export functionality
    # For now, return export metadata
    
    export_filename = f"{user_data.original_filename.rsplit('.', 1)[0]}_processed.{format}"
    
    return {
        "file_id": str(user_data.id),
        "export_format": format,
        "export_filename": export_filename,
        "include_stats": include_stats,
        "status": "export_ready",
        "download_url": f"/api/v1/data/{file_id}/download?format={format}"
    }