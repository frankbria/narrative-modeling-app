"""Server-side S3 access for MCP tools.

Callers never supply a raw bucket/key. The dataset's S3 location comes from the
trusted `user_data` record, is parsed here, and is *pinned to the app bucket* via
an allowlist so a poisoned URL can't reach another bucket. Errors are generic so
we never leak AccessDenied-vs-NotFound to a caller.
"""

import logging
import os
import re
import tempfile
from urllib.parse import unquote, urlparse

import boto3

logger = logging.getLogger(__name__)

# https://bucket.s3.amazonaws.com/key or https://bucket.s3.<region>.amazonaws.com/key
_HTTPS_S3_RE = re.compile(r"^https://([^.]+)\.s3(?:[.-][^.]+)?\.amazonaws\.com/(.+)$")


def _app_bucket() -> str | None:
    """The single S3 bucket MCP tools are allowed to read from."""
    return os.getenv("AWS_S3_BUCKET") or os.getenv("AWS_BUCKET_NAME")


def parse_and_validate_s3_url(s3_url: str, allowed_bucket: str | None) -> tuple[str, str]:
    """Parse `s3://b/k` or `https://b.s3[.region].amazonaws.com/k` into (bucket, key).

    Raises ValueError if the format is unrecognized or the bucket is not the
    configured app bucket. Pure/sync — no network, no credentials.
    """
    if not allowed_bucket:
        raise ValueError("app S3 bucket is not configured")

    bucket: str | None = None
    key: str | None = None

    if s3_url.startswith("s3://"):
        parsed = urlparse(s3_url)
        bucket = parsed.netloc
        key = parsed.path.lstrip("/")
    else:
        match = _HTTPS_S3_RE.match(s3_url.split("?", 1)[0])
        if match:
            bucket, key = match.group(1), match.group(2)

    if not bucket or not key:
        raise ValueError("unrecognized S3 URL")

    key = unquote(key)
    if bucket != allowed_bucket:
        raise ValueError("S3 URL outside the allowed bucket")

    return bucket, key


def download_dataset_file(s3_url: str) -> str:
    """Download a dataset file to a temp path from a trusted, DB-sourced S3 URL.

    The bucket is pinned to the app bucket; on any failure a generic RuntimeError
    is raised (the real S3 error is logged, never returned to the caller).
    """
    bucket, key = parse_and_validate_s3_url(s3_url, _app_bucket())

    try:
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name=os.getenv("AWS_REGION", "us-east-1"),
        )
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        temp_file_path = temp_file.name
        temp_file.close()
        s3_client.download_file(bucket, key, temp_file_path)
        return temp_file_path
    except Exception:
        logger.error("S3 download failed for key in app bucket", exc_info=True)
        raise RuntimeError("failed to load dataset file") from None
