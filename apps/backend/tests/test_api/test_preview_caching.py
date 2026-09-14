"""#517: GET /api/v1/data/{file_id}/preview must not re-download and re-parse the
whole S3 object on every page.

Before #517 each page request downloaded the entire object and parsed it in full,
so paging through a preview re-read the whole file each time. The fix caches the
parsed frame per (user, dataset) with a bounded TTL, ranges-reads a file too large
to cache, and does the parse off the event loop.
"""

from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest

from app.models.user_data import UserData

TEST_USER = "test_user_123"  # the identity async_authorized_client authenticates as


def _csv_bytes(n: int = 10) -> bytes:
    df = pd.DataFrame({"id": range(n), "label": [f"row{i}" for i in range(n)]})
    return df.to_csv(index=False).encode()


async def _seed_processed_csv(user_id: str = TEST_USER, rows: int = 10) -> UserData:
    doc = UserData(
        user_id=user_id,
        filename="t.csv",
        original_filename="t.csv",
        s3_url="https://test-bucket.s3.amazonaws.com/datasets/u/t.csv",
        file_path="datasets/u/t.csv",
        num_rows=rows,
        num_columns=2,
        data_schema=[],
        file_type="csv",
        is_processed=True,
        columns=["id", "label"],
        row_count=rows,
    )
    await doc.insert()
    return doc


def test_cache_is_keyed_by_user_and_file():
    """Unit: the cache key includes user_id, so one tenant's cached frame can
    never be reached with another tenant's key even for the same s3_url."""
    from app.api.routes.data_processing import _preview_cache

    _preview_cache.clear()
    frame = object()  # sentinel; get/put don't inspect the value
    _preview_cache.put(("user_a", "s3://b/shared.csv"), frame)
    assert _preview_cache.get(("user_a", "s3://b/shared.csv")) is frame
    assert _preview_cache.get(("user_b", "s3://b/shared.csv")) is None
    _preview_cache.clear()


@pytest.fixture(autouse=True)
def _clear_preview_cache():
    """The parsed-frame cache is process-global; clear it around each test."""
    from app.api.routes.data_processing import _preview_cache

    _preview_cache.clear()
    yield
    _preview_cache.clear()


@pytest.mark.asyncio
async def test_second_page_does_not_redownload(setup_database, async_authorized_client):
    """AC4: a second page request for the same dataset serves from the cache —
    the S3 object is downloaded exactly once."""
    doc = await _seed_processed_csv(rows=10)
    spy = AsyncMock(return_value=_csv_bytes(10))
    with patch("app.services.s3_service.s3_service.download_file_bytes", spy):
        r1 = await async_authorized_client.get(
            f"/api/v1/data/{doc.id}/preview?rows=3&offset=0"
        )
        r2 = await async_authorized_client.get(
            f"/api/v1/data/{doc.id}/preview?rows=3&offset=3"
        )

    assert r1.status_code == 200, r1.text
    assert r2.status_code == 200, r2.text
    assert spy.call_count == 1  # cache hit on the second page — no re-download
    # And the pages are the correct, disjoint slices.
    assert [row["id"] for row in r1.json()["data"]] == [0, 1, 2]
    assert [row["id"] for row in r2.json()["data"]] == [3, 4, 5]
    assert r1.json()["total_rows"] == 10


@pytest.mark.asyncio
async def test_large_file_is_range_read_not_cached(
    setup_database, async_authorized_client, monkeypatch
):
    """AC2: a file too large to cache is range-read (only the requested rows are
    parsed) and is not held in the cache — so it does re-download, but never
    parses the whole file."""
    import app.api.routes.data_processing as dp

    monkeypatch.setattr(dp, "_PREVIEW_CACHE_MAX_BYTES", 1)  # force the range-read path
    doc = await _seed_processed_csv(rows=20)
    spy = AsyncMock(return_value=_csv_bytes(20))
    with patch("app.services.s3_service.s3_service.download_file_bytes", spy):
        r1 = await async_authorized_client.get(
            f"/api/v1/data/{doc.id}/preview?rows=4&offset=8"
        )
        r2 = await async_authorized_client.get(
            f"/api/v1/data/{doc.id}/preview?rows=4&offset=8"
        )

    assert r1.status_code == 200, r1.text
    assert r2.status_code == 200, r2.text
    # Correct slice even though only the range was parsed.
    assert [row["id"] for row in r1.json()["data"]] == [8, 9, 10, 11]
    assert r1.json()["total_rows"] == 20
    assert r1.json()["approximate_total_rows"] is True
    # Not cached, so the second identical request re-downloads.
    assert spy.call_count == 2


@pytest.mark.asyncio
async def test_foreign_dataset_404s_before_the_cache_is_touched(
    setup_database, async_authorized_client
):
    """The ownership `find_one` runs before the cache read, so a dataset owned by
    another tenant answers 404 and its S3 object is never downloaded — the cache
    can't become a cross-tenant read path."""
    other = await _seed_processed_csv(user_id="someone_else_517")
    spy = AsyncMock(return_value=_csv_bytes(10))
    with patch("app.services.s3_service.s3_service.download_file_bytes", spy):
        r = await async_authorized_client.get(
            f"/api/v1/data/{other.id}/preview?rows=3&offset=0"
        )
    assert r.status_code == 404, r.text
    assert spy.call_count == 0  # never reached the download/cache path


@pytest.mark.asyncio
async def test_frame_larger_than_memory_budget_is_not_cached(
    setup_database, async_authorized_client, monkeypatch
):
    """A file small enough to parse whole but whose PARSED frame exceeds the memory
    budget is served but not retained — bounding resident memory on the shared VPS
    (internal review #517). It re-downloads on the next page rather than holding a
    multi-x-source-size frame for the TTL."""
    import app.api.routes.data_processing as dp

    monkeypatch.setattr(dp, "_PREVIEW_CACHE_MAX_FRAME_BYTES", 1)  # nothing fits
    doc = await _seed_processed_csv(rows=10)
    spy = AsyncMock(return_value=_csv_bytes(10))
    with patch("app.services.s3_service.s3_service.download_file_bytes", spy):
        r1 = await async_authorized_client.get(
            f"/api/v1/data/{doc.id}/preview?rows=3&offset=0"
        )
        r2 = await async_authorized_client.get(
            f"/api/v1/data/{doc.id}/preview?rows=3&offset=3"
        )

    assert r1.status_code == 200, r1.text
    assert r2.status_code == 200, r2.text
    # Correct data still returned (parsed whole, just not cached).
    assert [row["id"] for row in r1.json()["data"]] == [0, 1, 2]
    assert [row["id"] for row in r2.json()["data"]] == [3, 4, 5]
    assert r1.json()["total_rows"] == 10
    # Over the frame budget -> not cached -> second page re-downloads.
    assert spy.call_count == 2


@pytest.mark.asyncio
async def test_range_read_total_rows_counts_a_missing_trailing_newline(
    setup_database, async_authorized_client, monkeypatch
):
    """The over-cap range-read reports total_rows from a line count; a CSV whose
    last row has no trailing newline (many writers omit it) must still count that
    row, not drop it (codex #517)."""
    import app.api.routes.data_processing as dp

    monkeypatch.setattr(dp, "_PREVIEW_CACHE_MAX_BYTES", 1)  # force the range-read path
    doc = await _seed_processed_csv(rows=3)
    no_trailing_nl = b"id,label\n0,a\n1,b\n2,c"  # 3 data rows, no final newline
    with patch(
        "app.services.s3_service.s3_service.download_file_bytes",
        AsyncMock(return_value=no_trailing_nl),
    ):
        r = await async_authorized_client.get(
            f"/api/v1/data/{doc.id}/preview?rows=10&offset=0"
        )

    assert r.status_code == 200, r.text
    assert r.json()["total_rows"] == 3  # not 2
