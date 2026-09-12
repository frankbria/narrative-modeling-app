"""#466 AC3: the first transformation on a freshly uploaded dataset must succeed.

``DatasetMetadata.file_path`` is a raw key right after ``/datasets/upload`` and every
``file_path or s3_url`` site fed it to the URL-only downloader, so the *first* apply on
any dataset failed and every later one (once ``file_path`` held a URL) worked. A mocked
downloader cannot see this — the whole flow runs here against real S3 (LocalStack).
Skips locally when LocalStack is down; ``CI_REQUIRE_SERVICES`` makes that a failure.
"""
import io
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

USER = "first_apply_user"
CSV = b"id,name,score\n1, alice ,10\n2,bob,\n3,carol,30\n"


@pytest.fixture
def real_s3_env(monkeypatch, test_s3_bucket):
    """Point the app's S3 helpers AND S3Service at LocalStack (creds `test`, not `test-`)."""
    monkeypatch.setenv("AWS_ENDPOINT_URL", "http://localhost:4566")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("AWS_BUCKET_NAME", test_s3_bucket)
    monkeypatch.setenv("AWS_S3_BUCKET", test_s3_bucket)
    monkeypatch.setenv("S3_BUCKET_NAME", test_s3_bucket)
    return test_s3_bucket


@pytest_asyncio.fixture
async def client(setup_database, real_s3_env) -> AsyncGenerator:
    from asgi_lifespan import LifespanManager
    from httpx import ASGITransport, AsyncClient

    from app.auth.nextauth_auth import get_current_user_id
    from app.main import app
    from tests.conftest import _point_app_at_test_database

    async def override() -> str:
        return USER

    app.dependency_overrides.clear()
    app.dependency_overrides[get_current_user_id] = override
    _point_app_at_test_database()
    async with LifespanManager(app, startup_timeout=30, shutdown_timeout=30):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c
    app.dependency_overrides.clear()


def _keys(s3_client, bucket) -> set[str]:
    return {o["Key"] for o in s3_client.list_objects_v2(Bucket=bucket).get("Contents", [])}


async def test_first_transformation_on_a_fresh_upload_succeeds(client, s3_client, real_s3_env):
    from app.models.dataset import DatasetMetadata

    upload = await client.post(
        "/api/v1/datasets/upload", files={"file": ("d.csv", io.BytesIO(CSV), "text/csv")}
    )
    assert upload.status_code in (200, 201), upload.text
    dataset_id = upload.json()["dataset_id"]
    stored = await DatasetMetadata.find_one(DatasetMetadata.dataset_id == dataset_id)
    assert stored is not None
    assert not stored.file_path.startswith(("s3://", "http")), (
        "precondition: a fresh upload stores a raw key in file_path — that is the input "
        f"the downloader used to reject (got {stored.file_path!r})"
    )
    keys_before = _keys(s3_client, real_s3_env)

    apply = await client.post("/api/v1/transformations/apply", json={
        "dataset_id": dataset_id, "transformation_type": "trim_whitespace",
        "parameters": {"columns": ["name"]},
    })
    assert apply.status_code == 200, apply.text
    body = apply.json()
    assert body["success"] is True, body  # was: "Invalid S3 URL format: datasets/..."

    new_keys = _keys(s3_client, real_s3_env) - keys_before
    assert len(new_keys) == 1 and next(iter(new_keys)).startswith(f"transformed/{USER}/"), new_keys

    # and the SECOND transformation — the one that always worked — still does
    again = await client.post("/api/v1/transformations/apply", json={
        "dataset_id": dataset_id, "transformation_type": "trim_whitespace",
        "parameters": {"columns": ["name"]},
    })
    assert again.status_code == 200 and again.json()["success"] is True, again.text
