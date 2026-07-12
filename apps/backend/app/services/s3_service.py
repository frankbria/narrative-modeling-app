import asyncio
import logging
import os
import re
import tempfile
from urllib.parse import unquote

from botocore.exceptions import ClientError

from app.config import resolve_s3_bucket
from app.utils.circuit_breaker import with_circuit_breaker, with_sync_circuit_breaker
from app.utils.s3 import create_s3_client, parse_s3_url

logger = logging.getLogger(__name__)


@with_sync_circuit_breaker(
    "s3",
    max_attempts=3,
    failure_threshold=5,
    recovery_timeout=60.0,
    # Only retry/count transient S3 errors. ValueError means a deterministic
    # validation failure (bad URL, wrong bucket, path traversal): retrying it
    # is pointless, and counting it toward the breaker would let malicious
    # input open the circuit and block legitimate downloads.
    exceptions=(ClientError,)
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
        # SECURITY: Get allowed bucket from environment. Prefer the explicit
        # AWS_S3_BUCKET allowlist var, but fall back to the app's canonical bucket
        # (any historical name) so a deploy that sets only AWS_BUCKET_NAME still
        # works (#257). Fail closed (raise) when no bucket is configured at all.
        ALLOWED_BUCKET = os.getenv("AWS_S3_BUCKET") or resolve_s3_bucket()
        if not ALLOWED_BUCKET:
            raise ValueError(
                "S3 bucket not configured: set AWS_S3_BUCKET (or AWS_BUCKET_NAME) — "
                "download allowlist has no allowed bucket"
            )

        # SECURITY: Validate S3 URL format and bucket whitelist.
        # parse_s3_url handles amazonaws and endpoint-style (MinIO/LocalStack)
        # URLs with exact-origin endpoint matching; URLs it cannot attribute
        # to a bucket are rejected here.
        try:
            bucket_name, object_key = parse_s3_url(s3_url)
        except ValueError:
            raise ValueError(f"Invalid S3 URL format: {s3_url}")
        if bucket_name is None:
            raise ValueError(f"Invalid S3 URL format: {s3_url}")

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

        # SECURITY: Validate path structure. Two app-internal namespaces are
        # trusted, each exactly {prefix}/{user_id}/{filename} (two segments, bounded
        # charset, no traversal): 'datasets/' (uploads) and 'transformed/' (transform
        # outputs, written by transformation/bulk/data-issue flows). Transformed
        # artifacts must be downloadable too — after issue #276 the dataset's s3_url
        # points at them, so preview/viz/chained-transform read this namespace.
        path_pattern = r'^(?:datasets|transformed)/[a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+$'
        if not re.match(path_pattern, object_key):
            logger.error(f"Invalid S3 path structure: {object_key}")
            raise ValueError(
                "Invalid S3 path structure: must match "
                "'{datasets|transformed}/{user_id}/{filename}'"
            )

        # Initialize S3 client
        s3_client = create_s3_client()

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

        # Check if we're using test/mock credentials
        aws_access_key = os.getenv("AWS_ACCESS_KEY_ID", "")
        aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY", "")
        self.is_mock_mode = (
            aws_access_key.startswith("test-") or
            aws_secret_key.startswith("test-") or
            not aws_access_key or
            not aws_secret_key
        )

        if self.is_mock_mode:
            logger.warning("S3Service initialized in mock mode (test credentials or missing credentials)")
            # Create a dummy client that won't be used
            self.s3_client = None
        else:
            try:
                self.s3_client = create_s3_client()
            except Exception as e:
                logger.exception("Failed to initialize S3 client: %s", e)
                self.is_mock_mode = True
                self.s3_client = None
    
    @with_circuit_breaker(
        "s3",
        max_attempts=3,
        failure_threshold=5,
        recovery_timeout=60.0,
        exceptions=(ClientError,)
    )
    async def download_file_bytes(self, file_key: str) -> bytes:
        """Download file from S3 and return as bytes"""
        if self.is_mock_mode or self.s3_client is None:
            raise RuntimeError("S3Service is in mock mode - cannot download files")

        def _download() -> bytes:
            # boto3 is blocking; run the request + body read off the event loop.
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=file_key)
            return response['Body'].read()

        try:
            return await asyncio.to_thread(_download)
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
        exceptions=(ClientError,),
    )
    async def get_file_size(self, file_key: str) -> int:
        """Return an object's size in bytes via head_object (no download)."""
        if self.is_mock_mode or self.s3_client is None:
            raise RuntimeError("S3Service is in mock mode - cannot stat files")
        response = await asyncio.to_thread(
            self.s3_client.head_object, Bucket=self.bucket_name, Key=file_key
        )
        return response["ContentLength"]

    def generate_presigned_url(
        self, file_key: str, expires_in: int = 3600, filename: str | None = None
    ) -> str:
        """Presigned GET URL for temporary browser-downloadable access.

        Synchronous by design: boto3's ``generate_presigned_url`` is a local HMAC
        signing operation with no network I/O, so it is safe to call from an async
        route without blocking the event loop (hence no circuit breaker either).
        Pass ``filename`` to force a clean download name via Content-Disposition.
        """
        if self.is_mock_mode or self.s3_client is None:
            raise RuntimeError("S3Service is in mock mode - cannot presign URLs")
        params: dict[str, str] = {"Bucket": self.bucket_name, "Key": file_key}
        if filename:
            # Escape internally too so this reusable primitive is safe regardless
            # of the caller: a raw quote/semicolon can't malform the header.
            safe = re.sub(r"[^A-Za-z0-9._-]", "_", filename) or "download"
            params["ResponseContentDisposition"] = f'attachment; filename="{safe}"'
        return self.s3_client.generate_presigned_url(
            "get_object", Params=params, ExpiresIn=expires_in
        )
    
    @with_circuit_breaker(
        "s3",
        max_attempts=3,
        failure_threshold=5,
        recovery_timeout=60.0,
        exceptions=(ClientError,)
    )
    async def upload_file_obj(self, file_obj, file_key: str) -> str:
        """Upload a file-like object to S3"""
        if self.is_mock_mode or self.s3_client is None:
            raise RuntimeError("S3Service is in mock mode - cannot upload files")

        # Rewind before every (re)attempt: this method's body re-runs on each
        # circuit-breaker retry, and boto3's upload_fileobj consumes the stream —
        # without a seek, a retry would resume from EOF and upload a truncated
        # object while the caller thinks it succeeded (issue #278 review).
        if hasattr(file_obj, "seek"):
            try:
                file_obj.seek(0)
            except (OSError, ValueError):
                pass  # non-seekable stream — nothing we can do, let boto3 try

        try:
            await asyncio.to_thread(
                self.s3_client.upload_fileobj, file_obj, self.bucket_name, file_key
            )
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
        if self.is_mock_mode or self.s3_client is None:
            raise RuntimeError("S3Service is in mock mode - cannot delete files")

        try:
            await asyncio.to_thread(
                self.s3_client.delete_object, Bucket=self.bucket_name, Key=file_key
            )
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
