import boto3
import os
import tempfile
import logging
import re
from urllib.parse import unquote
from botocore.exceptions import ClientError

from app.utils.circuit_breaker import with_circuit_breaker, with_sync_circuit_breaker

logger = logging.getLogger(__name__)


@with_sync_circuit_breaker(
    "s3",
    max_attempts=3,
    failure_threshold=5,
    recovery_timeout=60.0,
    exceptions=(ClientError, ValueError)
)
def download_file_from_s3(s3_url: str) -> str:
    """
    Download a file from S3 and save it to a temporary location.

    Security validations:
    - Bucket whitelist enforcement
    - Path traversal prevention
    - Path structure validation
    - File size limit enforcement

    Args:
        s3_url (str): The S3 URL of the file to download

    Returns:
        str: The path to the downloaded file

    Raises:
        ValueError: If S3 URL is invalid, bucket not allowed, path traversal detected,
                    invalid path structure, or file too large
    """
    try:
        # SECURITY: Get allowed bucket from environment
        ALLOWED_BUCKET = os.getenv("AWS_S3_BUCKET")
        if not ALLOWED_BUCKET:
            raise ValueError("AWS_S3_BUCKET environment variable not set")

        # SECURITY: Validate S3 URL format and bucket whitelist
        # Pattern enforces: https://{bucket}.s3.amazonaws.com/{path}
        s3_pattern = r"https://([^\.]+)\.s3\.amazonaws\.com/([^?]+)"
        match = re.match(s3_pattern, s3_url)

        if not match:
            raise ValueError(f"Invalid S3 URL format: {s3_url}")

        bucket_name = match.group(1)
        object_key = match.group(2)

        # SECURITY: Enforce bucket whitelist
        if bucket_name != ALLOWED_BUCKET:
            logger.error(f"Access denied: bucket '{bucket_name}' not in whitelist (allowed: {ALLOWED_BUCKET})")
            raise ValueError(f"Access denied: S3 bucket '{bucket_name}' not allowed")

        # URL decode the object key
        object_key = unquote(object_key)

        # SECURITY: Prevent path traversal attacks
        if '..' in object_key or object_key.startswith('/'):
            logger.error(f"Path traversal detected in S3 key: {object_key}")
            raise ValueError("Invalid S3 path: path traversal detected")

        # SECURITY: Validate path structure (datasets/{user_id}/{filename})
        # Allow flexible structure but prevent malicious patterns
        path_pattern = r'^datasets/[a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+$'
        if not re.match(path_pattern, object_key):
            logger.error(f"Invalid S3 path structure: {object_key}")
            raise ValueError("Invalid S3 path structure: must match 'datasets/{user_id}/{filename}'")

        # Initialize S3 client
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name=os.getenv("AWS_REGION", "us-east-1"),
        )

        # SECURITY: Check file size before downloading to prevent DoS
        try:
            response = s3_client.head_object(Bucket=bucket_name, Key=object_key)
            file_size = response['ContentLength']

            # Maximum file size: 1 GB
            MAX_FILE_SIZE = 1024 * 1024 * 1024
            if file_size > MAX_FILE_SIZE:
                logger.error(f"File too large: {file_size} bytes (max {MAX_FILE_SIZE})")
                raise ValueError(f"File too large: {file_size} bytes exceeds maximum {MAX_FILE_SIZE} bytes (1 GB)")

            logger.info(f"File size validated: {file_size} bytes")
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                raise ValueError(f"File not found in S3: {bucket_name}/{object_key}")
            raise

        logger.info(f"Downloading file from S3: {bucket_name}/{object_key}")

        # Create a temporary file and close it immediately
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        temp_file_path = temp_file.name
        temp_file.close()  # Close the file handle immediately

        # Download the file
        s3_client.download_file(bucket_name, object_key, temp_file_path)

        logger.info(f"File downloaded successfully to {temp_file_path}")
        return temp_file_path

    except Exception as e:
        logger.error(f"Error downloading file from S3: {str(e)}")
        raise


class S3Service:
    """Service for S3 operations"""
    
    def __init__(self):
        self.bucket_name = os.getenv("AWS_BUCKET_NAME") or os.getenv("S3_BUCKET_NAME", "narrative-modeling-dev")
        self.s3_client = boto3.client(
            "s3",
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name=os.getenv("AWS_REGION", "us-east-1"),
        )
    
    @with_circuit_breaker(
        "s3",
        max_attempts=3,
        failure_threshold=5,
        recovery_timeout=60.0,
        exceptions=(ClientError,)
    )
    async def download_file_bytes(self, file_key: str) -> bytes:
        """Download file from S3 and return as bytes"""
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=file_key)
            return response['Body'].read()
        except ClientError as e:
            logger.error(f"Error downloading file from S3: {str(e)}")
            raise
    
    def get_file_url(self, file_key: str) -> str:
        """Get S3 URL for a file"""
        return f"s3://{self.bucket_name}/{file_key}"
    
    @with_circuit_breaker(
        "s3",
        max_attempts=3,
        failure_threshold=5,
        recovery_timeout=60.0,
        exceptions=(ClientError,)
    )
    async def upload_file_obj(self, file_obj, file_key: str) -> str:
        """Upload a file-like object to S3"""
        try:
            self.s3_client.upload_fileobj(file_obj, self.bucket_name, file_key)
            logger.info(f"File uploaded successfully to {file_key}")
            return self.get_file_url(file_key)
        except ClientError as e:
            logger.error(f"Error uploading file to S3: {str(e)}")
            raise
    
    async def download_file_obj(self, file_key: str) -> bytes:
        """Download file from S3 and return as bytes"""
        return await self.download_file_bytes(file_key)
    
    @with_circuit_breaker(
        "s3",
        max_attempts=3,
        failure_threshold=5,
        recovery_timeout=60.0,
        exceptions=(ClientError,)
    )
    async def delete_file(self, file_key: str) -> bool:
        """Delete a file from S3"""
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=file_key)
            logger.info(f"File deleted successfully: {file_key}")
            return True
        except ClientError as e:
            logger.error(f"Error deleting file from S3: {str(e)}")
            raise


# Create singleton instance
s3_service = S3Service()


# Helper functions for backward compatibility
async def get_file_from_s3(file_key: str) -> bytes:
    """Get file data from S3"""
    return await s3_service.download_file_bytes(file_key)
