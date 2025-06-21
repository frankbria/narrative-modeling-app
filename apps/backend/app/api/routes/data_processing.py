"""
API routes for data processing functionality
"""

from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from pydantic import BaseModel, Field

from app.auth.nextauth_auth import get_current_user_id
from app.models.user_data import UserData
from app.services.data_processing.data_processor import DataProcessor
from app.services.s3_service import s3_service


router = APIRouter()
data_processor = DataProcessor()


class ProcessingRequest(BaseModel):
    """Request model for data processing"""
    file_id: str = Field(..., description="ID of the uploaded file to process")
    options: Optional[Dict[str, Any]] = Field(default=None, description="Processing options")


class ProcessingResponse(BaseModel):
    """Response model for data processing"""
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
        user_data = await UserData.find_one(
            UserData.id == request.file_id,
            UserData.user_id == current_user_id
        )
        
        if not user_data:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Download file from S3
        file_key = user_data.s3_url.replace(f"s3://{s3_service.bucket_name}/", "")
        file_bytes = await s3_service.download_file_bytes(file_key)
        
        # Process the file
        processed_data = await data_processor.process_bytes(
            file_bytes=file_bytes,
            filename=user_data.original_filename,
            file_type=user_data.file_type
        )
        
        # Store processing results in database
        user_data.schema = processed_data.schema.model_dump()
        user_data.statistics = processed_data.statistics.model_dump()
        user_data.quality_report = processed_data.quality_report.model_dump()
        user_data.processed_at = processed_data.processed_at
        user_data.is_processed = True
        
        await user_data.save()
        
        # Return processing results
        return ProcessingResponse(
            status="success",
            file_id=str(user_data.id),
            processing_id=str(user_data.id),  # Using same ID for now
            schema=processed_data.schema.model_dump(),
            statistics=processed_data.statistics.model_dump(),
            quality_report=processed_data.quality_report.model_dump(),
            preview=processed_data.get_preview()
        )
        
    except Exception as e:
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
    user_data = await UserData.find_one(
        UserData.id == file_id,
        UserData.user_id == current_user_id
    )
    
    if not user_data:
        raise HTTPException(status_code=404, detail="File not found")
    
    if not user_data.is_processed:
        raise HTTPException(status_code=400, detail="File not processed yet")
    
    # For now, return preview from stored data
    # In production, might want to re-read from S3 for pagination
    preview_data = user_data.data_preview or []
    
    # Apply pagination
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