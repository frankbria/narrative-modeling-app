"""#960: a chart requested after a transformation is a chart of the transformed data.

The chart caches were never cleared when a dataset moved to a new file, so the box plot,
histogram and correlation matrix kept answering with the data from before. The whole
flow runs here through the routes against real S3 (LocalStack). Skips locally when
LocalStack is down; ``CI_REQUIRE_SERVICES`` makes that a failure.
"""
import io
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

USER = "charts_960_user"
# Twenty distinct small rows, then one large row thirty times: removing duplicates takes
# the median of `spend` from 1000 to 10.
CSV = ("visits,spend\n" + "".join(f"{i},{i}\n" for i in range(20)) + "99,1000\n" * 30).encode()


@pytest.fixture
def real_s3_env(monkeypatch, test_s3_bucket, s3_client):
    """Point the app's S3 helpers AND the service singletons at LocalStack."""
    monkeypatch.setenv("AWS_ENDPOINT_URL", "http://localhost:4566")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    for name in ("AWS_BUCKET_NAME", "AWS_S3_BUCKET", "S3_BUCKET_NAME"):
        monkeypatch.setenv(name, test_s3_bucket)
    from app.services.s3_service import s3_service
    from app.services.versioning_service import versioning_service

    monkeypatch.setattr(versioning_service, "s3_client", s3_client)
    monkeypatch.setattr(s3_service, "s3_client", s3_client)
    monkeypatch.setattr(s3_service, "bucket_name", test_s3_bucket)
    monkeypatch.setattr(s3_service, "is_mock_mode", False)
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


async def _medians(client, dataset_id: str) -> tuple[float, float]:
    """The median the box plot reports, and the middle of the default histogram's range."""
    box = await client.get(f"/api/v1/visualizations/boxplot/{dataset_id}/spend")
    histogram = await client.get(f"/api/v1/visualizations/histogram/{dataset_id}/spend")
    assert (box.status_code, histogram.status_code) == (200, 200), (box.text, histogram.text)
    return box.json()["median"], max(histogram.json()["bin_edges"])


async def test_the_charts_after_a_transformation_are_of_the_new_data(client):
    upload = await client.post("/api/v1/upload/secure", files={"file": ("visits.csv", io.BytesIO(CSV), "text/csv")})
    dataset_id = upload.json()["file_id"]
    assert await _medians(client, dataset_id) == (1000.0, 1000.0)

    applied = await client.post(
        "/api/v1/transformations/apply",
        json={"dataset_id": dataset_id, "transformation_type": "remove_duplicates", "parameters": {}},
    )
    assert applied.json()["success"] is True, applied.text

    # 21 rows now: 0..19 and one 1000.
    assert await _medians(client, dataset_id) == (10.0, 1000.0)
    correlation = await client.get(f"/api/v1/visualizations/correlation/{dataset_id}")
    assert correlation.status_code == 200
