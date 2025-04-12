import boto3
import os
from botocore.exceptions import ClientError, NoCredentialsError
from typing import Optional, Tuple
import logging
import io

# Suppress AWS logging
logging.getLogger("boto3").setLevel(logging.WARNING)
logging.getLogger("botocore").setLevel(logging.WARNING)
logging.getLogger("s3transfer").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

# Set up logging
logger = logging.getLogger(__name__)

# Initialize S3 client as None initially
s3_client = None
S3_BUCKET = None


def get_s3_client():
    """
    Get or create an S3 client with the current environment variables.
    This ensures we're using the most up-to-date environment variables.
    """
    global s3_client

    # Check for required environment variables
    required_env_vars = [
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_BUCKET_NAME",
    ]
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]

    if missing_vars:
        logger.warning(
            f"Missing required AWS environment variables: {', '.join(missing_vars)}"
        )
        return None

    try:
        # Create a new client with current environment variables
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name=os.getenv("AWS_REGION", "us-east-1"),
        )
        logger.info("S3 client initialized successfully")
        return s3_client
    except Exception as e:
        logger.error(f"Failed to initialize S3 client: {e}")
        return None


def upload_file_to_s3(
    file_content: bytes, s3_filename: str, content_type: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """
    Upload a file to S3.

    Args:
        file_content: The content of the file as bytes
        s3_filename: The filename to use in S3
        content_type: The content type of the file (optional)

    Returns:
        A tuple of (success, url)
        - success: Boolean indicating if the upload was successful
        - url: The public URL of the uploaded file, or None if upload failed
    """
    # Get the S3 client with current environment variables
    client = get_s3_client()
    if client is None:
        return False, None

    # Get the bucket name
    bucket_name = os.getenv("AWS_BUCKET_NAME")
    if not bucket_name:
        logger.error("AWS_BUCKET_NAME environment variable not set")
        return False, None

    try:
        # Upload the file without public access
        extra_args = {}
        if content_type:
            extra_args["ContentType"] = content_type

        client.upload_fileobj(
            io.BytesIO(file_content), bucket_name, s3_filename, ExtraArgs=extra_args
        )

        # Generate the URL (this will be a signed URL if needed for access)
        url = f"https://{bucket_name}.s3.amazonaws.com/{s3_filename}"

        logger.info(f"File uploaded successfully to {url}")
        return True, url

    except NoCredentialsError:
        logger.error("AWS credentials not found or invalid")
        return False, None
    except ClientError as e:
        logger.error(f"Error uploading file to S3: {e}")
        return False, None
    except Exception as e:
        logger.error(f"Unexpected error uploading file to S3: {e}")
        return False, None


def get_file_from_s3(s3_url: str) -> io.BytesIO:
    """
    Download a file from S3 using its URL.

    Args:
        s3_url: The S3 URL of the file to download

    Returns:
        A BytesIO object containing the file content
    """
    # Get the S3 client
    client = get_s3_client()
    if client is None:
        raise Exception("Failed to initialize S3 client")

    # Parse the S3 URL to get bucket and key
    # URL format: https://bucket-name.s3.amazonaws.com/key
    try:
        # Remove the https:// prefix if present
        if s3_url.startswith("https://"):
            s3_url = s3_url[8:]

        # Split by the first slash to separate bucket and key
        parts = s3_url.split("/", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid S3 URL format: {s3_url}")

        bucket_name = parts[0].split(".")[0]  # Remove .s3.amazonaws.com
        key = parts[1]

        # Download the file to a BytesIO object
        file_obj = io.BytesIO()
        client.download_fileobj(bucket_name, key, file_obj)
        file_obj.seek(0)

        logger.info(f"File downloaded successfully from {s3_url}")
        return file_obj
    except Exception as e:
        logger.error(f"Error downloading file from S3: {e}")
        raise
