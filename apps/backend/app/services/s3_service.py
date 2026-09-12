import asyncio
import logging
import os
import re
import tempfile

from botocore.exceptions import ClientError

from app.utils.circuit_breaker import with_circuit_breaker, with_sync_circuit_breaker
from app.utils.s3 import (
    allowed_bucket,
    check_object_size,
    configured_bucket,
    create_s3_client,
    resolve_validated_object,
    validate_object_key,
)

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
        # One validated core for every reader (#531/#567): parse, bucket
        # allowlist, traversal + namespace checks. Strict here — this path serves
        # transformations and data processing, which only ever read the two app
        # namespaces; the legacy root allowance belongs to the BytesIO reader.
        bucket_name, object_key = resolve_validated_object(s3_url)

        # Initialize S3 client
        s3_client = create_s3_client()

        # SECURITY: Check file size before downloading to prevent DoS
        file_size = check_object_size(s3_client, bucket_name, object_key)
        logger.info(f"File size validated: {file_size} bytes")

        logger.info(f"Downloading file from S3: {bucket_name}/{object_key}")

        # Create a temporary file and close it immediately
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        temp_file_path = temp_file.name
        temp_file.close()  # Close the file handle immediately

        # Download the file. On failure, remove the temp file we just created so a
        # failed download (or a circuit-breaker retry, which re-runs this whole
        # body) doesn't leak a partial copy in /tmp (#280).
        try:
            s3_client.download_file(bucket_name, object_key, temp_file_path)
        except Exception:
            try:
                os.unlink(temp_file_path)
            except OSError:
                pass
            raise

        logger.info(f"File downloaded successfully to {temp_file_path}")
        return temp_file_path

    except Exception as e:
        logger.error(f"Error downloading file from S3: {str(e)}")
        raise


def _read_dataframe(local_path: str, file_type: str | None, nrows: int | None):
    """Parse a local file into a DataFrame by file_type, inferring when None.

    download_file_from_s3 temp files have no suffix, so extension sniffing is
    useless — callers pass the dataset's file_type; None falls back to csv-then-
    parquet inference (the historical get_dataframe_from_s3 behavior).
    """
    import pandas as pd

    ft = (file_type or "").lower()
    if ft == "csv":
        return pd.read_csv(local_path, nrows=nrows)
    if ft in ("xlsx", "xls"):
        return pd.read_excel(local_path, nrows=nrows)
    if ft == "json":
        return pd.read_json(local_path)
    if ft == "parquet":
        df = pd.read_parquet(local_path)
        return df.head(nrows) if nrows else df
    if ft:
        raise ValueError(f"Unsupported file type: {file_type}")
    # Infer: csv first, then parquet.
    try:
        return pd.read_csv(local_path, nrows=nrows)
    except (pd.errors.ParserError, pd.errors.EmptyDataError, ValueError, UnicodeDecodeError):
        df = pd.read_parquet(local_path)
        return df.head(nrows) if nrows else df


def load_dataframe_from_s3(
    s3_url: str, file_type: str | None = None, nrows: int | None = None
):
    """Download an S3 object, parse it into a DataFrame, and ALWAYS remove the
    temp file (try/finally). Centralizes the download+parse+cleanup that every
    caller previously duplicated — and most leaked (issue #280).

    Blocking (boto3 + pandas); call sites keep wrapping it in asyncio.to_thread.
    Reuses download_file_from_s3, so all its security validation still applies.
    """
    local_path = download_file_from_s3(s3_url)
    try:
        return _read_dataframe(local_path, file_type, nrows)
    finally:
        try:
            os.unlink(local_path)
        except OSError:
            pass


class S3Service:
    """Service for S3 operations"""

    def __init__(self):
        # bucket_name is a live property (#622); an explicit assignment pins this
        # instance (tests do that), production never assigns and follows the env.
        self._bucket_override: str | None = None

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

        # The same core as the URL readers (#531/#567): the bucket is the one
        # allowlisted bucket (fail closed when unconfigured), the key follows the
        # same rules (legacy root allowed until #615), and the size cap applies.
        bucket = self._live_bucket()  # same pin-or-live answer as the writers (#622)
        file_key = validate_object_key(file_key, allow_legacy_root=True)

        def _download() -> bytes:
            # boto3 is blocking; run the request + body read off the event loop.
            check_object_size(self.s3_client, bucket, file_key)
            response = self.s3_client.get_object(Bucket=bucket, Key=file_key)
            return response['Body'].read()

        try:
            return await asyncio.to_thread(_download)
        except ClientError as e:
            logger.error(f"Error downloading file from S3: {str(e)}")
            raise
    
    @property
    def bucket_name(self) -> str:
        """The one configured bucket, resolved per call like every reader (#567,
        #622) — never a value frozen at construction, so URL building, erasure's
        bucket comparison and the boto3 calls below can never disagree. An
        explicit assignment pins this instance instead (tests pin a fixture
        bucket); production code never assigns. The literal is only for
        mock-mode runs with nothing configured, where nothing is read or written."""
        # The two services keep their historical unconfigured defaults ("…-dev"
        # here, "…-uploads" in versioning): mock-mode only, nothing is written.
        return self._pin() or configured_bucket() or "narrative-modeling-dev"

    @bucket_name.setter
    def bucket_name(self, value: str) -> None:
        self._bucket_override = value

    @bucket_name.deleter
    def bucket_name(self) -> None:
        # unittest.mock.patch(obj, "bucket_name", ...) restores by deleting the
        # instance attribute it set; clearing the pin is what "delete" means here.
        self._bucket_override = None

    def get_file_url(self, file_key: str) -> str:
        """Get S3 URL for a file"""
        return f"s3://{self.bucket_name}/{file_key}"

    def _pin(self) -> str | None:
        # getattr: tests build instances with __new__ and never run __init__.
        return getattr(self, "_bucket_override", None)

    def _live_bucket(self) -> str:
        """The bucket for THIS call (#622): the instance's explicit pin if one was
        assigned, else resolved like the readers — never a value captured at
        construction, so a process whose environment changed cannot download
        from one bucket and write to another."""
        return self._pin() or allowed_bucket()

    @with_circuit_breaker(
        "s3",
        max_attempts=3,
        failure_threshold=5,
        recovery_timeout=60.0,
        exceptions=(ClientError,),
    )
    async def get_file_size(self, file_key: str) -> int:
        """Return an object's size in bytes via head_object (no download)."""
        # Hygiene, not authorization (#622): the caller has already checked ownership.
        file_key = validate_object_key(file_key, allow_legacy_root=True)
        if self.is_mock_mode or self.s3_client is None:
            raise RuntimeError("S3Service is in mock mode - cannot stat files")
        response = await asyncio.to_thread(
            self.s3_client.head_object, Bucket=self._live_bucket(), Key=file_key
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
        # Hygiene, not authorization (#622): the caller has already checked ownership.
        # New writes are namespaced; only delete/head need the pre-#581 root shape.
        file_key = validate_object_key(file_key)
        if self.is_mock_mode or self.s3_client is None:
            raise RuntimeError("S3Service is in mock mode - cannot presign URLs")
        params: dict[str, str] = {"Bucket": self._live_bucket(), "Key": file_key}
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
        # Hygiene, not authorization (#622): the caller has already checked ownership.
        # New writes are namespaced; only delete/head need the pre-#581 root shape.
        file_key = validate_object_key(file_key)
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
                self.s3_client.upload_fileobj, file_obj, self._live_bucket(), file_key
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
        # Hygiene, not authorization (#622): the caller has already checked ownership.
        file_key = validate_object_key(file_key, allow_legacy_root=True)
        if self.is_mock_mode or self.s3_client is None:
            raise RuntimeError("S3Service is in mock mode - cannot delete files")

        try:
            await asyncio.to_thread(
                self.s3_client.delete_object, Bucket=self._live_bucket(), Key=file_key
            )
            logger.info(f"File deleted successfully: {file_key}")
            return True
        except ClientError as e:
            logger.error(f"Error deleting file from S3: {str(e)}")
            raise


# Create singleton instance
s3_service = S3Service()

