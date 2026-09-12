"""Every route that writes a dataset object keys it under its owner (#581).

#464 fixed the chunked path; the three non-chunked writers kept calling a helper
that returned a bare ``{uuid}.{ext}``. Those objects are unreachable through the
strict downloader, invisible to erasure, and untargetable by any per-tenant
lifecycle rule — 155 of them sat in the production bucket when this was filed.

Same shape as ``test_chunked_upload_flow.py``: the real handler runs against the
real test database; only the S3 write is substituted, recording the key it was
handed so the invariant is asserted on the *key*, not on a mocked return value.
"""

import io
import re
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio

from app.api.routes import secure_upload as secure_upload_module
from app.api.routes import upload as upload_module

pytestmark = pytest.mark.asyncio

TENANT = "tenant_prefix_user"
CLEAN_CSV = b"id,score\n1,10\n2,20\n"
PII_CSV = b"id,email\n1,alice@example.com\n2,bob@example.com\n"
KEY_RE = re.compile(
    r"^datasets/" + re.escape(TENANT) + r"/(masked_)?"
    r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\.csv$"
)


@pytest.fixture
def s3_keys(monkeypatch):
    """Substitute the S3 write in BOTH route modules, recording every key."""
    keys: list[str] = []

    def fake_upload(content: bytes, s3_filename: str, content_type: str | None = None):
        keys.append(s3_filename)
        return True, f"s3://test-bucket/{s3_filename}"

    monkeypatch.setattr(secure_upload_module, "upload_file_to_s3", fake_upload)
    monkeypatch.setattr(upload_module, "upload_file_to_s3", fake_upload)
    # /upload/ refuses to run without these names set; the values are never used
    # because the S3 call above is substituted.
    for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_BUCKET_NAME"):
        monkeypatch.setenv(name, "test-placeholder")
    return keys


@pytest.fixture
def no_ai_summary(monkeypatch):
    """The routes schedule an OpenAI summary in the background; keep it out."""

    async def noop(*args, **kwargs):
        return None

    monkeypatch.setattr(secure_upload_module, "generate_ai_summary_safe", noop)
    monkeypatch.setattr(upload_module, "generate_ai_summary_safe", noop, raising=False)


@pytest_asyncio.fixture
async def client(setup_database, s3_keys, no_ai_summary) -> AsyncGenerator:
    from asgi_lifespan import LifespanManager
    from httpx import ASGITransport, AsyncClient

    from app.auth.nextauth_auth import get_current_user_id
    from app.main import app
    from tests.conftest import _point_app_at_test_database

    async def override() -> str:
        return TENANT

    app.dependency_overrides.clear()
    app.dependency_overrides[get_current_user_id] = override
    _point_app_at_test_database()
    async with LifespanManager(app, startup_timeout=30, shutdown_timeout=30):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            yield c
    app.dependency_overrides.clear()


def _file(content: bytes, name: str = "data.csv"):
    return {"file": (name, io.BytesIO(content), "text/csv")}


class TestEveryDatasetWriterUsesTheOwnerPrefix:
    async def test_secure_upload(self, client, s3_keys):
        response = await client.post("/api/v1/upload/secure", files=_file(CLEAN_CSV))
        assert response.status_code == 200, response.text
        assert len(s3_keys) == 1 and KEY_RE.match(s3_keys[0]), s3_keys

    async def test_confirm_pii_upload_unmasked(self, client, s3_keys):
        response = await client.post(
            "/api/v1/upload/confirm-pii-upload",
            files=_file(PII_CSV),
            params={"mask_pii": "false"},  # a query parameter on this route
        )
        assert response.status_code == 200, response.text
        assert len(s3_keys) == 1 and KEY_RE.match(s3_keys[0]), s3_keys
        assert "masked_" not in s3_keys[0]

    async def test_confirm_pii_upload_masked_keeps_the_prefix(self, client, s3_keys):
        # Before #581 the masked variant was ``masked_{uuid}.csv`` — a *second*
        # bare shape at the bucket root.
        response = await client.post(
            "/api/v1/upload/confirm-pii-upload",
            files=_file(PII_CSV),
            params={"mask_pii": "true"},
        )
        assert response.status_code == 200, response.text
        assert len(s3_keys) == 1 and KEY_RE.match(s3_keys[0]), s3_keys
        assert s3_keys[0].rsplit("/", 1)[1].startswith("masked_")

    async def test_plain_upload_route(self, client, s3_keys):
        response = await client.post("/api/v1/upload/", files=_file(CLEAN_CSV))
        assert response.status_code == 200, response.text
        assert len(s3_keys) == 1 and KEY_RE.match(s3_keys[0]), s3_keys

    async def test_client_filename_never_reaches_the_key(self, client, s3_keys):
        response = await client.post(
            "/api/v1/upload/secure", files=_file(CLEAN_CSV, name="../../etc/passwd.csv")
        )
        assert response.status_code == 200, response.text
        assert KEY_RE.match(s3_keys[0]) and "passwd" not in s3_keys[0]

    async def test_the_bare_key_helper_is_gone(self):
        # AC2: a helper that cannot express the owner must not exist for the next
        # route to reach for.
        import app.utils.schema_inference as schema_inference

        assert not hasattr(schema_inference, "generate_s3_filename")
