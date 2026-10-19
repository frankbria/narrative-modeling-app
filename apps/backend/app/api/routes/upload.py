import io
import logging
import os
from typing import Any

import pandas as pd
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Request,
    UploadFile,
)

from app.auth.nextauth_auth import get_current_user_id
from app.billing.enforcement import quota
from app.billing.storage import enforce_storage_ceiling
from app.models.user_data import UserData
from app.utils.ai_summary import generate_dataset_summary
from app.utils.s3 import (
    allowed_bucket,
    configured_bucket,
    create_s3_client,
    dataset_s3_key,
    upload_file_to_s3,
)
from app.utils.schema_inference import infer_schema
from app.utils.upload_limits import read_upload_capped, require_rows

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter()


def _frame_of(filename: str, content: bytes) -> pd.DataFrame:
    """The upload as a frame: 400 for an unsupported type or a header with no rows (#1062)."""
    if filename.endswith(".csv"):
        df = pd.read_csv(io.BytesIO(content))
    elif filename.endswith(".xlsx"):
        df = pd.read_excel(io.BytesIO(content))
    elif filename.endswith(".txt"):
        df = pd.read_csv(io.BytesIO(content), sep="\t")
    else:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Please upload a CSV, Excel, or TXT file.",
        )
    require_rows(df)
    return df


def _require_s3_configured() -> None:
    """503 when this deployment cannot store files — an operator fix, not a retry.

    Was: carry on with `s3_url = "s3_not_configured"` and return 200, a dataset row
    whose s3_url is a placeholder that every later read fails on (#459). The refund
    middleware returns the unit.
    """
    missing_vars = [
        var for var in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY") if not os.getenv(var)
    ]
    # The bucket goes through the ONE resolver, not a hardcoded env name (#507).
    if not configured_bucket():
        missing_vars.append("a configured S3 bucket")
    if missing_vars:
        logger.error(
            f"S3 is not configured; refusing upload. Missing: {', '.join(missing_vars)}"
        )
        raise HTTPException(
            status_code=503,
            detail="File storage is not configured on this deployment.",
        )


def _signed(url: str, s3_filename: str) -> str:
    """A signed URL valid for an hour, or the plain one when signing fails."""
    try:
        signed_url = create_s3_client().generate_presigned_url(
            "get_object",
            # Same resolver the writer used, so the signed URL points at the bucket
            # the object was written to (#507).
            Params={"Bucket": allowed_bucket(), "Key": s3_filename},
            ExpiresIn=3600,
        )
    except Exception as e:
        logger.error(f"Failed to generate signed URL: {e}")
        return url
    logger.info("Generated signed URL for temporary access")
    return str(signed_url)


def _stored(user_id: str, filename: str, content: bytes, content_type: str | None) -> str:
    """Put the bytes in S3 under an owner-prefixed, server-derived key (#581) and return a
    URL for them. 503 / 500 when storage is unconfigured / the put fails: the old
    placeholder-string `s3_url` made every later read of the dataset fail (#459)."""
    s3_filename = dataset_s3_key(user_id, filename)
    _require_s3_configured()
    logger.info(f"Attempting to upload file to S3: {s3_filename}")
    success, upload_url = upload_file_to_s3(content, s3_filename, content_type)
    if not success or not upload_url:
        logger.error("Failed to upload file to S3")
        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to upload file to S3. Please check AWS credentials "
                "and bucket configuration."
            ),
        )
    logger.info(f"File uploaded successfully to S3: {upload_url}")
    return _signed(upload_url, s3_filename)


def _file_type(filename: str) -> str | None:
    """The extension — model training routes on it (csv, xls, xlsx, parquet)."""
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else None


def _upload_response(
    df: pd.DataFrame,
    user_data: UserData,
    schema_fields: Any,
    filename: str,
    content_type: str | None,
    s3_url: str,
) -> dict[str, Any]:
    return {
        "status": "success",
        "file_id": str(user_data.id),
        "filename": filename,
        "num_rows": user_data.num_rows,
        "num_columns": user_data.num_columns,
        "preview": df.head(5).to_dict('records'),
        "pii_report": {
            "has_pii": False,
            "detections": [],
            "risk_level": "none",
            "total_detections": 0,
            "affected_columns": []
        },
        "headers": df.columns.tolist(),
        "previewData": df.head(10).values.tolist(),
        "fileName": filename,
        "fileType": content_type,
        "id": str(user_data.id),
        "s3_url": s3_url,
        "schema": schema_fields,
    }


@router.post("/", dependencies=[Depends(quota("uploads"))])
async def upload_file(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """
    Upload a file, infer its schema, store it in S3, and save metadata in MongoDB.
    Supports CSV, Excel, and TXT files.
    """
    try:
        logger.info(
            f"Received file: {file.filename}, content_type: {file.content_type}"
        )

        # Ensure a filename is present before reading the upload into memory
        if not file.filename:
            raise HTTPException(
                status_code=400,
                detail="Missing filename. Please upload a CSV, Excel, or TXT file.",
            )

        content = await read_upload_capped(file)
        logger.info(f"File content size: {len(content)} bytes")
        await enforce_storage_ceiling(current_user_id, len(content))

        df = _frame_of(file.filename, content)
        schema_fields = infer_schema(df)
        s3_url = _stored(current_user_id, file.filename, content, file.content_type)

        user_data = UserData(
            user_id=current_user_id,
            filename=file.filename,
            original_filename=file.filename,
            file_type=_file_type(file.filename),
            s3_url=s3_url,
            num_rows=len(df),
            num_columns=len(df.columns),
            data_schema=schema_fields,
            file_size=len(content),
        )
        await user_data.insert()
        logger.info(f"UserData document saved to database with ID: {user_data.id}")

        background_tasks.add_task(generate_dataset_summary, str(user_data.id))
        logger.info(
            f"Added AI summary generation to background tasks for dataset {user_data.id}"
        )

        return _upload_response(
            df, user_data, schema_fields, file.filename, file.content_type, s3_url
        )

    except HTTPException:
        # Preserve client errors (e.g. 400 bad file, 413 too large) instead of
        # re-wrapping them as a 500.
        raise
    except Exception as e:
        logger.exception("Error processing file: %s", e)
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")
