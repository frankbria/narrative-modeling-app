"""
Secure Upload API with PII detection and resumable uploads
"""

import io
import logging
import uuid
from typing import Any

import pandas as pd
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)

from app.auth.nextauth_auth import get_current_user_id
from app.billing.enforcement import quota
from app.models.user_data import UserData
from app.services.security.pii_detector import PIIDetector
from app.services.security.upload_handler import ChunkedUploadHandler, RateLimiter
from app.utils.s3 import upload_file_to_s3
from app.utils.schema_inference import generate_s3_filename, infer_schema
from app.utils.upload_limits import MAX_UPLOAD_BYTES, read_upload_capped

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize security services
pii_detector = PIIDetector()
upload_handler = ChunkedUploadHandler()
rate_limiter = RateLimiter()


@router.post("/secure", dependencies=[Depends(quota("uploads"))])
async def secure_upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
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
        
        if not file.filename:
            raise HTTPException(status_code=400, detail="Missing filename")

        # Read file content
        content = await read_upload_capped(file)

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
        
        # Generate unique S3 filename
        s3_filename = generate_s3_filename(file.filename)
        
        # Upload to S3
        logger.info(f"Uploading file {file.filename} to S3 as {s3_filename}")
        success, s3_url = upload_file_to_s3(content, s3_filename, content_type=file.content_type)
        
        if not success or not s3_url:
            logger.error(f"S3 upload failed for file {file.filename}")
            raise HTTPException(
                status_code=500,
                detail="Failed to upload file to S3. Please check AWS credentials and bucket configuration."
            )
        
        logger.info(f"S3 upload successful: {s3_url}")

        # Detect file type from extension
        file_ext = file.filename.lower().rsplit('.', 1)[-1] if '.' in file.filename else ''
        if file_ext == 'csv':
            file_type = "csv"
        elif file_ext in ('xls', 'xlsx'):
            file_type = "excel"
        elif file_ext == 'parquet':
            file_type = "parquet"
        else:
            # Fall back to content-type header if extension unclear
            content_type = file.content_type or ''
            if 'csv' in content_type:
                file_type = "csv"
            elif 'excel' in content_type or 'spreadsheet' in content_type:
                file_type = "excel"
            else:
                file_type = "csv"  # Default fallback

        # Create UserData record
        user_data = UserData(
            user_id=current_user_id,
            filename=file.filename,
            original_filename=file.filename,
            s3_url=s3_url,
            num_rows=len(df),
            num_columns=len(df.columns),
            data_schema=schema,
            file_type=file_type,
            columns=list(df.columns),
            data_preview=df.head(100).to_dict('records')
        )
        
        # Add PII information
        if pii_report["has_pii"]:
            user_data.pii_report = pii_report
            user_data.contains_pii = True
            user_data.pii_risk_level = pii_report["risk_level"]
        
        await user_data.insert()
        
        # Schedule background AI summary
        from app.utils.ai_summary import generate_dataset_summary
        background_tasks.add_task(generate_dataset_summary, str(user_data.id))
        
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
) -> dict[str, Any]:
    """
    Confirm upload of file with PII after user review
    """
    
    # Similar to secure_upload but skips PII blocking
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    content = await read_upload_capped(file)

    if file.filename.endswith('.csv'):
        df = pd.read_csv(io.BytesIO(content))
    elif file.filename.endswith(('.xlsx', '.xls')):
        df = pd.read_excel(io.BytesIO(content))
    
    # Detect PII
    pii_detections = pii_detector.detect_pii_in_dataframe(df)
    pii_report = pii_detector.generate_pii_report(pii_detections)
    
    # Generate unique S3 filename
    s3_filename = generate_s3_filename(file.filename)
    
    # Mask PII if requested
    if mask_pii and pii_detections:
        df_processed = pii_detector.mask_pii(df, pii_detections)
        # Upload masked version
        processed_content = df_processed.to_csv(index=False).encode()
        masked_filename = f"masked_{s3_filename}"
        success, s3_url = upload_file_to_s3(processed_content, masked_filename, content_type="text/csv")
    else:
        # Upload original
        success, s3_url = upload_file_to_s3(content, s3_filename, content_type=file.content_type)
        df_processed = df
    
    # Infer schema
    schema = infer_schema(df_processed)
    
    # Check upload success
    if not success or not s3_url:
        raise HTTPException(
            status_code=500,
            detail="Failed to upload file to S3"
        )
    
    # Create UserData record
    user_data = UserData(
        user_id=current_user_id,
        filename=file.filename,
        original_filename=file.filename,
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
    background_tasks.add_task(generate_ai_summary_safe, str(user_data.id), df_processed)
    
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
    filename: str = Form(...),
    file_size: int = Form(...),
    file_hash: str | None = Form(None),
    current_user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """
    Initialize chunked upload session for large files.

    These are Form fields, not query parameters: the client posts a
    url-encoded body (``useChunkedUpload.ts``), so the old query declaration
    made every init 422 before the handler ran (issue #463). The backend moved
    rather than the client — a POST body is the right place for a filename and
    a hash, and it keeps them out of URLs and access logs.
    """

    if not rate_limiter.check_concurrent_limit(current_user_id):
        raise HTTPException(
            status_code=429,
            detail="Too many concurrent uploads"
        )

    session_info = await upload_handler.init_upload(
        current_user_id, filename, file_size, file_hash
    )
    rate_limiter.start_upload(current_user_id)

    return session_info


@router.post("/chunked/{session_id}/chunk/{chunk_number}")
async def upload_chunk(
    session_id: str,
    chunk_number: int,
    chunk_hash: str | None = None,
    file: UploadFile = File(...),
    current_user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """
    Upload a single chunk
    """
    
    chunk_data = await read_upload_capped(file)
    # The concurrency slot is released by complete/abort, not here: this used to
    # decrement on the last chunk as well, so after one finished upload the
    # user's active count was pinned at 0 and the cap never bound again.
    return await upload_handler.upload_chunk(
        session_id, current_user_id, chunk_number, chunk_data, chunk_hash
    )


@router.get("/chunked/{session_id}/resume")
async def resume_chunked_upload(
    session_id: str,
    current_user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """
    Get resume information for interrupted upload
    """
    return await upload_handler.resume_upload(session_id, current_user_id)


@router.post(
    "/chunked/{session_id}/complete",
    dependencies=[Depends(quota("uploads"))],
)
async def complete_chunked_upload(
    session_id: str,
    background_tasks: BackgroundTasks,
    current_user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """
    Complete chunked upload and process file
    """
    
    session = upload_handler.get_session(session_id, current_user_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Upload session not found")

    temp_path = await upload_handler.complete_upload(session_id, current_user_id)

    # Cap the assembled-file read: chunked sessions allow very large files, so
    # reading the whole thing into memory here would reintroduce the memory-DoS
    # (issue #270). Reject over MAX_UPLOAD_BYTES before loading it into RAM.
    if temp_path.stat().st_size > MAX_UPLOAD_BYTES:
        upload_handler.abort_upload(session_id, current_user_id)
        temp_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum upload size is "
            f"{MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
        )

    # Process the complete file
    with open(temp_path, 'rb') as f:
        content = f.read()

    filename = session["filename"]

    # Load and process file (similar to secure_upload)
    if not filename.endswith(('.csv', '.xlsx', '.xls')):
        upload_handler.abort_upload(session_id, current_user_id)
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format: {filename}",
        )

    try:
        if filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(content))
            file_type, content_type = "csv", "text/csv"
        else:
            df = pd.read_excel(io.BytesIO(content))
            file_type, content_type = (
                "excel",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
    except Exception as e:
        # Matches /secure: a corrupt upload is the caller's 400, not a 500 that
        # also strands the assembled temp file.
        upload_handler.abort_upload(session_id, current_user_id)
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {str(e)}")

    # Detect PII
    pii_detections = pii_detector.detect_pii_in_dataframe(df)
    pii_report = pii_detector.generate_pii_report(pii_detections)

    # Upload to S3 under a server-derived, tenant-prefixed key. The client
    # filename must never reach the key: two tenants uploading data.csv used to
    # write the same unprefixed object, so the second silently destroyed the
    # first (issue #464). This adopts the datasets/{user_id}/... convention the
    # strict downloader, erasure and lifecycle rules expect; the non-chunked
    # routes in this module still write bare {uuid}.{ext} keys (tracked
    # separately).
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'csv'
    s3_key = f"datasets/{current_user_id}/{uuid.uuid4()}.{ext}"
    success, s3_url = upload_file_to_s3(content, s3_key, content_type=content_type)
    if not success or not s3_url:
        logger.error("S3 upload failed for chunked session %s", session_id)
        raise HTTPException(status_code=500, detail="Failed to upload file to S3")

    # Create UserData record
    schema = infer_schema(df)
    user_data = UserData(
        user_id=current_user_id,
        filename=filename,
        original_filename=filename,
        s3_url=s3_url,
        num_rows=len(df),
        num_columns=len(df.columns),
        data_schema=schema,
        file_type=file_type,
        columns=list(df.columns),
    )

    if pii_report["has_pii"]:
        user_data.pii_report = pii_report
        user_data.contains_pii = True
        user_data.pii_risk_level = pii_report["risk_level"]
    
    await user_data.insert()
    
    # Drop the session along with the temp file. Leaving it behind meant a
    # retried or double-clicked complete stat()'d a file the first call had
    # already unlinked, which is a 500 where a 404 is the honest answer.
    upload_handler.abort_upload(session_id, current_user_id)
    
    # Background AI summary
    if pii_report["has_pii"]:
        masked_df = pii_detector.mask_pii(df, pii_detections)
        background_tasks.add_task(generate_ai_summary_safe, str(user_data.id), masked_df)
    else:
        background_tasks.add_task(generate_ai_summary_safe, str(user_data.id), df)
    
    rate_limiter.end_upload(current_user_id)
    
    return {
        "status": "success",
        "file_id": str(user_data.id),
        "filename": filename,
        "pii_report": pii_report
    }


@router.delete("/chunked/{session_id}")
async def abort_chunked_upload(
    session_id: str,
    current_user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Abandon an in-flight chunked upload and drop its partial file."""
    if not upload_handler.abort_upload(session_id, current_user_id):
        raise HTTPException(status_code=404, detail="Upload session not found")


    rate_limiter.end_upload(current_user_id)
    return {"status": "aborted", "session_id": session_id}


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
async def cleanup_expired_sessions(
    current_user_id: str = Depends(get_current_user_id),
):
    """Reap expired upload sessions (temp files + metadata).

    Requires authentication (issue #272): the endpoint was previously
    unauthenticated, letting any network caller spam it. It only removes
    already-expired sessions, so any valid account is sufficient — there is no
    admin-role system to gate further, and the operation cannot touch active
    uploads. ponytail: per-worker in-memory sessions (see upload_handler); a
    scheduled reaper is the upgrade path if temp-file accumulation matters.
    """
    cleaned = upload_handler.cleanup_expired_sessions()
    return {"cleaned_sessions": cleaned}