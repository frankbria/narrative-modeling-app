"""Bounded reads for file uploads (issue #270).

Every upload route used ``content = await file.read()``, pulling the entire
upload into memory with no cap — a large or crafted upload could exhaust RAM
before the downstream row/column checks ran. ``read_upload_capped`` reads the
same bytes but aborts with HTTP 413 the moment the cap is crossed.
"""

import os

from fastapi import HTTPException, UploadFile

# 100 MB default — matches nginx `client_max_body_size 100M` and
# MAX_EXPORT_SOURCE_BYTES (data_processing.py). Override with MAX_UPLOAD_BYTES.
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(100 * 1024 * 1024)))
_READ_CHUNK = 1024 * 1024  # 1 MB


def _too_large(max_bytes: int) -> HTTPException:
    return HTTPException(
        status_code=413,
        detail=f"File too large. Maximum upload size is {max_bytes // (1024 * 1024)} MB.",
    )


async def read_upload_capped(
    file: UploadFile, max_bytes: int | None = None
) -> bytes:
    """Read ``file`` fully, raising 413 once ``max_bytes`` is exceeded.

    First rejects on the parsed part size (cheap, Content-Length-derived), then
    streams in ``_READ_CHUNK`` blocks so memory stays bounded even when the size
    is unknown or under-reported. ``max_bytes`` defaults to ``MAX_UPLOAD_BYTES``,
    resolved at call time so it stays overridable in tests/config.
    """
    if max_bytes is None:
        max_bytes = MAX_UPLOAD_BYTES

    if file.size is not None and file.size > max_bytes:
        raise _too_large(max_bytes)

    buffer = bytearray()
    while chunk := await file.read(_READ_CHUNK):
        buffer.extend(chunk)
        if len(buffer) > max_bytes:
            raise _too_large(max_bytes)
    return bytes(buffer)
