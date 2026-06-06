import boto3
import os
import re
from botocore.exceptions import ClientError, NoCredentialsError
from typing import Optional, Tuple
from urllib.parse import urlparse
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


def create_s3_client():
    """
    Create a boto3 S3 client from current environment variables.

    Honors the optional AWS_ENDPOINT_URL variable so S3-compatible storage
    (e.g. MinIO in CI, LocalStack locally) can be used transparently. When
    AWS_ENDPOINT_URL is unset, boto3 targets the default AWS endpoint.

    This is the single factory all backend S3 clients should be created
    through. Raises on failure (callers decide how to handle).
    """
    client_kwargs = {
        "aws_access_key_id": os.getenv("AWS_ACCESS_KEY_ID"),
        "aws_secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY"),
        "region_name": os.getenv("AWS_REGION", "us-east-1"),
    }
    endpoint_url = os.getenv("AWS_ENDPOINT_URL")
    if endpoint_url:
        client_kwargs["endpoint_url"] = endpoint_url
    return boto3.client("s3", **client_kwargs)


def parse_s3_url(s3_url: str) -> Tuple[Optional[str], str]:
    """
    Parse any persisted S3 URL shape into (bucket, key).

    Handles every format the app stores or has stored historically:
    - s3://{bucket}/{key}
    - {AWS_ENDPOINT_URL}/{bucket}/{key}      (MinIO/LocalStack, path-style)
    - https://{bucket}.s3.amazonaws.com/{key} (incl. presigned query strings)
    - any other http(s) URL: bucket is None, key is the URL path

    Returns:
        (bucket, key) — bucket is None when it cannot be determined from
        the URL; callers that need a bucket should fall back to the
        configured bucket name.

    Raises:
        ValueError: if no object key can be extracted.
    """
    bucket: Optional[str] = None
    key = ""

    if s3_url.startswith("s3://"):
        bucket, _, key = s3_url[5:].partition("/")
    else:
        endpoint_url = (os.getenv("AWS_ENDPOINT_URL") or "").rstrip("/")
        if endpoint_url and s3_url.startswith(endpoint_url):
            path = s3_url[len(endpoint_url):].lstrip("/")
            bucket, _, key = path.partition("/")
        else:
            match = re.match(r"https://([^.]+)\.s3\.amazonaws\.com/([^?]+)", s3_url)
            if match:
                bucket, key = match.group(1), match.group(2)
            elif urlparse(s3_url).scheme in ("http", "https"):
                key = urlparse(s3_url).path.lstrip("/")

    key = key.split("?")[0]
    if not key:
        raise ValueError(f"Invalid S3 URL format: {s3_url}")
    return bucket, key


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
        s3_client = create_s3_client()
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
        # Log upload attempt
        logger.info(f"Attempting to upload file to S3: {s3_filename} to bucket: {bucket_name}")
        logger.info(f"File size: {len(file_content)} bytes")
        
        # Upload the file without public access
        extra_args = {}
        if content_type:
            extra_args["ContentType"] = content_type

        client.upload_fileobj(
            io.BytesIO(file_content), bucket_name, s3_filename, ExtraArgs=extra_args
        )

        # Generate the URL (this will be a signed URL if needed for access)
        endpoint_url = os.getenv("AWS_ENDPOINT_URL")
        if endpoint_url:
            # S3-compatible storage (MinIO/LocalStack): path-style URL
            url = f"{endpoint_url.rstrip('/')}/{bucket_name}/{s3_filename}"
        else:
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

    # Parse the S3 URL to get bucket and key (all persisted URL shapes)
    try:
        bucket_name, key = parse_s3_url(s3_url)
        if bucket_name is None:
            # Legacy fallback: derive the bucket from the host's first label
            # (e.g. "bucket.s3.amazonaws.com" variants parse_s3_url doesn't map)
            netloc = urlparse(s3_url if "://" in s3_url else f"https://{s3_url}").netloc
            bucket_name = netloc.split(".")[0]
            if not bucket_name:
                raise ValueError(f"Invalid S3 URL format: {s3_url}")

        # Download the file to a BytesIO object
        file_obj = io.BytesIO()
        client.download_fileobj(bucket_name, key, file_obj)
        file_obj.seek(0)

        logger.info(f"File downloaded successfully from {s3_url}")
        return file_obj
    except Exception as e:
        logger.error(f"Error downloading file from S3: {e}")
        raise
