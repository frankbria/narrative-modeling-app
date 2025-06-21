"""
Batch prediction API routes
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import io

from app.models.batch_job import BatchJob, JobStatus, JobType
from app.services.batch_prediction import BatchPredictionService
from app.auth.nextauth_auth import get_current_user_id


router = APIRouter(prefix="/batch", tags=["batch-prediction"])

# Initialize service
batch_service = BatchPredictionService()


# Request/Response Models
class CreateBatchJobRequest(BaseModel):
    model_id: str = Field(..., description="Model ID to use for predictions")
    output_format: str = Field(default="csv", description="Output format (csv, json)")
    include_probabilities: bool = Field(default=True, description="Include prediction probabilities")
    include_metadata: bool = Field(default=False, description="Include model metadata")
    chunk_size: int = Field(default=1000, ge=100, le=10000, description="Records per processing chunk")
    priority: int = Field(default=0, description="Job priority")


class BatchJobResponse(BaseModel):
    job_id: str
    job_type: str
    status: str
    progress: Dict[str, Any]
    config: Dict[str, Any]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_seconds: Optional[float]
    error_message: Optional[str]
    results: Dict[str, Any]
    input_size_bytes: Optional[int]
    output_path: Optional[str]


class JobProgressResponse(BaseModel):
    job_id: str
    status: str
    percentage_complete: float
    processed_records: int
    total_records: int
    success_count: int
    error_count: int
    success_rate: float
    current_chunk: int
    total_chunks: int
    estimated_completion: Optional[datetime]


# API Routes
@router.post("/jobs", response_model=BatchJobResponse)
async def create_batch_job(
    file: UploadFile = File(..., description="CSV file with data to predict"),
    model_id: str = Form(..., description="Model ID"),
    output_format: str = Form(default="csv", description="Output format"),
    include_probabilities: bool = Form(default=True, description="Include probabilities"),
    include_metadata: bool = Form(default=False, description="Include metadata"),
    chunk_size: int = Form(default=1000, description="Chunk size"),
    priority: int = Form(default=0, description="Job priority"),
    current_user_id: str = Depends(get_current_user_id)
):
    """Create a new batch prediction job from uploaded file"""
    
    # Validate file type
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")
    
    try:
        # Read file content
        content = await file.read()
        
        # Save to temporary file
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.csv') as temp_file:
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        try:
            # Create job
            job = await batch_service.create_batch_prediction_job(
                user_id=current_user_id,
                model_id=model_id,
                input_data=temp_file_path,
                output_format=output_format,
                include_probabilities=include_probabilities,
                chunk_size=chunk_size,
                priority=priority
            )
            
            # Store input file size
            job.input_size_bytes = len(content)
            await job.save()
            
        finally:
            # Clean up temp file
            os.unlink(temp_file_path)
        
        return BatchJobResponse(
            job_id=job.job_id,
            job_type=job.job_type,
            status=job.status,
            progress=job.progress.dict(),
            config=job.config,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            duration_seconds=job.duration_seconds,
            error_message=job.error_message,
            results=job.results,
            input_size_bytes=job.input_size_bytes,
            output_path=job.output_path
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create batch job: {str(e)}")


@router.get("/jobs", response_model=List[BatchJobResponse])
async def list_batch_jobs(
    job_type: Optional[JobType] = Query(None, description="Filter by job type"),
    status: Optional[JobStatus] = Query(None, description="Filter by status"),
    limit: int = Query(default=50, le=100, description="Maximum number of jobs to return"),
    current_user_id: str = Depends(get_current_user_id)
):
    """List user's batch jobs"""
    
    jobs = await batch_service.list_user_jobs(
        user_id=current_user_id,
        job_type=job_type,
        status=status,
        limit=limit
    )
    
    return [
        BatchJobResponse(
            job_id=job.job_id,
            job_type=job.job_type,
            status=job.status,
            progress=job.progress.dict(),
            config=job.config,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            duration_seconds=job.duration_seconds,
            error_message=job.error_message,
            results=job.results,
            input_size_bytes=job.input_size_bytes,
            output_path=job.output_path
        )
        for job in jobs
    ]


@router.get("/jobs/{job_id}", response_model=BatchJobResponse)
async def get_batch_job(
    job_id: str,
    current_user_id: str = Depends(get_current_user_id)
):
    """Get details of a specific batch job"""
    
    job = await batch_service.get_job_status(job_id, current_user_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return BatchJobResponse(
        job_id=job.job_id,
        job_type=job.job_type,
        status=job.status,
        progress=job.progress.dict(),
        config=job.config,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        duration_seconds=job.duration_seconds,
        error_message=job.error_message,
        results=job.results,
        input_size_bytes=job.input_size_bytes,
        output_path=job.output_path
    )


@router.get("/jobs/{job_id}/progress", response_model=JobProgressResponse)
async def get_job_progress(
    job_id: str,
    current_user_id: str = Depends(get_current_user_id)
):
    """Get real-time progress of a batch job"""
    
    job = await batch_service.get_job_status(job_id, current_user_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return JobProgressResponse(
        job_id=job.job_id,
        status=job.status,
        percentage_complete=job.progress.percentage_complete,
        processed_records=job.progress.processed_records,
        total_records=job.progress.total_records,
        success_count=job.progress.success_count,
        error_count=job.progress.error_count,
        success_rate=job.progress.success_rate,
        current_chunk=job.progress.current_chunk,
        total_chunks=job.progress.total_chunks,
        estimated_completion=job.estimated_completion
    )


@router.post("/jobs/{job_id}/cancel")
async def cancel_batch_job(
    job_id: str,
    current_user_id: str = Depends(get_current_user_id)
):
    """Cancel a pending or running batch job"""
    
    success = await batch_service.cancel_job(job_id, current_user_id)
    
    if not success:
        raise HTTPException(status_code=400, detail="Job cannot be cancelled")
    
    return {"message": "Job cancelled successfully"}


@router.post("/jobs/{job_id}/retry")
async def retry_batch_job(
    job_id: str,
    current_user_id: str = Depends(get_current_user_id)
):
    """Retry a failed batch job"""
    
    success = await batch_service.retry_job(job_id, current_user_id)
    
    if not success:
        raise HTTPException(status_code=400, detail="Job cannot be retried")
    
    return {"message": "Job retry initiated"}


@router.get("/jobs/{job_id}/download")
async def download_results(
    job_id: str,
    current_user_id: str = Depends(get_current_user_id)
):
    """Download batch job results"""
    
    # Get job details
    job = await batch_service.get_job_status(job_id, current_user_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Job is not completed")
    
    # Download results
    content = await batch_service.download_results(job_id, current_user_id)
    
    if not content:
        raise HTTPException(status_code=404, detail="Results not found")
    
    # Determine content type and filename
    config = job.config
    output_format = config.get("output_format", "csv")
    
    if output_format == "csv":
        media_type = "text/csv"
        filename = f"batch_results_{job_id}.csv"
    elif output_format == "json":
        media_type = "application/json"
        filename = f"batch_results_{job_id}.json"
    else:
        media_type = "application/octet-stream"
        filename = f"batch_results_{job_id}.{output_format}"
    
    # Return file stream
    return StreamingResponse(
        io.BytesIO(content),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.delete("/jobs/{job_id}")
async def delete_batch_job(
    job_id: str,
    current_user_id: str = Depends(get_current_user_id)
):
    """Delete a batch job and its results"""
    
    job = await batch_service.get_job_status(job_id, current_user_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Only allow deletion of completed, failed, or cancelled jobs
    if job.status in [JobStatus.PENDING, JobStatus.RUNNING]:
        raise HTTPException(status_code=400, detail="Cannot delete active job")
    
    # Delete job document
    await job.delete()
    
    # TODO: Clean up S3 files in background
    
    return {"message": "Job deleted successfully"}


@router.get("/stats")
async def get_batch_stats(
    current_user_id: str = Depends(get_current_user_id)
):
    """Get batch processing statistics for the user"""
    
    # Get all user jobs
    all_jobs = await batch_service.list_user_jobs(
        user_id=current_user_id,
        limit=1000  # Get all jobs for stats
    )
    
    # Calculate statistics
    total_jobs = len(all_jobs)
    completed_jobs = len([j for j in all_jobs if j.status == JobStatus.COMPLETED])
    failed_jobs = len([j for j in all_jobs if j.status == JobStatus.FAILED])
    running_jobs = len([j for j in all_jobs if j.status == JobStatus.RUNNING])
    pending_jobs = len([j for j in all_jobs if j.status == JobStatus.PENDING])
    
    # Calculate total predictions processed
    total_predictions = sum(
        j.progress.processed_records for j in all_jobs 
        if j.progress.processed_records
    )
    
    # Calculate average success rate
    success_rates = [
        j.progress.success_rate for j in all_jobs 
        if j.progress.processed_records > 0
    ]
    avg_success_rate = sum(success_rates) / len(success_rates) if success_rates else 0
    
    return {
        "total_jobs": total_jobs,
        "completed_jobs": completed_jobs,
        "failed_jobs": failed_jobs,
        "running_jobs": running_jobs,
        "pending_jobs": pending_jobs,
        "total_predictions": total_predictions,
        "average_success_rate": avg_success_rate,
        "completion_rate": (completed_jobs / total_jobs * 100) if total_jobs > 0 else 0
    }