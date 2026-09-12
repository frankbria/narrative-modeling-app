"""#581 AC5: erasure must find the object a ``/upload/secure`` upload wrote.

Before #581 that route keyed objects as a bare ``{uuid}.csv``; erasure derives keys
from the stored URL and could delete them, but nothing proved the two agreed once
the key convention changed. This runs the *real* route against a *real* S3
(LocalStack), then the real cascade, and asserts the object is gone. Skips locally
when LocalStack is down; ``CI_REQUIRE_SERVICES`` turns that into a failure in CI.
"""

import io
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

USER = "erasure_secure_user"
CSV = b"id,score\n1,10\n2,20\n"


@pytest.fixture
def real_s3_env(monkeypatch, test_s3_bucket):
    """Point the app's S3 helpers AND S3Service at LocalStack.

    S3Service treats credentials that start with ``test-`` as mock mode; the
    LocalStack placeholders are ``test``/``test`` (no dash), so it goes live.
    """
    monkeypatch.setenv("AWS_ENDPOINT_URL", "http://localhost:4566")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("AWS_BUCKET_NAME", test_s3_bucket)
    monkeypatch.setenv("AWS_S3_BUCKET", test_s3_bucket)
    monkeypatch.setenv("S3_BUCKET_NAME", test_s3_bucket)
    return test_s3_bucket


@pytest_asyncio.fixture
async def client(setup_database, real_s3_env, monkeypatch) -> AsyncGenerator:
    from asgi_lifespan import LifespanManager
    from httpx import ASGITransport, AsyncClient

    from app.api.routes import secure_upload as secure_upload_module
    from app.auth.nextauth_auth import get_current_user_id
    from app.main import app
    from tests.conftest import _point_app_at_test_database

    async def noop(*args, **kwargs):
        return None

    # Both background summary entry points: /secure schedules
    # generate_dataset_summary (imported inside the handler, so patch the source
    # module), /confirm and chunked schedule generate_ai_summary_safe.
    import app.utils.ai_summary as ai_summary

    monkeypatch.setattr(ai_summary, "generate_dataset_summary", noop)
    monkeypatch.setattr(secure_upload_module, "generate_ai_summary_safe", noop)

    async def override() -> str:
        return USER

    app.dependency_overrides.clear()
    app.dependency_overrides[get_current_user_id] = override
    _point_app_at_test_database()
    async with LifespanManager(app, startup_timeout=30, shutdown_timeout=30):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            yield c
    app.dependency_overrides.clear()


def _keys(s3_client, bucket) -> set[str]:
    return {
        o["Key"] for o in s3_client.list_objects_v2(Bucket=bucket).get("Contents", [])
    }


async def test_erasing_a_secure_upload_removes_its_object(client, s3_client, real_s3_env):
    from app.models.user_data import UserData
    from app.services.erasure_service import DatasetErasureService

    bucket = real_s3_env
    response = await client.post(
        "/api/v1/upload/secure", files={"file": ("d.csv", io.BytesIO(CSV), "text/csv")}
    )
    assert response.status_code == 200, response.text
    file_id = response.json()["file_id"]

    stored = await UserData.get(file_id)
    keys_after_upload = _keys(s3_client, bucket)
    assert len(keys_after_upload) == 1
    (key,) = keys_after_upload
    assert key.startswith(f"datasets/{USER}/"), key
    assert stored.s3_url.endswith(key)

    # A fresh service instance picks up the LocalStack environment set above.
    service = DatasetErasureService()
    assert not service.s3_service.is_mock_mode
    # The "s3" circuit breaker is a process-wide singleton. Earlier integration
    # tests in the same run can trip it (failed S3 calls elsewhere), and erasure
    # then swallows the open-breaker error into the manifest as a delete failure —
    # which is what a first CI run of this test reported. Start it closed.
    from app.utils.circuit_breaker import get_circuit_breaker

    get_circuit_breaker("s3").reset()
    manifest = await service.erase_dataset(file_id, USER)

    assert await UserData.get(file_id) is None
    assert _keys(s3_client, bucket) == set(), (
        "the /secure object survived erasure: "
        f"s3_objects_deleted={manifest.s3_objects_deleted} failures={manifest.failures} "
        f"notes={manifest.notes} stored_url={stored.s3_url!r} "
        f"service_bucket={service.s3_service.bucket_name!r} "
        f"endpoint={service.s3_service.s3_client.meta.endpoint_url!r}"
    )
