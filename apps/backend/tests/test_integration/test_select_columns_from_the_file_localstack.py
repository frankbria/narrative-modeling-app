"""#924: selecting columns by pattern reads the schema of the dataset's current file.

It iterated `DatasetMetadata.data_schema`, which no upload path fills, so every pattern
matched nothing. Through the route, for a dataset uploaded by each path, against real
S3 (LocalStack). Skips locally when LocalStack is down; ``CI_REQUIRE_SERVICES`` makes
that a failure.
"""
import io

import pytest

from tests.test_integration.test_charts_follow_a_transformation_localstack import (  # noqa: F401
    client,
    real_s3_env,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

CSV = b"score,city,spend\n1,paris,10\n2,oslo,\n3,rome,30\n4,oslo,\n"


async def _secure(client) -> str:  # noqa: F811
    upload = await client.post("/api/v1/upload/secure", files={"file": ("visits.csv", io.BytesIO(CSV), "text/csv")})
    assert upload.status_code == 200, upload.text
    return upload.json()["file_id"]


async def _datasets(client) -> str:  # noqa: F811
    upload = await client.post("/api/v1/datasets/upload", files={"file": ("visits.csv", io.BytesIO(CSV), "text/csv")})
    assert upload.status_code == 200, upload.text
    return upload.json()["dataset_id"]


async def _matched(client, dataset_id: str, pattern_type: str, criteria: dict) -> list[str]:  # noqa: F811
    response = await client.post(
        f"/api/v1/transformations/datasets/{dataset_id}/columns/select-pattern",
        json={"pattern_type": pattern_type, "criteria": criteria},
    )
    assert response.status_code == 200, response.text
    return sorted(c["column_name"] for c in response.json()["columns"])


@pytest.mark.parametrize("upload", [_secure, _datasets], ids=["/upload/secure", "/datasets/upload"])
async def test_a_pattern_matches_the_columns_of_the_file(client, upload):  # noqa: F811
    dataset_id = await upload(client)

    assert await _matched(client, dataset_id, "name_pattern", {"pattern": "^sc"}) == ["score"]
    assert await _matched(client, dataset_id, "data_type", {"types": ["numeric"]}) == ["score", "spend"]
    assert await _matched(
        client, dataset_id, "quality_metric", {"metric": "missing_values", "operator": "gt", "threshold": 0}
    ) == ["spend"]


async def test_after_a_transformation_the_selection_follows_the_new_file(client):  # noqa: F811
    dataset_id = await _secure(client)
    gaps = {"metric": "missing_values", "operator": "gt", "threshold": 0}
    assert await _matched(client, dataset_id, "quality_metric", gaps) == ["spend"]

    applied = await client.post(
        "/api/v1/transformations/apply",
        json={"dataset_id": dataset_id, "transformation_type": "fill_missing", "parameters": {"method": "mean"}},
    )
    assert applied.json()["success"] is True, applied.text

    assert await _matched(client, dataset_id, "quality_metric", gaps) == [], "the blanks were filled"
