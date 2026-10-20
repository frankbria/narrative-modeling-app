"""`POST /api/v1/upload/` ran no PII scan but answered `pii_report.has_pii: false` (#1121).

Nothing called it (the Upload page uses `/upload/secure`, `/confirm-pii-upload` and the
chunked routes), and a dataset stored that way reached `/ai/summarize` unscanned. The route
is removed; this pins that a CSV with an email column cannot be stored through it.
"""

import io

import pytest

from app.models.user_data import UserData

pytestmark = pytest.mark.asyncio

PII_CSV = b"id,email\n1,alice@example.com\n2,bob@example.com\n"


async def test_a_csv_with_an_email_column_is_not_stored_through_the_legacy_route(
    async_authorized_client, setup_database, monkeypatch
):
    # S3 is configured and the put succeeds, so only the route's existence decides the answer.
    for var in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_BUCKET_NAME"):
        monkeypatch.setenv(var, "present-for-this-test")
    monkeypatch.setattr("app.utils.s3._put_object", lambda *a, **k: None)

    response = await async_authorized_client.post(
        "/api/v1/upload/", files={"file": ("people.csv", io.BytesIO(PII_CSV), "text/csv")}
    )

    assert response.status_code == 404, response.text
    assert "pii_report" not in response.text
    assert await UserData.find().count() == 0
