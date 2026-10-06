"""The frontend's `/user_data/{id}` fixture is a real response, not a guess (#808).

The explore page read `dataset.schema?.row_count` for its Rows card. No writer
sets `schema` before processing, so every fresh dataset said "Rows N/A", and the
page's test stayed green because its fixture was hand-written with a `schema`
the API never sends. The page test now renders this fixture, and this test keeps
the fixture's shape equal to what the route actually returns.

Regenerate after a deliberate response change:
    UPDATE_FIXTURES=1 PYTHONPATH=. uv run pytest tests/test_api/test_user_data_response_fixture.py
"""

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.models.user_data import UserData

FIXTURES = Path(__file__).resolve().parents[4] / "apps/frontend/__tests__/fixtures"
USER_DATA = FIXTURES / "userDataResponse.unprocessed.json"
PROCESS = FIXTURES / "dataProcessResponse.json"
CSV = b"tenure,plan,churn\n1,basic,1\n24,pro,0\n36,pro,0\n5,basic,1\n60,premium,0\n"


def _check(path: Path, body: dict) -> None:
    if os.getenv("UPDATE_FIXTURES"):
        path.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n")
    fixture = json.loads(path.read_text())
    assert set(fixture) == set(body), f"regenerate {path.name}: the response shape changed"


@pytest.mark.asyncio
async def test_the_frontend_fixture_has_the_real_response_shape(
    async_authorized_client, setup_database
):
    # A fresh upload as `/upload/` and `/upload/secure` store it: counts set,
    # nothing processed yet.
    doc = UserData(
        user_id="test_user_123",
        filename="churn.csv",
        original_filename="churn.csv",
        s3_url="https://bucket.s3.amazonaws.com/datasets/test_user_123/a.csv",
        num_rows=5,
        num_columns=3,
        data_schema=[],
        file_type="csv",
        file_size=len(CSV),
        created_at=datetime(2026, 10, 1, tzinfo=UTC),
        updated_at=datetime(2026, 10, 1, tzinfo=UTC),
    )
    await doc.insert()

    response = await async_authorized_client.get(f"/api/v1/user_data/{doc.id}")
    assert response.status_code == 200
    body = response.json()

    _check(USER_DATA, body)
    assert body["schema"] is None  # what the explore page sees before processing

    # What the page merges in after it asks for processing. Only the S3 read is
    # stubbed; the processing pipeline and the route's serialisation are real.
    with patch(
        "app.services.s3_service.s3_service.download_file_bytes",
        new_callable=AsyncMock,
        return_value=CSV,
    ):
        processed = await async_authorized_client.post(
            "/api/v1/data/process", json={"file_id": str(doc.id)}
        )
    assert processed.status_code == 200
    _check(PROCESS, processed.json())
    assert "is_processed" not in processed.json()  # the page must set it itself
    # The nested values the page reads, which a top-level key check cannot see.
    fixture = json.loads(PROCESS.read_text())
    for body in (processed.json(), fixture):
        assert {"row_count", "column_count", "columns"} <= set(body["schema"])
        assert "overall_quality_score" in body["quality_report"]
