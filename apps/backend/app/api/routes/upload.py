from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Request
from typing import List, Dict, Any
import pandas as pd
import io
import traceback
import os
import boto3
from app.models.user_data import UserData, SchemaField
from app.auth.clerk_auth import get_current_user_id
from app.utils.schema_inference import infer_schema, generate_s3_filename
from app.utils.s3 import upload_file_to_s3
import logging

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/test")
async def test_endpoint():
    """
    A simple test endpoint to verify that the backend is working correctly.
    """
    return {"message": "Upload endpoint is working"}


@router.post("/")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    current_user_id: str = Depends(get_current_user_id),
) -> Dict[str, Any]:
    """
    Upload a file, infer its schema, store it in S3, and save metadata in MongoDB.
    Supports CSV, Excel, and TXT files.
    """
    try:
        # Log request details
        logger.info(
            f"Received file: {file.filename}, content_type: {file.content_type}"
        )

        # Read file content
        content = await file.read()
        logger.info(f"File content size: {len(content)} bytes")

        # Determine file type and read accordingly
        if file.filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content))
        elif file.filename.endswith(".xlsx"):
            df = pd.read_excel(io.BytesIO(content))
        elif file.filename.endswith(".txt"):
            df = pd.read_csv(io.BytesIO(content), sep="\t")
        else:
            raise HTTPException(
                status_code=400,
                detail="Unsupported file type. Please upload a CSV, Excel, or TXT file.",
            )

        # Get basic stats
        num_rows = len(df)
        num_columns = len(df.columns)

        # Infer schema
        schema_fields = infer_schema(df)

        # Generate a unique S3 filename
        s3_filename = generate_s3_filename(file.filename)

        # Check if AWS environment variables are set
        required_env_vars = [
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_BUCKET_NAME",
        ]
        missing_vars = [var for var in required_env_vars if not os.getenv(var)]

        if missing_vars:
            # If S3 is not configured, we'll still process the file and store metadata
            # but without the S3 URL
            logger.warning(
                f"S3 upload skipped: Missing environment variables: {', '.join(missing_vars)}"
            )
            s3_url = "s3_not_configured"
        else:
            # Log the environment variables (without sensitive values)
            logger.info("AWS environment variables:")
            for var in required_env_vars:
                value = os.getenv(var)
                if var in ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"]:
                    masked_value = value[:4] + "*" * (len(value) - 8) + value[-4:]
                    logger.info(f"{var}: {masked_value}")
                else:
                    logger.info(f"{var}: {value}")

            # Upload to S3
            logger.info(f"Attempting to upload file to S3: {s3_filename}")
            success, s3_url = upload_file_to_s3(content, s3_filename, file.content_type)

            if not success:
                logger.error("Failed to upload file to S3")
                s3_url = "s3_upload_failed"
            else:
                logger.info(f"File uploaded successfully to S3: {s3_url}")

                # Generate a signed URL for temporary access if needed
                try:
                    s3_client = boto3.client(
                        "s3",
                        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
                        region_name=os.getenv("AWS_REGION", "us-east-1"),
                    )

                    # Generate a signed URL that expires in 1 hour
                    signed_url = s3_client.generate_presigned_url(
                        "get_object",
                        Params={
                            "Bucket": os.getenv("AWS_BUCKET_NAME"),
                            "Key": s3_filename,
                        },
                        ExpiresIn=3600,  # 1 hour
                    )

                    logger.info(f"Generated signed URL for temporary access")
                    s3_url = signed_url
                except Exception as e:
                    logger.error(f"Failed to generate signed URL: {e}")
                    # Continue with the regular URL if signed URL generation fails

        # Create a new UserData document
        user_data = UserData(
            user_id=current_user_id,
            filename=file.filename,
            s3_url=s3_url,
            num_rows=num_rows,
            num_columns=num_columns,
            data_schema=schema_fields,
        )

        # Save to database
        await user_data.insert()
        logger.info(f"UserData document saved to database with ID: {user_data.id}")

        # Get preview data for response
        preview_data = df.head(10).values.tolist()
        headers = df.columns.tolist()

        return {
            "headers": headers,
            "previewData": preview_data,
            "fileName": file.filename,
            "fileType": file.content_type,
            "id": str(user_data.id),
            "s3_url": s3_url,
            "schema": schema_fields,
        }

    except Exception as e:
        # Log the full traceback
        logger.error(f"Error processing file: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")
