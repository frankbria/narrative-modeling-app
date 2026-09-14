"""#541 AC3/AC5: a loaded sample dataset is a REAL S3 object that downstream code can
read — proving it is usable end-to-end (preview/transform/train all download it the same
way). Before #541 the loader stored a fabricated URL for an object it never uploaded, so
every later read 404'd.

Runs the real loader against real S3 (LocalStack) and reads the stored URL back through
the platform's validated downloader. Skips when LocalStack is down.
"""

import os

import pytest
import pytest_asyncio

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

USER = "onboarding_localstack_user"
DATASET_ID = "customer_churn"


@pytest_asyncio.fixture
async def real_s3_env(monkeypatch, test_s3_bucket, s3_client):
    if s3_client is None or test_s3_bucket is None:
        from tests.conftest import require_service
        require_service("LocalStack S3 not available")
    monkeypatch.setenv("AWS_ENDPOINT_URL", os.getenv("S3_ENDPOINT_URL", "http://localhost:4566"))
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("AWS_BUCKET_NAME", test_s3_bucket)
    monkeypatch.setenv("AWS_S3_BUCKET", test_s3_bucket)
    monkeypatch.setenv("S3_BUCKET_NAME", test_s3_bucket)
    return test_s3_bucket


async def test_loaded_sample_is_a_real_downloadable_object(setup_database, real_s3_env, s3_client):
    from app.services.onboarding_service import OnboardingService
    from app.utils.s3 import get_file_from_s3

    result = await OnboardingService().load_sample_dataset(USER, DATASET_ID)
    s3_url = result["s3_url"]

    # The object really exists in the bucket (not a fabricated URL).
    keys = {o["Key"] for o in s3_client.list_objects_v2(Bucket=real_s3_env).get("Contents", [])}
    assert any(k.startswith(f"datasets/{USER}/") and k.endswith(".csv") for k in keys), keys

    # And downstream code can read it through the validated downloader (usable, #541 AC3).
    content = get_file_from_s3(s3_url)
    data = content.read() if hasattr(content, "read") else content
    assert data and (b"," in data if isinstance(data, bytes) else "," in data)
