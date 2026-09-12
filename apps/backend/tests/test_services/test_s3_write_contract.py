"""The one-bucket contract on the write side (#622).

#621 put every download on `configured_bucket()` / `validate_object_key()`.
Three gaps stayed: the versioning service resolved its bucket from a third
precedence at import time, the S3Service write methods took raw keys against a
bucket fixed at construction, and nothing tested that every reader and writer
answers the same bucket. These tests do.
"""

from unittest.mock import MagicMock

import pytest

from app.config import resolve_configured_bucket
from app.services.s3_service import S3Service
from app.utils.s3 import allowed_bucket, configured_bucket, validate_object_key

LEGACY_ROOT = "masked_123e4567-e89b-12d3-a456-426614174000.csv"


@pytest.fixture
def three_different_names(monkeypatch):
    monkeypatch.setenv("S3_BUCKET", "bucket-from-S3_BUCKET")
    monkeypatch.setenv("AWS_S3_BUCKET", "bucket-from-AWS_S3_BUCKET")
    monkeypatch.setenv("AWS_BUCKET_NAME", "bucket-from-AWS_BUCKET_NAME")
    monkeypatch.delenv("S3_BUCKET_NAME", raising=False)
    monkeypatch.delenv("AWS_ENDPOINT_URL", raising=False)


def test_every_reader_and_writer_agrees_on_the_bucket(three_different_names):
    from app.services.versioning_service import VersioningService

    answers = {
        "resolve_configured_bucket": resolve_configured_bucket(),
        "configured_bucket": configured_bucket(),
        "allowed_bucket": allowed_bucket(),
        "S3Service.bucket_name": S3Service().bucket_name,
        "VersioningService.bucket_name": VersioningService().bucket_name,
    }
    assert len(set(answers.values())) == 1, answers
    # The readers' precedence (#567): AWS_S3_BUCKET first.
    assert set(answers.values()) == {"bucket-from-AWS_S3_BUCKET"}


def test_settings_no_longer_carries_its_own_bucket_precedence():
    from app.config import settings

    assert not hasattr(settings, "S3_BUCKET"), "settings.S3_BUCKET was a third precedence; consumers use configured_bucket()"


def test_validate_object_key_says_it_is_not_authorization():
    assert "not" in validate_object_key.__doc__ and "authoriz" in validate_object_key.__doc__


def _live_service(monkeypatch, bucket: str) -> tuple[S3Service, MagicMock]:
    monkeypatch.setenv("AWS_S3_BUCKET", bucket)
    monkeypatch.setenv("AWS_BUCKET_NAME", bucket)
    svc = S3Service()
    svc.is_mock_mode = False
    svc.s3_client = MagicMock()
    return svc, svc.s3_client


class TestWriteMethodsValidateTheirKey:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("bad_key", ["datasets/../../etc/passwd", "unauthorized/u/file.csv", "datasets/no-tenant-segment"])
    async def test_upload_refuses_before_touching_boto3(self, monkeypatch, bad_key):
        svc, client = _live_service(monkeypatch, "test-bucket")
        with pytest.raises(ValueError):
            await svc.upload_file_obj(MagicMock(), bad_key)
        client.upload_fileobj.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_refuses_a_foreign_namespace(self, monkeypatch):
        svc, client = _live_service(monkeypatch, "test-bucket")
        with pytest.raises(ValueError):
            await svc.delete_file("unauthorized/u/file.csv")
        client.delete_object.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_file_size_and_presign_refuse_traversal(self, monkeypatch):
        svc, client = _live_service(monkeypatch, "test-bucket")
        with pytest.raises(ValueError):
            await svc.get_file_size("exports/u/../../x")
        with pytest.raises(ValueError):
            svc.generate_presigned_url("exports/u/../../x")
        client.head_object.assert_not_called()
        client.generate_presigned_url.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_still_admits_a_pre_581_root_key(self, monkeypatch):
        # Erasure must keep removing the legacy root objects until #615 moves them.
        svc, client = _live_service(monkeypatch, "test-bucket")
        assert await svc.delete_file(LEGACY_ROOT) is True
        client.delete_object.assert_called_once_with(Bucket="test-bucket", Key=LEGACY_ROOT)

    @pytest.mark.asyncio
    async def test_a_new_write_may_not_use_the_legacy_root_shape(self, monkeypatch):
        # Only delete/head admit the pre-#581 root shape; a NEW object must be namespaced.
        svc, client = _live_service(monkeypatch, "test-bucket")
        with pytest.raises(ValueError):
            await svc.upload_file_obj(MagicMock(), LEGACY_ROOT)
        with pytest.raises(ValueError):
            svc.generate_presigned_url(LEGACY_ROOT)
        client.upload_fileobj.assert_not_called()

    @pytest.mark.asyncio
    async def test_every_namespace_a_writer_uses_is_admitted(self, monkeypatch):
        svc, client = _live_service(monkeypatch, "test-bucket")
        for key in (
            "datasets/u/abc.csv",
            "transformed/u/d_123.parquet",
            "models/u/m/model.pkl",
            "batch-jobs/u/m/2026/input.csv",
            "exports/u/f/report.xlsx",
        ):
            await svc.upload_file_obj(MagicMock(), key)
        assert client.upload_fileobj.call_count == 5


class TestWriteMethodsResolveTheBucketLive:
    @pytest.mark.asyncio
    async def test_delete_follows_the_environment_not_the_constructor(self, monkeypatch):
        svc, client = _live_service(monkeypatch, "first-bucket")
        monkeypatch.setenv("AWS_S3_BUCKET", "later-bucket")
        monkeypatch.setenv("AWS_BUCKET_NAME", "later-bucket")
        await svc.delete_file("datasets/u/file.csv")
        client.delete_object.assert_called_once_with(Bucket="later-bucket", Key="datasets/u/file.csv")

    @pytest.mark.asyncio
    async def test_upload_and_download_use_the_same_bucket(self, monkeypatch):
        svc, client = _live_service(monkeypatch, "one-bucket")
        await svc.upload_file_obj(MagicMock(), "datasets/u/file.csv")
        (_, bucket_used, _), _ = client.upload_fileobj.call_args  # (file_obj, bucket, key)
        assert bucket_used == allowed_bucket() == "one-bucket"

    def test_presign_uses_the_live_bucket(self, monkeypatch):
        svc, client = _live_service(monkeypatch, "first-bucket")
        monkeypatch.setenv("AWS_S3_BUCKET", "later-bucket")
        monkeypatch.setenv("AWS_BUCKET_NAME", "later-bucket")
        svc.generate_presigned_url("exports/u/f/report.csv")
        params = client.generate_presigned_url.call_args.kwargs["Params"]
        assert params["Bucket"] == "later-bucket"


class TestConsumersOfTheLiveBucket:
    def test_model_storage_derives_keys_from_the_stored_path_not_the_current_bucket(self, monkeypatch):
        from app.services.model_storage import _key_of

        # Written under one bucket name, read after the environment moved on.
        assert _key_of("s3://old-bucket/models/u1/m1/model.pkl") == "models/u1/m1/model.pkl"
        assert _key_of("models/u1/m1/model.pkl") == "models/u1/m1/model.pkl"

    @pytest.mark.asyncio
    async def test_download_honours_the_same_pin_as_the_writers(self, monkeypatch):
        svc, client = _live_service(monkeypatch, "env-bucket")
        svc.bucket_name = "pinned-bucket"
        client.get_object.return_value = {"Body": MagicMock(read=lambda: b"x"), "ContentLength": 1}
        client.head_object.return_value = {"ContentLength": 1}
        await svc.download_file_bytes("datasets/u/file.csv")
        assert client.head_object.call_args.kwargs["Bucket"] == "pinned-bucket"
