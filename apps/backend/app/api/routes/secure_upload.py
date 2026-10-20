"""
Secure Upload API with PII detection and resumable uploads
"""

import io
import logging
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)

from app.auth.nextauth_auth import get_current_user_id
from app.billing.enforcement import quota, release
from app.billing.storage import enforce_storage_ceiling
from app.models.user_data import UserData
from app.services.security.pii_detector import PIIDetector
from app.services.security.upload_handler import ChunkedUploadHandler, RateLimiter
from app.utils.s3 import dataset_s3_key, upload_file_to_s3
from app.utils.schema_inference import infer_schema
from app.utils.upload_limits import MAX_UPLOAD_BYTES, read_upload_capped, require_rows

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize security services
pii_detector = PIIDetector()
upload_handler = ChunkedUploadHandler()
rate_limiter = RateLimiter()


_ALLOWED_TYPES = (
    "text/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

#: Case-sensitive on purpose: `/secure` has always matched the extension as sent.
_READERS = {".csv": pd.read_csv, ".xlsx": pd.read_excel, ".xls": pd.read_excel}

_CONTENT_TYPES = {
    ".csv": "text/csv",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
}


def _suffix(filename: str) -> str:
    return filename[filename.rfind("."):]


def _file_type_of(filename: str) -> str:
    """`csv` or `excel` — the only two a parsed upload can be (`_parsed_frame` refuses the rest)."""
    return "csv" if filename.endswith(".csv") else "excel"


def _admit(user_id: str) -> None:
    """Per-user rate and concurrency limits; on return an upload slot is held (the caller
    releases it in a `finally`)."""
    if not rate_limiter.check_rate_limit(user_id):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please wait before uploading again."
        )

    # One shared budget across /secure and chunked (#526): reap stale chunked
    # sessions first so they don't count, then check the combined total.
    _release_expired_slots()
    if _active_upload_count(user_id) >= rate_limiter.max_concurrent_uploads:
        raise HTTPException(
            status_code=429,
            detail="Too many concurrent uploads. Please wait for current uploads to complete."
        )

    rate_limiter.record_request(user_id)
    rate_limiter.start_upload(user_id)


def _validated_name(file: UploadFile) -> str:
    if file.content_type not in _ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}"
        )
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")
    return file.filename


def _parsed_frame(filename: str, content: bytes) -> pd.DataFrame:
    """The upload as a frame: 400 for an unsupported extension, bytes that do not parse,
    or a header with no data rows (#1062). Runs before the S3 put."""
    reader = _READERS.get(_suffix(filename))
    if reader is None:
        raise HTTPException(status_code=400, detail="Unsupported file format")
    try:
        df = reader(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to parse file: {str(e)}"
        )
    require_rows(df)
    return df


def _secure_frame(filename: str, content: bytes) -> pd.DataFrame:
    df = _parsed_frame(filename, content)
    if len(df) > 10_000_000:  # 10M rows limit
        raise HTTPException(
            status_code=413,
            detail="File too large. Maximum 10 million rows allowed."
        )
    return df


def _pii_confirmation(pii_report: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "pii_detected",
        "pii_report": pii_report,
        "message": "High-risk PII detected. Please review and confirm upload.",
        "requires_confirmation": True
    }


def _put_in_s3(user_id: str, filename: str, content: bytes, content_type: str | None) -> str:
    """Store the bytes under a server-derived key; 500 when the put fails."""
    s3_filename = dataset_s3_key(user_id, filename)
    logger.info(f"Uploading file {filename} to S3 as {s3_filename}")
    success, s3_url = upload_file_to_s3(content, s3_filename, content_type=content_type)
    if not success or not s3_url:
        logger.error(f"S3 upload failed for file {filename}")
        raise HTTPException(
            status_code=500,
            detail="Failed to upload file to S3. Please check AWS credentials and bucket configuration."
        )
    logger.info(f"S3 upload successful: {s3_url}")
    return s3_url


async def _store_secure(
    user_id: str,
    file: UploadFile,
    content: bytes,
    df: pd.DataFrame,
    pii_report: dict[str, Any],
) -> UserData:
    filename = str(file.filename)
    schema = infer_schema(df)
    s3_url = _put_in_s3(user_id, filename, content, file.content_type)
    user_data = UserData(
        user_id=user_id,
        filename=filename,
        original_filename=filename,
        s3_url=s3_url,
        num_rows=len(df),
        num_columns=len(df.columns),
        data_schema=schema,
        file_type=_file_type_of(filename),
        file_size=len(content),
        columns=list(df.columns),
        data_preview=df.head(100).to_dict('records')
    )
    if pii_report["has_pii"]:
        user_data.pii_report = pii_report
        user_data.contains_pii = True
        user_data.pii_risk_level = pii_report["risk_level"]
    await user_data.insert()
    return user_data


def _schedule_summary(
    background_tasks: BackgroundTasks,
    user_data: UserData,
    df: pd.DataFrame,
    pii_report: dict[str, Any],
    pii_detections: list[Any],
) -> None:
    """The background AI summary. For a dataset the detector flagged (medium risk here —
    high risk returned earlier), summarize a PII-masked frame so the flagged columns'
    sample values never reach OpenAI, exactly like the sibling secure paths (#490, #679).
    The stored-schema summary (generate_dataset_summary) ships raw example_values, so it
    is only for a clean dataset with nothing to mask."""
    if pii_report["has_pii"]:
        background_tasks.add_task(
            generate_ai_summary_safe,
            str(user_data.id),
            _summary_frame(df, pii_detections),
        )
    else:
        from app.utils.ai_summary import generate_dataset_summary
        background_tasks.add_task(generate_dataset_summary, str(user_data.id))


@router.post("/secure", dependencies=[Depends(quota("uploads"))])
async def secure_upload(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """
    Secure file upload with PII detection and validation
    """
    _admit(current_user_id)

    try:
        filename = _validated_name(file)
        content = await read_upload_capped(file)
        await enforce_storage_ceiling(current_user_id, len(content))
        df = _secure_frame(filename, content)

        pii_detections = pii_detector.detect_pii_in_dataframe(df)
        pii_report = pii_detector.generate_pii_report(pii_detections)

        # If high-risk PII found, block upload unless explicitly allowed
        if pii_report["risk_level"] == "high":
            # No dataset was created, so give the unit back. The refund middleware
            # only sees >= 400 and this branch answers 200, so without this the
            # tenant pays here for nothing and pays again at /confirm-pii-upload —
            # two units for the one dataset they end up with (#459).
            await release(request)
            return _pii_confirmation(pii_report)

        user_data = await _store_secure(current_user_id, file, content, df, pii_report)
        _schedule_summary(background_tasks, user_data, df, pii_report, pii_detections)

        return {
            "status": "success",
            "file_id": str(user_data.id),
            "filename": filename,
            "num_rows": len(df),
            "num_columns": len(df.columns),
            "pii_report": pii_report,
            "preview": df.head(5).to_dict('records')
        }

    finally:
        rate_limiter.end_upload(current_user_id)


def _read_confirmed(filename: str, content: bytes) -> pd.DataFrame:
    if filename.endswith('.csv'):
        return pd.read_csv(io.BytesIO(content))
    if filename.endswith(('.xlsx', '.xls')):
        return pd.read_excel(io.BytesIO(content))
    # A clean 400, as /secure answers for the same file (#459).
    raise HTTPException(status_code=400, detail=f"Unsupported file format: {filename}")


def _store_confirmed(
    user_id: str, filename: str, content_type: str | None, content: bytes, masked: pd.DataFrame | None
) -> tuple[str, str, int]:
    """Write the confirmed upload: `(s3_url, file_type, stored size)`.

    The type is the type of the bytes written (#937). A masked copy is CSV whatever
    was uploaded, so its key ends in `.csv` too; it used to keep the upload's
    extension, which left a masked workbook as CSV under an `.xlsx` name.
    """
    if masked is not None:
        body, file_type, content_type = masked.to_csv(index=False).encode(), "csv", "text/csv"
        key = dataset_s3_key(user_id, "masked.csv", masked=True)
    else:
        body, file_type = content, filename.rsplit(".", 1)[-1].lower()
        key = dataset_s3_key(user_id, filename)
    success, s3_url = upload_file_to_s3(body, key, content_type=content_type)
    if not success or not s3_url:
        raise HTTPException(status_code=500, detail="Failed to upload file to S3")
    return s3_url, file_type, len(body)


@router.post("/confirm-pii-upload", dependencies=[Depends(quota("uploads"))])
async def confirm_pii_upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    mask_pii: bool = True,
    current_user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """
    Confirm upload of file with PII after user review
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    content = await read_upload_capped(file)
    # The original's size; a masked copy differs by a few bytes per masked cell.
    await enforce_storage_ceiling(current_user_id, len(content))

    df = _read_confirmed(file.filename, content)
    require_rows(df)
    pii_detections = pii_detector.detect_pii_in_dataframe(df)
    pii_report = pii_detector.generate_pii_report(pii_detections)

    masking = mask_pii and bool(pii_detections)
    df_processed = pii_detector.mask_pii(df, pii_detections) if masking else df
    s3_url, file_type, stored_size = _store_confirmed(
        current_user_id, file.filename, file.content_type, content, df_processed if masking else None
    )
    schema = infer_schema(df_processed)

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
        pii_masked=mask_pii,
        file_type=file_type,
        file_size=stored_size,
    )
    
    await user_data.insert()
    
    # Summarize a PII-masked frame regardless of the storage masking choice (#490).
    background_tasks.add_task(
        generate_ai_summary_safe, str(user_data.id), _summary_frame(df, pii_detections)
    )
    
    return {
        "status": "success",
        "file_id": str(user_data.id),
        "filename": file.filename,
        "pii_masked": mask_pii,
        "pii_report": pii_report,
        "preview": df_processed.head(5).to_dict('records')
    }


def _active_upload_count(user_id: str) -> int:
    """One per-user concurrency budget across BOTH upload surfaces (#526):
    live chunked sessions (init→last chunk) PLUS in-flight transient work counted
    on `RateLimiter.active_uploads` — every `/upload/secure` request and every
    chunked `complete` finalization (parse + S3 + insert). Chunked sessions are
    self-healing (an abandoned one stops counting at expiry, no counter to leak);
    the transient counter is always `finally`-balanced, so it can't leak either.
    Counting both keeps the cap a single shared limit, not two separate pools."""
    return upload_handler.count_active_sessions(user_id) + rate_limiter.active_uploads.get(user_id, 0)


def _release_expired_slots() -> list[str]:
    """Reap expired chunked sessions (removes them from the store and deletes their
    partial temp files). The chunked concurrency limit is now derived from the live
    sessions themselves (#526), so there is no separate counter to hand a slot back
    to — reaping is what makes an abandoned session stop counting."""
    return upload_handler.cleanup_expired_sessions()


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

    # Reap expired sessions first (cleans their partial temp files), then derive the
    # concurrency limit from the caller's LIVE sessions rather than a separate
    # counter (#526). An abandoned session — closed tab, dropped connection — stops
    # counting the moment it expires, so it can never permanently lock the user out;
    # there is no counter to leak when complete/abort don't run. (The old counter
    # pinned at 0 while the chunk route double-released, hiding the cap; once the cap
    # bound for real, ten abandoned sessions 429'd the user forever.)
    _release_expired_slots()

    if _active_upload_count(current_user_id) >= rate_limiter.max_concurrent_uploads:
        raise HTTPException(
            status_code=429,
            detail="Too many concurrent uploads"
        )

    # Refuse up front on the declared size (#768) rather than after the transfer;
    # /complete re-checks against the bytes that actually arrived. An oversize
    # declaration is init_upload's 413 to give, not a storage 402.
    if 0 <= file_size <= MAX_UPLOAD_BYTES:
        await enforce_storage_ceiling(current_user_id, file_size)

    # No rate_limiter.start_upload: the new session itself is the count (see above),
    # so complete/abort/expiry need no matching decrement.
    return await upload_handler.init_upload(
        current_user_id, filename, file_size, file_hash
    )


@router.post("/chunked/{session_id}/chunk/{chunk_number}")
async def upload_chunk(
    session_id: str,
    chunk_number: int,
    # Form, not a bare default: the request is multipart, so an undecorated
    # parameter is a query param — the same client/server mismatch that made
    # init unreachable (issue #463). Latent only because no client sends it.
    chunk_hash: str | None = Form(None),
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


async def _admit_assembled(user_id: str, temp_path: Path, filename: str) -> None:
    """Refuse the assembled file before reading it into memory."""
    # Cap the assembled-file read: chunked sessions allow very large files, so reading
    # the whole thing into memory would reintroduce the memory-DoS (issue #270).
    size = temp_path.stat().st_size
    if size > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum upload size is "
            f"{MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
        )
    await enforce_storage_ceiling(user_id, size)

    if not filename.lower().endswith(tuple(_READERS)):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format: {filename}",
        )


async def _store_chunked(
    user_id: str,
    filename: str,
    content: bytes,
    df: pd.DataFrame,
    pii_report: dict[str, Any],
    masked: pd.DataFrame | None = None,
) -> UserData:
    """Store the assembled upload; `masked` is the confirmed, PII-masked copy that
    replaces the original (key, bytes, preview and schema all follow it, #1122)."""
    # Under a server-derived, tenant-prefixed key. The client filename must never reach
    # the key: two tenants uploading data.csv used to write the same unprefixed object,
    # so the second silently destroyed the first (issue #464).
    lowered = filename.lower()
    s3_url, _, stored_size = _store_confirmed(
        user_id, lowered, _CONTENT_TYPES[_suffix(lowered)], content, masked
    )
    shown = df if masked is None else masked

    user_data = UserData(
        user_id=user_id,
        filename=filename,
        original_filename=filename,
        s3_url=s3_url,
        num_rows=len(shown),
        num_columns=len(shown.columns),
        data_schema=infer_schema(shown),
        file_type=_file_type_of(lowered) if masked is None else "csv",
        file_size=stored_size,
        columns=list(shown.columns),
        data_preview=shown.head(100).to_dict('records'),
        pii_masked=masked is not None,
    )
    if pii_report["has_pii"]:
        user_data.pii_report = pii_report
        user_data.contains_pii = True
        user_data.pii_risk_level = pii_report["risk_level"]
    await user_data.insert()
    return user_data


def _claimed(session_id: str, user_id: str) -> dict[str, Any]:
    """Claiming removes the session, so a concurrent or retried finish gets a clean 404
    instead of racing to a second S3 object, a second UserData row and a second charged
    quota unit."""
    session = upload_handler.claim_upload(session_id, user_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Upload session not found")
    return session


async def _scanned(
    user_id: str, temp_path: Path, filename: str
) -> tuple[bytes, pd.DataFrame, list[Any], dict[str, Any]]:
    """The assembled file, admitted, parsed and scanned for PII."""
    await _admit_assembled(user_id, temp_path, filename)
    content = temp_path.read_bytes()
    df = _parsed_frame(filename.lower(), content)
    pii_detections = pii_detector.detect_pii_in_dataframe(df)
    return content, df, pii_detections, pii_detector.generate_pii_report(pii_detections)


async def _hold_for_confirmation(
    request: Request, session: dict[str, Any], pii_report: dict[str, Any]
) -> dict[str, Any]:
    """Pause a high-risk chunked upload exactly as `/secure` does (#1122): nothing is
    stored, the session keeps the assembled file so `/confirm` can store it, and the
    unit is handed back because no dataset was created (#459)."""
    upload_handler.hold_upload(session)
    await release(request)
    return {**_pii_confirmation(pii_report), "session_id": session["id"]}


async def _store_and_summarise(
    background_tasks: BackgroundTasks,
    user_id: str,
    filename: str,
    scan: tuple[bytes, pd.DataFrame, list[Any], dict[str, Any]],
    mask_pii: bool | None,
) -> dict[str, Any]:
    content, df, pii_detections, pii_report = scan
    masked = pii_detector.mask_pii(df, pii_detections) if mask_pii and pii_detections else None
    user_data = await _store_chunked(user_id, filename, content, df, pii_report, masked)

    # Background AI summary — always over a PII-masked frame (#490).
    background_tasks.add_task(
        generate_ai_summary_safe, str(user_data.id), _summary_frame(df, pii_detections)
    )
    return {
        "status": "success",
        "file_id": str(user_data.id),
        "filename": filename,
        "pii_masked": masked is not None,
        "pii_report": pii_report,
    }


async def _finish_chunked(
    request: Request,
    session_id: str,
    background_tasks: BackgroundTasks,
    user_id: str,
    mask_pii: bool | None,
) -> dict[str, Any]:
    """`mask_pii` is None at completion (a high-risk file is held) and the user's
    choice at confirmation (the file is stored)."""
    session = _claimed(session_id, user_id)
    temp_path = Path(session["temp_path"])

    # Claiming popped the session, so it no longer counts via count_active_sessions.
    # The finalization below (parse + S3 upload + insert) is real, resource-heavy
    # work, so keep it counted toward the shared cap via a transient slot (#526) —
    # released on EVERY exit by the finally, so it can never leak.
    rate_limiter.start_upload(user_id)

    # The slot and the assembled temp file are released on *every* exit, not just the
    # successful one — except a held file, which the session owns again. Releasing only
    # on success meant a handful of corrupt uploads pinned a user at the concurrency
    # cap with no session left to abort, and 429'd their every subsequent init.
    held = False
    try:
        scan = await _scanned(user_id, temp_path, session["filename"])
        if mask_pii is None and scan[3]["risk_level"] == "high":
            held = True
            return await _hold_for_confirmation(request, session, scan[3])
        return await _store_and_summarise(
            background_tasks, user_id, session["filename"], scan, mask_pii
        )
    finally:
        if not held:
            temp_path.unlink(missing_ok=True)
        rate_limiter.end_upload(user_id)  # release the finalization slot (#526)


@router.post(
    "/chunked/{session_id}/complete",
    dependencies=[Depends(quota("uploads"))],
)
async def complete_chunked_upload(
    request: Request,
    session_id: str,
    background_tasks: BackgroundTasks,
    current_user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """
    Complete chunked upload and process file. A high-risk PII finding answers
    `pii_detected` and stores nothing until `/confirm` (#1122).
    """
    return await _finish_chunked(request, session_id, background_tasks, current_user_id, None)


@router.post(
    "/chunked/{session_id}/confirm",
    dependencies=[Depends(quota("uploads"))],
)
async def confirm_chunked_upload(
    request: Request,
    session_id: str,
    background_tasks: BackgroundTasks,
    mask_pii: bool = True,
    current_user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Store the held upload of a `pii_detected` completion, masked or as uploaded
    (the same choice as `/confirm-pii-upload`)."""
    return await _finish_chunked(request, session_id, background_tasks, current_user_id, mask_pii)


@router.delete("/chunked/{session_id}")
async def abort_chunked_upload(
    session_id: str,
    current_user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Abandon an in-flight chunked upload and drop its partial file (AC3 — the UI
    calls this to release an upload the user no longer wants)."""
    if not upload_handler.abort_upload(session_id, current_user_id):
        raise HTTPException(status_code=404, detail="Upload session not found")

    # No rate_limiter.end_upload: abort popped the session, so it no longer counts (#526).
    return {"status": "aborted", "session_id": session_id}


def _summary_frame(df: pd.DataFrame, pii_detections) -> pd.DataFrame:
    """The frame to hand the AI summary task: EVERY flagged column redacted, so the
    summary never ships PII to OpenAI — regardless of whether the caller chose to
    mask their *stored* copy (``mask_pii=False`` is a storage choice, not consent
    to send PII to a third party) (#490).

    Every column that produced a detection, whatever its confidence (#679): a weak
    value-pattern match still sets ``has_pii`` and routes here.

    Redacted, not masked (#718). ``PIIDetector.mask_pii`` is for the stored copy and
    keeps part of each value so a person can still read it: the first and last
    character and the length of a name, the last four digits of an SSN or a card, an
    email's domain. A third party gets none of that.
    """
    if not pii_detections:
        return df
    safe = df.copy()
    for column in {detection.column_name for detection in pii_detections}:
        safe[column] = _redacted(safe[column])
    return safe


def _redacted(column: pd.Series) -> pd.Series:
    """Each distinct value as a numbered token, missing values left missing.

    The summary still sees the column's shape (how many values, how many distinct),
    so what it says about the column stays true, and nothing of a value itself.
    """
    codes, _ = pd.factorize(column)
    tokens = pd.Series([f"[redacted {code + 1}]" for code in codes], index=column.index, dtype=object)
    return tokens.where(column.notna(), column)


async def generate_ai_summary_safe(user_data_id: str, df: pd.DataFrame):
    """Generate the AI summary from the safe (already-masked) DataFrame (#490).

    The summary is built from ``df`` — the frame the caller masked — NOT from the
    stored ``data_schema``: the chunked-upload path stores a raw schema, so
    delegating to ``generate_dataset_summary(user_data_id)`` would ship raw PII
    ``example_values`` to OpenAI. Degrades gracefully but never silently: a null
    result or an error is logged at WARNING with the dataset id (the previous
    version passed the DataFrame where a str id was expected, so every call
    raised and was swallowed, leaving the summary permanently null).
    """
    try:
        from app.utils.ai_summary import (
            call_openai_api,
            prepare_dataset_summary_from_df,
        )

        user_data = await UserData.get(user_data_id)
        if not user_data:
            logger.warning("AI summary skipped: dataset %s not found", user_data_id)
            return

        summary = await call_openai_api(
            prepare_dataset_summary_from_df(df, user_data.filename)
        )
        if summary is None:
            logger.warning(
                "AI summary not generated for dataset %s (OpenAI unavailable or "
                "no key); leaving it unset",
                user_data_id,
            )
            return

        # Only this field: the copy read before the model call is stale by now (#983).
        await user_data.set({UserData.aiSummary: summary})
        logger.info("AI summary generated for dataset %s", user_data_id)
    except Exception as e:
        logger.warning("Failed to generate AI summary for dataset %s: %s", user_data_id, e)


@router.get("/cleanup")
async def cleanup_expired_sessions(
    current_user_id: str = Depends(get_current_user_id),
):
    """Reap expired upload sessions (temp files + metadata).

    Requires authentication (issue #272): the endpoint was previously
    unauthenticated, letting any network caller spam it. It only removes
    already-expired sessions, so any valid account is sufficient — there is no
    admin-role system to gate further, and the operation cannot touch active
    uploads. The same sweep runs at the start of every upload, and since #584 it
    also reaps sessions a restart left on disk, so there is no scheduled reaper.
    """
    return {"cleaned_sessions": len(_release_expired_slots())}