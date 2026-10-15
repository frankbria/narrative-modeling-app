"""The upload page's high-risk PII fixture is a real `/upload/secure` answer (#1054).

The page rendered the warning from `total_detections` and `affected_columns`, which
the backend never sends, so every high-risk upload crashed the page while its test,
built on a hand-written report, stayed green. The page test now renders this fixture.

Regenerate after a deliberate response change:
    UPDATE_FIXTURES=1 PYTHONPATH=. uv run pytest tests/test_api/test_secure_upload_pii_fixture.py
"""

import io
import json
import os
from pathlib import Path

import pytest

FIXTURE = Path(__file__).resolve().parents[4] / "apps/frontend/__tests__/fixtures/secureUploadHighRiskPii.json"
CSV = b"name,email,phone\nJohn Doe,john@example.com,555-1234\nAda King,ada@example.com,555-9876\n"


@pytest.mark.asyncio
async def test_the_frontend_fixture_is_the_real_high_risk_answer(async_authorized_client, setup_database):
    response = await async_authorized_client.post(
        "/api/v1/upload/secure", files={"file": ("staff.csv", io.BytesIO(CSV), "text/csv")}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "pii_detected"

    if os.getenv("UPDATE_FIXTURES"):
        FIXTURE.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n")
    assert json.loads(FIXTURE.read_text()) == body, f"regenerate {FIXTURE.name}: the answer changed"
