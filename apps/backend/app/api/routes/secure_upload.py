"""
Secure Upload API with PII detection and resumable uploads
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, BackgroundTasks
from typing import Dict, Any, Optional
import pandas as pd
import io
from datetime import datetime

from app.auth.clerk_auth import get_current_user_id
from app.services.security.pii_detector import PIIDetector
from app.services.security.upload_handler import ChunkedUploadHandler, RateLimiter
from app.models.user_data import UserData, SchemaField
from app.utils.schema_inference import infer_schema
from app.utils.s3 import upload_file_to_s3
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize security services
pii_detector = PIIDetector()
upload_handler = ChunkedUploadHandler()
rate_limiter = RateLimiter()


@router.post("/secure")
async def secure_upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user_id: str = Depends(get_current_user_id),
) -> Dict[str, Any]:
    """
    Secure file upload with PII detection and validation
    """
    
    # Rate limiting check
    if not rate_limiter.check_rate_limit(current_user_id):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please wait before uploading again."
        )
    
    if not rate_limiter.check_concurrent_limit(current_user_id):
        raise HTTPException(
            status_code=429,
            detail="Too many concurrent uploads. Please wait for current uploads to complete."
        )
    
    rate_limiter.record_request(current_user_id)
    rate_limiter.start_upload(current_user_id)
    
    try:
        # Validate file type
        allowed_types = ['text/csv', 'application/vnd.ms-excel', 
                        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {file.content_type}"
            )
        
        # Read file content
        content = await file.read()
        
        # Load into DataFrame
        try:
            if file.filename.endswith('.csv'):
                df = pd.read_csv(io.BytesIO(content))
            elif file.filename.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(io.BytesIO(content))
            else:
                raise HTTPException(status_code=400, detail="Unsupported file format")
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to parse file: {str(e)}"
            )
        
        # Check file size (number of rows and columns)
        if len(df) > 10_000_000:  # 10M rows limit
            raise HTTPException(
                status_code=413,
                detail="File too large. Maximum 10 million rows allowed."
            )
        
        # Detect PII
        pii_detections = pii_detector.detect_pii_in_dataframe(df)
        pii_report = pii_detector.generate_pii_report(pii_detections)
        
        # If high-risk PII found, block upload unless explicitly allowed
        if pii_report["risk_level"] == "high":
            return {
                "status": "pii_detected",
                "pii_report": pii_report,
                "message": "High-risk PII detected. Please review and confirm upload.",
                "requires_confirmation": True
            }
        
        # Infer schema
        schema = infer_schema(df)
        
        # Upload to S3
        s3_url = upload_file_to_s3(content, file.filename, current_user_id)
        
        # Create UserData record
        user_data = UserData(
            user_id=current_user_id,
            filename=file.filename,
            s3_url=s3_url,
            num_rows=len(df),
            num_columns=len(df.columns),
            data_schema=schema
        )
        
        # Add PII information
        if pii_report["has_pii"]:
            user_data.pii_report = pii_report
            user_data.contains_pii = True
            user_data.pii_risk_level = pii_report["risk_level"]
        
        await user_data.insert()
        
        # Schedule background AI summary (without PII data)
        if pii_report["has_pii"]:
            # Use masked data for AI analysis
            masked_df = pii_detector.mask_pii(df, pii_detections)
            background_tasks.add_task(generate_ai_summary_safe, user_data.id, masked_df)
        else:
            background_tasks.add_task(generate_ai_summary_safe, user_data.id, df)
        
        return {
            "status": "success",
            "file_id": str(user_data.id),
            "filename": file.filename,
            "num_rows": len(df),
            "num_columns": len(df.columns),
            "pii_report": pii_report,
            "preview": df.head(5).to_dict('records')
        }
    
    finally:
        rate_limiter.end_upload(current_user_id)


@router.post("/confirm-pii-upload")
async def confirm_pii_upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    mask_pii: bool = True,
    current_user_id: str = Depends(get_current_user_id),
) -> Dict[str, Any]:
    """
    Confirm upload of file with PII after user review
    """
    
    # Similar to secure_upload but skips PII blocking
    content = await file.read()
    
    if file.filename.endswith('.csv'):
        df = pd.read_csv(io.BytesIO(content))
    elif file.filename.endswith(('.xlsx', '.xls')):
        df = pd.read_excel(io.BytesIO(content))
    
    # Detect PII
    pii_detections = pii_detector.detect_pii_in_dataframe(df)
    pii_report = pii_detector.generate_pii_report(pii_detections)
    
    # Mask PII if requested
    if mask_pii and pii_detections:
        df_processed = pii_detector.mask_pii(df, pii_detections)
        # Upload masked version
        processed_content = df_processed.to_csv(index=False).encode()
        s3_url = upload_file_to_s3(processed_content, f"masked_{file.filename}", current_user_id)
    else:
        # Upload original
        s3_url = upload_file_to_s3(content, file.filename, current_user_id)
        df_processed = df
    
    # Infer schema
    schema = infer_schema(df_processed)
    
    # Create UserData record
    user_data = UserData(
        user_id=current_user_id,
        filename=file.filename,
        s3_url=s3_url,
        num_rows=len(df_processed),
        num_columns=len(df_processed.columns),
        data_schema=schema,
        contains_pii=True,
        pii_report=pii_report,
        pii_risk_level=pii_report["risk_level"],
        pii_masked=mask_pii
    )
    
    await user_data.insert()
    
    # Use masked data for AI analysis
    background_tasks.add_task(generate_ai_summary_safe, user_data.id, df_processed)
    
    return {
        "status": "success",
        "file_id": str(user_data.id),
        "filename": file.filename,
        "pii_masked": mask_pii,
        "pii_report": pii_report,
        "preview": df_processed.head(5).to_dict('records')
    }


@router.post("/chunked/init")
async def init_chunked_upload(
    filename: str,
    file_size: int,
    file_hash: Optional[str] = None,
    current_user_id: str = Depends(get_current_user_id),
) -> Dict[str, Any]:
    """
    Initialize chunked upload session for large files
    """
    
    if not rate_limiter.check_concurrent_limit(current_user_id):
        raise HTTPException(
            status_code=429,
            detail="Too many concurrent uploads"
        )
    
    session_info = await upload_handler.init_upload(filename, file_size, file_hash)
    rate_limiter.start_upload(current_user_id)
    
    return session_info


@router.post("/chunked/{session_id}/chunk/{chunk_number}")
async def upload_chunk(
    session_id: str,
    chunk_number: int,
    chunk_hash: Optional[str] = None,
    file: UploadFile = File(...),
    current_user_id: str = Depends(get_current_user_id),
) -> Dict[str, Any]:
    """
    Upload a single chunk
    """
    
    chunk_data = await file.read()
    result = await upload_handler.upload_chunk(session_id, chunk_number, chunk_data, chunk_hash)
    
    if result.get("complete"):
        rate_limiter.end_upload(current_user_id)
    
    return result


@router.get("/chunked/{session_id}/resume")
async def resume_chunked_upload(
    session_id: str,
    current_user_id: str = Depends(get_current_user_id),
) -> Dict[str, Any]:
    """
    Get resume information for interrupted upload
    """
    return await upload_handler.resume_upload(session_id)


@router.post("/chunked/{session_id}/complete")
async def complete_chunked_upload(
    session_id: str,
    background_tasks: BackgroundTasks,
    current_user_id: str = Depends(get_current_user_id),
) -> Dict[str, Any]:
    """
    Complete chunked upload and process file
    """
    
    temp_path = await upload_handler.complete_upload(session_id)
    
    # Process the complete file
    with open(temp_path, 'rb') as f:
        content = f.read()
    
    # Get session info to get original filename
    session = upload_handler._get_session(session_id)
    filename = session["filename"]
    
    # Load and process file (similar to secure_upload)
    if filename.endswith('.csv'):
        df = pd.read_csv(io.BytesIO(content))
    elif filename.endswith(('.xlsx', '.xls')):
        df = pd.read_excel(io.BytesIO(content))
    
    # Detect PII
    pii_detections = pii_detector.detect_pii_in_dataframe(df)
    pii_report = pii_detector.generate_pii_report(pii_detections)
    
    # Upload to S3
    s3_url = upload_file_to_s3(content, filename, current_user_id)
    
    # Create UserData record
    schema = infer_schema(df)
    user_data = UserData(
        user_id=current_user_id,
        filename=filename,
        s3_url=s3_url,
        num_rows=len(df),
        num_columns=len(df.columns),
        data_schema=schema
    )
    
    if pii_report["has_pii"]:
        user_data.pii_report = pii_report
        user_data.contains_pii = True
        user_data.pii_risk_level = pii_report["risk_level"]
    
    await user_data.insert()
    
    # Clean up temp file
    temp_path.unlink()
    
    # Background AI summary
    if pii_report["has_pii"]:
        masked_df = pii_detector.mask_pii(df, pii_detections)
        background_tasks.add_task(generate_ai_summary_safe, user_data.id, masked_df)
    else:
        background_tasks.add_task(generate_ai_summary_safe, user_data.id, df)
    
    rate_limiter.end_upload(current_user_id)
    
    return {
        "status": "success",
        "file_id": str(user_data.id),
        "filename": filename,
        "pii_report": pii_report
    }


async def generate_ai_summary_safe(user_data_id: str, df: pd.DataFrame):
    """Generate AI summary using safe (potentially masked) data"""
    try:
        from app.utils.ai_summary import generate_dataset_summary
        
        # Use the masked dataframe for AI analysis
        summary = await generate_dataset_summary(df)
        
        # Update the user data record
        user_data = await UserData.get(user_data_id)
        if user_data:
            user_data.aiSummary = summary
            await user_data.save()
    
    except Exception as e:
        logger.error(f"Failed to generate AI summary for {user_data_id}: {e}")


@router.get("/cleanup")
async def cleanup_expired_sessions():
    """Admin endpoint to cleanup expired upload sessions"""
    cleaned = upload_handler.cleanup_expired_sessions()
    return {"cleaned_sessions": cleaned}