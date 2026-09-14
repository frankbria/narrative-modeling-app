"""#541: the onboarding sample-dataset loader must upload a real S3 object (not a
fabricated URL) and persist progress on a dedicated document (not an arbitrary/invalid
UserData).

Real Mongo (setup_database); the S3 write is substituted so the assertion is on the KEY
and the stored URL, not on a live bucket — the same shape as the upload-key contract tests.
"""

import pytest

from app.models.onboarding import OnboardingProgress
from app.models.user_data import UserData
from app.services.onboarding_service import OnboardingService

pytestmark = pytest.mark.asyncio

USER = "onboarding_sample_user"
DATASET_ID = "customer_churn"  # a real file under apps/backend/sample_datasets/


async def test_load_sample_uploads_a_real_object_not_a_fabricated_url(setup_database, monkeypatch):
    captured = {}

    def fake_upload(content, s3_filename, content_type=None):
        captured["key"] = s3_filename
        captured["bytes"] = content
        captured["content_type"] = content_type
        return True, f"s3://test-bucket/{s3_filename}"

    monkeypatch.setattr("app.utils.s3.upload_file_to_s3", fake_upload)

    svc = OnboardingService()
    result = await svc.load_sample_dataset(USER, DATASET_ID)

    # A real object was uploaded under the user's server-derived prefix (#541 AC1)...
    assert captured["key"].startswith(f"datasets/{USER}/")
    assert captured["key"].endswith(".csv")
    assert captured["bytes"], "the CSV bytes must actually be uploaded"
    # ...and the STORED url points at that real object, not the old fabricated one.
    assert result["s3_url"] == f"s3://test-bucket/{captured['key']}"
    assert "sample-bucket.s3.amazonaws.com" not in result["s3_url"]

    ud = await UserData.get(result["upload_id"])
    assert ud is not None and ud.s3_url == result["s3_url"]
    assert ud.num_rows > 0 and ud.is_processed is True


async def test_progress_persists_for_a_user_with_no_dataset(setup_database, monkeypatch):
    """#541 AC4: saving progress for a brand-new user (no UserData) must not raise and
    must NOT create an invalid UserData — it writes a dedicated OnboardingProgress doc."""
    # Avoid Redis cache masking the DB round-trip.
    from app.services import redis_cache

    monkeypatch.setattr(redis_cache.cache_service, "get_user_progress", _async_none)
    monkeypatch.setattr(redis_cache.cache_service, "cache_user_progress", _async_noop)

    svc = OnboardingService()
    new_user = "onboarding_brand_new_user"
    # Build it the way the service does (via its own get-or-create) so required fields are set.
    progress = await svc._get_or_create_user_progress(new_user)

    await svc._save_user_progress(new_user, progress)  # must not raise

    record = await OnboardingProgress.find_one(OnboardingProgress.user_id == new_user)
    assert record is not None and record.progress.get("user_id") == new_user
    # No UserData was fabricated for a user who never uploaded anything.
    assert await UserData.find(UserData.user_id == new_user).count() == 0

    # And it reads back through the dedicated collection.
    loaded = await svc._get_or_create_user_progress(new_user)
    assert loaded.user_id == new_user


async def test_legacy_progress_on_user_data_is_migrated_read_through(setup_database, monkeypatch):
    """#541 (codex): a user onboarded before this change has progress on
    UserData.onboarding_progress — preserve it (read-through) instead of resetting to
    step zero when the new collection is empty and the cache is cold."""
    from app.models.user_data import UserData
    from app.services import redis_cache

    monkeypatch.setattr(redis_cache.cache_service, "get_user_progress", _async_none)
    monkeypatch.setattr(redis_cache.cache_service, "cache_user_progress", _async_noop)

    from datetime import UTC, datetime

    from app.schemas.onboarding import OnboardingUserProgress

    legacy_user = "onboarding_legacy_user"
    # A realistic legacy dump: the old code stored progress.dict() (all fields present).
    legacy_progress = OnboardingUserProgress(
        user_id=legacy_user, started_at=datetime.now(UTC), last_activity_at=datetime.now(UTC)
    )
    legacy_progress.completed_steps = ["welcome", "upload_data"]
    await UserData(
        user_id=legacy_user, filename="d.csv", original_filename="d.csv", s3_url="s3://b/d.csv",
        num_rows=1, num_columns=1, data_schema=[], contains_pii=False,
        onboarding_progress=legacy_progress.dict(),
    ).insert()

    svc = OnboardingService()
    progress = await svc._get_or_create_user_progress(legacy_user)
    assert "welcome" in progress.completed_steps and "upload_data" in progress.completed_steps

    # Saving migrates it into the dedicated collection.
    await svc._save_user_progress(legacy_user, progress)
    record = await OnboardingProgress.find_one(OnboardingProgress.user_id == legacy_user)
    assert record is not None
    assert set(record.progress["completed_steps"]) >= {"welcome", "upload_data"}


async def test_save_progress_is_idempotent_upsert(setup_database, monkeypatch):
    """The save path is an upsert: repeated saves for the same user never raise on the
    unique user_id index (the concurrent-first-save race, codex)."""
    from app.services import redis_cache

    monkeypatch.setattr(redis_cache.cache_service, "get_user_progress", _async_none)
    monkeypatch.setattr(redis_cache.cache_service, "cache_user_progress", _async_noop)

    svc = OnboardingService()
    user = "onboarding_upsert_user"
    p = await svc._get_or_create_user_progress(user)
    await svc._save_user_progress(user, p)
    await svc._save_user_progress(user, p)  # second save must update, not DuplicateKeyError
    assert await OnboardingProgress.find(OnboardingProgress.user_id == user).count() == 1


async def _async_none(*args, **kwargs):
    return None


async def _async_noop(*args, **kwargs):
    return None
