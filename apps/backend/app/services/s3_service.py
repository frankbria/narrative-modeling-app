import asyncio
import logging
import os
import tempfile
import uuid
from collections.abc import Collection
from typing import Any

from botocore.exceptions import ClientError

from app.config import development_uses_a_real_bucket
from app.utils.circuit_breaker import with_circuit_breaker, with_sync_circuit_breaker
from app.utils.filenames import attachment_disposition
from app.utils.s3 import (
    allowed_bucket,
    check_object_size,
    configured_bucket,
    create_s3_client,
    get_s3_client,
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
        # allowlist, traversal + namespace checks.
        bucket_name, object_key = resolve_validated_object(s3_url)

        # The shared, bounded client (#519/#722), not one built per call. It is
        # unavailable only when the credentials are missing from the environment;
        # then build one as before, and boto3 reports what is missing on the request.
        s3_client = get_s3_client() or create_s3_client()

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


class FormatMismatchError(ValueError):
    """The object's bytes don't match its declared file_type (#524).

    A transformation once rewrote s3_url to a .parquet object while file_type
    stayed 'csv', so every reader parsed parquet bytes as CSV and failed with an
    opaque pandas error. Raising this instead names the real problem — the stored
    file_type and the object disagree — so the failure is diagnosable, not a
    mystery parse exception.
    """


def _looks_like_parquet(local_path: str) -> bool:
    """A Parquet file begins AND ends with the 4-byte magic ``PAR1``. Requiring
    BOTH avoids a false positive on a non-Parquet file that merely starts with
    those bytes (e.g. a CSV whose first column is named ``PAR1...``) — a valid CSV
    would be wrongly rejected on the header alone (#524, codex)."""
    try:
        with open(local_path, "rb") as fh:
            if fh.read(4) != b"PAR1":
                return False
            fh.seek(0, os.SEEK_END)
            if fh.tell() < 8:  # too small to hold both the header and footer magic
                return False
            fh.seek(-4, os.SEEK_END)
            return fh.read(4) == b"PAR1"
    except OSError:
        return False


def _kind_of(local_path: str) -> str:
    """What the file's own bytes say it is: parquet, xlsx, xls, json or csv (#858)."""
    if _looks_like_parquet(local_path):
        return "parquet"
    with open(local_path, "rb") as fh:
        head = fh.read(512)
    if head.startswith(b"PK\x03\x04"):  # a zip container, which is what .xlsx is
        return "xlsx"
    if head.startswith(b"\xd0\xcf\x11\xe0"):  # the OLE container of the old binary .xls
        return "xls"
    # JSON opens with a bracket or a brace, after an optional UTF-8 BOM and whitespace.
    if head.lstrip(b"\xef\xbb\xbf \t\r\n")[:1] in (b"[", b"{"):
        return "json"
    return "csv"


def _read_csv(local_path: str, nrows: int | None, usecols: Any = None):
    import pandas as pd

    return pd.read_csv(local_path, nrows=nrows, usecols=usecols)


def _read_excel(local_path: str, nrows: int | None):
    import pandas as pd

    return pd.read_excel(local_path, nrows=nrows)


def _read_json(local_path: str, nrows: int | None):
    import pandas as pd

    try:
        df = pd.read_json(local_path, encoding="utf-8-sig")  # -sig: a leading BOM is not data
    except ValueError:
        # One object per line (JSON Lines) is not one document, and must not fall
        # through to the CSV reader, which would return it as junk columns.
        df = pd.read_json(local_path, encoding="utf-8-sig", lines=True)
    return df.head(nrows) if nrows else df


def _read_parquet(local_path: str, nrows: int | None):
    import pandas as pd

    df = pd.read_parquet(local_path)
    return df.head(nrows) if nrows else df


# "excel" is what the secure upload routes stored before #902.
_READERS = {
    "csv": _read_csv,
    "xlsx": _read_excel,
    "xls": _read_excel,
    "excel": _read_excel,
    "json": _read_json,
    "parquet": _read_parquet,
}


def _require_matching_bytes(local_path: str, file_type: str, ft: str) -> None:
    """A declared type must agree with the object's magic bytes (#524): a Parquet object
    declared as csv/excel/json (or the reverse) fails with a clear FormatMismatchError
    rather than an opaque parse error."""
    if ft not in _READERS:
        return  # an unknown type is refused by the caller, whatever the bytes are
    is_parquet = _looks_like_parquet(local_path)
    if is_parquet == (ft == "parquet"):
        return
    found = "Parquet" if is_parquet else "not Parquet"
    raise FormatMismatchError(
        f"declared file_type '{file_type}' but the object is {found} — the "
        "stored file_type and s3_url disagree (#524); recheck the dataset record"
    )


def _read_by_content(local_path: str, nrows: int | None):
    """Read a file nobody declared a type for, by what its bytes are (#858).

    This path used to try CSV, then Parquet. `read_csv` does not fail on JSON: it
    returns junk columns, and a transformation then wrote that junk back over the
    dataset on both twins. An Excel workbook was not readable at all.
    """
    kind = _kind_of(local_path)
    if kind == "json":
        try:
            return _read_json(local_path, nrows)
        except ValueError:
            kind = "csv"  # a CSV whose first header merely opens with a bracket
    return _READERS[kind](local_path, nrows)


def _read_dataframe(local_path: str, file_type: str | None, nrows: int | None):
    """Parse a local file into a DataFrame by file_type, or by its bytes when None.

    download_file_from_s3 temp files have no suffix, so extension sniffing is
    useless: callers pass the dataset's file_type, and the transformation readers,
    which pass None, are dispatched on the file's content (`_read_by_content`).
    """
    ft = (file_type or "").lower()
    if not file_type:
        return _read_by_content(local_path, nrows)
    _require_matching_bytes(local_path, file_type, ft)
    reader = _READERS.get(ft)
    if reader is None:
        raise ValueError(f"Unsupported file type: {file_type}")
    return reader(local_path, nrows)


def read_dataframe_from_bytes(content: bytes, file_type: str | None = None, nrows: int | None = None):
    """`_read_dataframe` for an object already in memory: by its declared `file_type`,
    or by what its bytes are when there is none (#733).

    The readers take a path, so the bytes go through a temp file. Blocking: call it off
    the event loop.
    """
    with tempfile.NamedTemporaryFile() as held:
        held.write(content)
        held.flush()
        return _read_dataframe(held.name, file_type, nrows)


def _parquet_columns(local_path: str, wanted: set[str]):
    """Those columns of a Parquet file, in file order. The format is stored column by
    column, so the others are never decoded."""
    import pandas as pd
    import pyarrow.parquet as pq

    present = [name for name in pq.read_schema(local_path).names if name in wanted]
    return pd.read_parquet(local_path, columns=present)


def read_columns_from_bytes(content: bytes, columns: Collection[str]):
    """The named columns of an object already in memory, read by what its bytes are.

    For the readers that use a column or two of a dataset (#712): a Parquet file,
    which is what a dataset is once transformed, gives up only those columns, and a
    CSV is parsed with the others skipped. A workbook or JSON is read whole and
    narrowed. A name the file does not have is left out, never an error: the caller
    finds out when it uses the column, as it did before. Blocking: call it off the
    event loop.
    """
    wanted = set(columns)
    with tempfile.NamedTemporaryFile() as held:
        held.write(content)
        held.flush()
        kind = _kind_of(held.name)
        if kind == "parquet":
            return _parquet_columns(held.name, wanted)
        if kind == "csv":
            return _read_csv(held.name, None, usecols=wanted.__contains__)
        frame = _read_by_content(held.name, None)
        return frame.loc[:, [name for name in frame.columns if name in wanted]]


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


# Logged once per process (#878): the service is built at import and again by several
# services per request, so the first one to find the misconfiguration says it and the
# rest stay quiet. The bucket's name stays out of the line: the repository is public and
# logs get pasted into issues.
_warned_of_a_real_bucket = False
_REAL_BUCKET_IN_DEVELOPMENT = (
    "ENVIRONMENT is development and AWS_ENDPOINT_URL is not set: uploads and model "
    "artifacts are written to a real S3 bucket, beside any other environment that uses "
    "it. Set AWS_ENDPOINT_URL=http://localhost:4566 to use LocalStack "
    "(docker compose -f docker-compose.test.yml up -d localstack)."
)


def _warn_once_of_a_real_bucket_in_development() -> None:
    global _warned_of_a_real_bucket
    if _warned_of_a_real_bucket or not development_uses_a_real_bucket():
        return
    _warned_of_a_real_bucket = True
    logger.warning(_REAL_BUCKET_IN_DEVELOPMENT)


def _lacks_real_credentials() -> bool:
    """Test credentials (a ``test-`` prefix) or none: the service runs in mock mode."""
    aws_access_key = os.getenv("AWS_ACCESS_KEY_ID", "")
    aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    return (
        aws_access_key.startswith("test-")
        or aws_secret_key.startswith("test-")
        or not aws_access_key
        or not aws_secret_key
    )


class S3Service:
    """Service for S3 operations"""

    def __init__(self):
        # bucket_name is a live property (#622); an explicit assignment pins this
        # instance (tests do that), production never assigns and follows the env.
        self._bucket_override: str | None = None
        self.is_mock_mode = _lacks_real_credentials()
        self.s3_client = None
        if self.is_mock_mode:
            logger.warning("S3Service initialized in mock mode (test credentials or missing credentials)")
            return
        _warn_once_of_a_real_bucket_in_development()
        try:
            self.s3_client = create_s3_client()
        except Exception as e:
            logger.exception("Failed to initialize S3 client: %s", e)
            self.is_mock_mode = True

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
        # same rules, and the size cap applies.
        bucket = self._live_bucket()  # same pin-or-live answer as the writers (#622)
        file_key = validate_object_key(file_key)

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

    def verify_bucket_writable(self) -> None:
        """Fail fast if the configured S3 bucket is missing or not writable (#495).

        Called from the app lifespan **only in a production-like environment**
        (see main.py): a refused boot is far better than a running deployment that
        writes to a guessed or wrong bucket (the #495 data-integrity risk), and it
        catches a credential rotation that silently broke S3 access (P1.33). In
        dev/test this never runs, so mock-mode and no-bucket stay fine there.

        A missing bucket, mock-mode credentials in production, or a failed
        put/delete probe each raise ``RuntimeError``. The probe writes and removes
        one tiny object so "writable" is actually verified, not assumed.
        """
        bucket = configured_bucket()
        if not bucket:
            raise RuntimeError(
                "No S3 bucket is configured (set AWS_S3_BUCKET); refusing to "
                "start rather than write to a guessed bucket (#495)."
            )
        if self.is_mock_mode or self.s3_client is None:
            raise RuntimeError(
                "S3 is in mock mode (test or missing AWS credentials) in a "
                "production-like environment; refusing to start (#495)."
            )
        probe_key = f"_startup/write-probe-{uuid.uuid4().hex}"
        try:
            written = self.s3_client.put_object(Bucket=bucket, Key=probe_key, Body=b"ok")
            self._remove_probe(bucket, probe_key, written.get("VersionId"))
        except Exception as exc:  # noqa: BLE001 - any failure means "not writable"
            raise RuntimeError(
                f"Configured S3 bucket {bucket!r} is not writable "
                f"({type(exc).__name__}); refusing to start (#495)."
            ) from exc

    def _remove_probe(self, bucket: str, key: str, version_id: str | None) -> None:
        """Delete the probe, and on a versioned bucket the version it wrote (#529).

        A plain delete there keeps the bytes as a noncurrent version and adds a delete
        marker, one of each per boot of each worker. Deleting a version needs
        ``s3:DeleteObjectVersion``; a policy without it gets the plain delete, never a
        refused boot, and the bucket's lifecycle rule expires what is left.
        """
        if version_id:
            try:
                self.s3_client.delete_object(Bucket=bucket, Key=key, VersionId=version_id)
                return
            except ClientError as exc:
                logger.warning(
                    "The startup probe could not delete the object version it wrote (%s): "
                    "a noncurrent version and a delete marker stay in the bucket until its "
                    "lifecycle rule expires them. Grant s3:DeleteObjectVersion to stop that.",
                    exc.response.get("Error", {}).get("Code", "unknown"),
                )
        self.s3_client.delete_object(Bucket=bucket, Key=key)

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
        file_key = validate_object_key(file_key)
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
        # New writes are namespaced.
        file_key = validate_object_key(file_key)
        if self.is_mock_mode or self.s3_client is None:
            raise RuntimeError("S3Service is in mock mode - cannot presign URLs")
        params: dict[str, str] = {"Bucket": self._live_bucket(), "Key": file_key}
        if filename:
            # S3 sends this back as the download's header, so it is built like every
            # other one: safe whatever the caller passes (#648).
            params["ResponseContentDisposition"] = attachment_disposition(filename)
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
        # New writes are namespaced.
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
        file_key = validate_object_key(file_key)
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

