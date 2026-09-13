"""#486: an oversized CSV field must fail billing CLOSED, not reserve 0."""

import io

import pytest

from app.api.routes.batch_prediction import (
    MAX_CSV_FIELD_BYTES,
    CsvCountError,
    _count_csv_rows,
)
from app.billing import metering

pytestmark = pytest.mark.asyncio

TEST_USER = "test_user_123"


def test_count_csv_rows_counts_a_normal_file():
    content = b"a,b\n1,2\n3,4\n5,6\n"
    assert _count_csv_rows(content) == 3


def test_count_csv_rows_raises_on_an_oversized_field():
    big = b"x" * (MAX_CSV_FIELD_BYTES + 1)
    content = b"col\n" + big + b"\n"
    with pytest.raises(CsvCountError):
        _count_csv_rows(content)


def test_count_csv_rows_restores_the_global_field_limit():
    import csv as _csv

    before = _csv.field_size_limit()
    with pytest.raises(CsvCountError):
        _count_csv_rows(b"c\n" + b"y" * (MAX_CSV_FIELD_BYTES + 1) + b"\n")
    assert _csv.field_size_limit() == before


def _oversized_csv() -> dict:
    body = b"feature\n" + b"z" * (MAX_CSV_FIELD_BYTES + 10) + b"\n"
    return {"file": ("big.csv", io.BytesIO(body), "text/csv")}


async def test_oversized_field_upload_is_rejected_and_refunds(
    async_authorized_client, setup_database
):
    before = await metering.usage_for(TEST_USER, "predictions")
    resp = await async_authorized_client.post(
        "/api/v1/batch/jobs", files=_oversized_csv(), data={"model_id": "model_123"}
    )
    assert resp.status_code == 400, resp.text
    assert "field" in resp.json()["detail"].lower()
    # The admission dependency's reserved unit is refunded on the 4xx.
    assert await metering.usage_for(TEST_USER, "predictions") == before
