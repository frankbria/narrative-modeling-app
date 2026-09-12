import io
import logging
import os
import re
import uuid
from urllib.parse import unquote, urlparse

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, NoCredentialsError

from app.config import resolve_aws_region, resolve_s3_bucket

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
        "region_name": resolve_aws_region(),
    }
    endpoint_url = os.getenv("AWS_ENDPOINT_URL")
    if endpoint_url:
        client_kwargs["endpoint_url"] = endpoint_url
        # Pin path-style addressing for S3-compatible endpoints so bucket
        # names never become unresolvable host prefixes (e.g.
        # http://test-bucket.localhost:9000) regardless of boto3 version.
        # Real AWS keeps the default (virtual-hosted) addressing.
        client_kwargs["config"] = Config(s3={"addressing_style": "path"})
    return boto3.client("s3", **client_kwargs)


def parse_s3_url(s3_url: str) -> tuple[str | None, str]:
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
    bucket: str | None = None
    key = ""

    if s3_url.startswith("s3://"):
        bucket, _, key = s3_url[5:].partition("/")
    else:
        endpoint_url = (os.getenv("AWS_ENDPOINT_URL") or "").rstrip("/")
        parsed = urlparse(s3_url)
        endpoint = urlparse(endpoint_url) if endpoint_url else None
        # Exact scheme+host+port comparison — a plain prefix check would
        # also match lookalike hosts (http://localhost:9000.attacker.com).
        if endpoint and parsed.scheme == endpoint.scheme and parsed.netloc == endpoint.netloc:
            path = parsed.path.lstrip("/")
            bucket, _, key = path.partition("/")
        else:
            # Virtual-host, with or without a region label (bucket.s3.eu-west-1.amazonaws.com).
            match = re.match(r"https://([^.]+)\.s3(?:\.[a-z0-9-]+)?\.amazonaws\.com/([^?]+)", s3_url)
            if match:
                bucket, key = match.group(1), match.group(2)
            elif parsed.scheme in ("http", "https"):
                key = parsed.path.lstrip("/")

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

    # Credentials are required by name; the bucket is resolved through the one
    # canonical resolver (#257/#567) so a deployment that sets only AWS_S3_BUCKET or
    # S3_BUCKET_NAME is not refused here while every other reader accepts it.
    missing_vars = [v for v in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY") if not os.getenv(v)]
    if not resolve_s3_bucket():
        missing_vars.append("AWS_BUCKET_NAME (or any S3 bucket variable)")

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


def dataset_s3_key(user_id: str, original_filename: str, *, masked: bool = False) -> str:
    """The S3 key for a newly uploaded dataset object: ``datasets/{user_id}/[masked_]{uuid4}.{ext}``.

    The owner prefix is what the strict downloader, ``DatasetErasureService`` and
    any per-tenant lifecycle rule key on; an object written anywhere else is
    unreachable to the first, invisible to the second and untargetable by the third
    (#464, #581). Only the extension of the client filename survives — the name
    itself never reaches the key, so two tenants uploading ``data.csv`` cannot
    collide and a ``../`` in it cannot escape the prefix. Every route that writes a
    dataset object must build its key here; there is deliberately no helper that
    can express a key without the owner.
    """
    # ``user_id`` comes from the verified JWT / API key, never from the request
    # body. This is still the one place every tenant boundary in the bucket is
    # drawn, so refuse anything that could fold into another prefix rather than
    # trust every future caller.
    if not user_id or "/" in user_id or user_id in (".", ".."):
        raise ValueError(f"unsafe user_id for an S3 prefix: {user_id!r}")
    ext = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else ""
    ext = re.sub(r"[^a-z0-9]", "", ext)
    name = f"{'masked_' if masked else ''}{uuid.uuid4()}"
    return f"datasets/{user_id}/{name}.{ext}" if ext else f"datasets/{user_id}/{name}"


def upload_file_to_s3(
    file_content: bytes, s3_filename: str, content_type: str | None = None
) -> tuple[bool, str | None]:
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

    # The one canonical bucket resolver (#567 AC4).
    bucket_name = resolve_s3_bucket()
    if not bucket_name:
        logger.error("No S3 bucket configured (AWS_BUCKET_NAME or a sibling variable)")
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


#: Largest object any reader will download (1 GB). One cap, shared by the BytesIO
#: and temp-file readers, so an unbounded object cannot exhaust memory or /tmp.
MAX_DOWNLOAD_BYTES = 1024 * 1024 * 1024

#: The two app-internal namespaces every stored object lives in:
#: ``{datasets|transformed}/{user_id}/{filename}``, plus the versioning layout
#: ``datasets/{user_id}/{dataset_id}/versions/{version_id}/{filename}``. The
#: user_id and ids are bounded-charset; the *filename* may be anything without a
#: slash, because datasets.py stores the raw client filename (``my data.csv``,
#: ``data (1).csv``) and refusing those made the app's own objects unreadable
#: (#496). Traversal and absolute paths are refused before this is consulted, and
#: a slash-free final segment cannot leave the tenant prefix.
_NAMESPACED_KEY = re.compile(
    r"^(?:datasets|transformed)/[a-zA-Z0-9_-]+/"
    r"(?:[a-zA-Z0-9_-]+/versions/[a-zA-Z0-9_-]+/)?"
    r"[^/]+$"
)
#: The pre-#581 shape still sitting at the production bucket root until the
#: operator runs the reconciliation (#615): (masked_){uuid4}.{ext}, nothing else.
_LEGACY_ROOT_KEY = re.compile(
    r"^(?:masked_)?[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}(?:\.[a-z0-9]+)?$",
    re.IGNORECASE,
)


def allowed_bucket() -> str:
    """The single bucket this deployment may read from (#567).

    Fails closed: with no bucket configured there is nothing to compare a URL
    against, so reading is refused rather than allowed. Every reader resolves the
    bucket through this one function — the #567 failure was two allowlists that
    resolved it with different code and drifted.
    """
    bucket = _allowed_bucket()
    if not bucket:
        raise ValueError(
            "S3 bucket not configured: set AWS_S3_BUCKET (or AWS_BUCKET_NAME) — "
            "download allowlist has no allowed bucket"
        )
    return bucket


def validate_object_key(key: str, *, allow_legacy_root: bool = False) -> str:
    """URL-decode ``key`` and prove it names something this app is allowed to read.

    Refuses traversal (``..``), an absolute path, and any key outside the two
    app namespaces. ``allow_legacy_root`` additionally admits exactly the
    pre-#581 root-level ``(masked_){uuid}.{ext}`` shape that ``UserData.s3_url``
    still points at in production until #615 moves those objects; nothing else at
    the root is ever accepted. Returns the decoded key.
    """
    decoded = unquote(key or "")
    # Traversal is a *segment* that is "." or "..", or an absolute/empty segment
    # ("/etc/passwd", "a//b"). A ".." inside a filename ("experiment..csv") is a
    # legitimate name datasets.py will happily store, and cannot traverse
    # because the segment contains no slash.
    segments = decoded.split("/")
    if not decoded or decoded.startswith("/") or any(seg in ("", ".", "..") for seg in segments):
        logger.error("Path traversal or absolute path in S3 key: %r", key)
        raise ValueError("Invalid S3 path: path traversal detected")
    if _NAMESPACED_KEY.match(decoded):
        return decoded
    if allow_legacy_root and _LEGACY_ROOT_KEY.match(decoded):
        return decoded
    logger.error("Invalid S3 path structure: %r", decoded)
    raise ValueError(
        "Invalid S3 path structure: must match "
        "'{datasets|transformed}/{user_id}/{filename}'"
    )


def resolve_validated_object(s3_url: str, *, allow_legacy_root: bool = False) -> tuple[str, str]:
    """Turn a stored URL into ``(bucket, key)`` that may be downloaded (#531, #567).

    The one place every reader goes through: parse (all persisted shapes), refuse
    a URL the parser cannot attribute to a bucket, refuse a bucket other than
    this deployment's, then validate the key. Raises ``ValueError`` on every
    refusal — deterministic, so callers' retry/breaker logic must not count it.
    """
    bucket, key = parse_s3_url(s3_url)
    if bucket is None:
        raise ValueError(f"Invalid S3 URL format: {s3_url}")
    require_allowed_bucket(bucket)
    return bucket, validate_object_key(key, allow_legacy_root=allow_legacy_root)


def check_object_size(client, bucket: str, key: str) -> int:
    """HEAD the object and refuse anything over ``MAX_DOWNLOAD_BYTES`` before a byte is read."""
    try:
        size = int(client.head_object(Bucket=bucket, Key=key)["ContentLength"])
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "404":
            raise ValueError(f"File not found in S3: {bucket}/{key}") from e
        raise
    if size > MAX_DOWNLOAD_BYTES:
        logger.error("File too large: %d bytes (max %d)", size, MAX_DOWNLOAD_BYTES)
        raise ValueError(
            f"File too large: {size} bytes exceeds maximum {MAX_DOWNLOAD_BYTES} bytes (1 GB)"
        )
    return size


def _allowed_bucket() -> str | None:
    """The single bucket this deployment may read from, or None if unconfigured.

    Deliberately the same expression as
    `app/services/s3_service.py::download_file_from_s3`, which has enforced its
    own allowlist since #257. Two allowlists that resolve their allowed bucket
    differently is how this class of bug quietly reopens — an earlier version of
    this function accepted *any* of the four historical env names, which was the
    more permissive of the two. Consolidating them into one helper is a
    follow-up; agreeing on the answer comes first.

    Resolved at call time rather than import time so tests and deployments that
    set the environment after import are honoured.
    """
    return os.getenv("AWS_S3_BUCKET") or resolve_s3_bucket()


def require_allowed_bucket(bucket_name: str) -> None:
    """Refuse to read from a bucket this deployment does not own (issue #451).

    Defense in depth behind the schema fix: `s3_url` is no longer settable from
    a request, but a stored URL is only as trustworthy as whatever wrote it.
    Call this at every site that turns a stored URL into a download, not just
    `get_file_from_s3` — `column_stats` parses and fetches on its own. If no bucket is configured the
    check cannot be evaluated, so it fails closed rather than allowing anything.

    The key is validated separately by `validate_object_key`, which admits the
    legacy root shape only where a reader explicitly asks for it (#581/#615).
    """
    allowed = allowed_bucket()  # raises the one "not configured" error when unset
    if bucket_name != allowed:
        logger.error(
            "Refusing to download from unexpected bucket %r (allowed: %r)",
            bucket_name, allowed,
        )
        raise ValueError(
            f"Access denied: S3 bucket '{bucket_name}' not allowed (not permitted for this deployment)"
        )


def get_file_from_s3(s3_url: str) -> io.BytesIO:
    """Download a stored object into memory — the one BytesIO reader (#531).

    Same validated core as ``s3_service.download_file_from_s3`` (bucket allowlist,
    traversal and namespace checks, size cap); differs only in where the bytes
    land. This reader serves preview/viz/column-stats, which read
    ``UserData.s3_url`` — and production still has pre-#581 objects at the bucket
    root — so it alone admits the legacy root shape, until #615 retires it.
    """
    client = get_s3_client()
    if client is None:
        raise Exception("Failed to initialize S3 client")

    try:
        bucket_name, key = resolve_validated_object(s3_url, allow_legacy_root=True)
        check_object_size(client, bucket_name, key)

        file_obj = io.BytesIO()
        client.download_fileobj(bucket_name, key, file_obj)
        file_obj.seek(0)

        logger.info(f"File downloaded successfully from {s3_url}")
        return file_obj
    except Exception as e:
        logger.error(f"Error downloading file from S3: {e}")
        raise

