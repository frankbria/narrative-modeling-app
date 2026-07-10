"""Tests for the capped upload reader (issue #270).

The reader must abort with HTTP 413 once an upload exceeds the byte cap, so a
large/crafted upload can't exhaust memory before downstream row/column checks.
"""

import io

import pytest
from fastapi import HTTPException
from starlette.datastructures import UploadFile

from app.utils.upload_limits import MAX_UPLOAD_BYTES, read_upload_capped


def _upload(data: bytes, *, declared_size: int | None = None) -> UploadFile:
    """Build an UploadFile; declared_size mimics the multipart Content-Length."""
    return UploadFile(
        filename="data.csv",
        file=io.BytesIO(data),
        size=declared_size if declared_size is not None else len(data),
    )


@pytest.mark.asyncio
async def test_reads_small_upload_in_full():
    payload = b"col_a,col_b\n1,2\n3,4\n"
    result = await read_upload_capped(_upload(payload), max_bytes=1024)
    assert result == payload


@pytest.mark.asyncio
async def test_rejects_when_declared_size_exceeds_cap():
    # Oversized per the declared size — must 413 without reading the body.
    up = _upload(b"x" * 50, declared_size=10_000)
    with pytest.raises(HTTPException) as exc:
        await read_upload_capped(up, max_bytes=100)
    assert exc.value.status_code == 413


@pytest.mark.asyncio
async def test_rejects_when_streamed_bytes_exceed_cap_even_if_size_unknown():
    # size=None (client omitted Content-Length) — the streamed cap must catch it.
    big = b"y" * 5000
    up = UploadFile(filename="data.csv", file=io.BytesIO(big), size=None)
    with pytest.raises(HTTPException) as exc:
        await read_upload_capped(up, max_bytes=1000)
    assert exc.value.status_code == 413


@pytest.mark.asyncio
async def test_boundary_exactly_at_cap_is_allowed():
    payload = b"z" * 100
    result = await read_upload_capped(_upload(payload), max_bytes=100)
    assert result == payload


@pytest.mark.asyncio
async def test_default_cap_is_100_mb():
    assert MAX_UPLOAD_BYTES == 100 * 1024 * 1024
