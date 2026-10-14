"""#889: column statistics describe the file the dataset is on, through a transformation.

The cached rows are keyed by the dataset, not by its file. `record_new_file` deletes them
whenever the dataset moves (#960); this reads them before and after a real
transformation, through the routes, against real S3 (LocalStack). Skips locally when
LocalStack is down; ``CI_REQUIRE_SERVICES`` makes that a failure.
"""
import io

import pytest

from tests.test_integration.test_charts_follow_a_transformation_localstack import (  # noqa: F401
    client,
    real_s3_env,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

CSV = b"visits,spend\n1,10\n2,\n3,30\n4,40\n"


async def _missing_spend(client, dataset_id: str) -> int:  # noqa: F811
    stats = await client.get(f"/api/v1/column_stats/dataset/{dataset_id}")
    assert stats.status_code == 200, stats.text
    return next(c["missing"] for c in stats.json() if c["column_name"] == "spend")


async def test_after_filling_the_blank_the_stats_count_no_missing_value(client):  # noqa: F811
    upload = await client.post("/api/v1/upload/secure", files={"file": ("visits.csv", io.BytesIO(CSV), "text/csv")})
    dataset_id = upload.json()["file_id"]
    assert await _missing_spend(client, dataset_id) == 1, "computed and cached from the upload"

    applied = await client.post(
        "/api/v1/transformations/apply",
        json={"dataset_id": dataset_id, "transformation_type": "fill_missing", "parameters": {"method": "mean"}},
    )
    assert applied.json()["success"] is True, applied.text

    assert await _missing_spend(client, dataset_id) == 0, "read from the file the dataset is on now"
