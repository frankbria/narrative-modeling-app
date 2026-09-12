"""Unit tests for the pure helpers in the erasure service (issue #259).

These need no database — they exercise the S3-key derivation and ObjectId
guard that decide which id-space a target belongs to. The full cascade is
covered by tests/test_integration/test_erasure_cascade.py (real Mongo + S3).
"""

import pytest
from beanie import PydanticObjectId

from app.schemas.erasure import DeletionManifest
from app.services.erasure_service import _as_object_id, _s3_key

pytestmark = pytest.mark.unit


class TestS3KeyDerivation:
    def test_bare_key_passes_through(self):
        # DatasetMetadata.file_path is already a raw key.
        assert _s3_key("datasets/user1/dataset_abc_data.csv", "bucket") == (
            "datasets/user1/dataset_abc_data.csv"
        )

    def test_s3_url_strips_scheme_and_bucket(self):
        assert _s3_key("s3://bucket/models/u/m/model.pkl", "bucket") == "models/u/m/model.pkl"

    def test_https_url_strips_host(self):
        url = "https://bucket.s3.us-east-1.amazonaws.com/datasets/u/file.csv"
        assert _s3_key(url, "bucket") == "datasets/u/file.csv"

    # #481: every persisted shape must derive the key of the object actually
    # written, or delete_object matches nothing and erasure "succeeds" anyway.
    def test_presigned_url_drops_the_query_string(self):
        url = (
            "https://bucket.s3.amazonaws.com/datasets/u/file.csv"
            "?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Expires=3600&X-Amz-Signature=abc"
        )
        assert _s3_key(url, "bucket") == "datasets/u/file.csv"

    def test_endpoint_style_url_drops_the_bucket_segment(self, monkeypatch):
        # MinIO/LocalStack: {endpoint}/{bucket}/{key}. The old parser returned
        # "bucket/datasets/u/file.csv" here.
        monkeypatch.setenv("AWS_ENDPOINT_URL", "http://localhost:4566")
        url = "http://localhost:4566/bucket/datasets/u/file.csv"
        assert _s3_key(url, "bucket") == "datasets/u/file.csv"

    def test_endpoint_style_presigned_url(self, monkeypatch):
        monkeypatch.setenv("AWS_ENDPOINT_URL", "http://localhost:9000")
        url = "http://localhost:9000/bucket/datasets/u/file.csv?X-Amz-Signature=abc"
        assert _s3_key(url, "bucket") == "datasets/u/file.csv"

    # #616: the bucket a stored URL names must be OUR bucket, or nothing is deleted
    # and the manifest says why — never a delete of whatever holds that key in ours.
    def test_matching_bucket_yields_the_key_and_no_failure(self):
        manifest = DeletionManifest(target_type="dataset", target_id="d", subject_user_id="u")
        assert _s3_key("s3://bucket/datasets/u/file.csv", "bucket", manifest) == "datasets/u/file.csv"
        assert manifest.failures == []

    def test_foreign_s3_url_is_refused_and_recorded(self):
        manifest = DeletionManifest(target_type="dataset", target_id="d", subject_user_id="u")
        assert _s3_key("s3://someone-elses-bucket/datasets/u/file.csv", "ours", manifest) is None
        assert len(manifest.failures) == 1
        assert "someone-elses-bucket" in manifest.failures[0]
        assert "'ours'" in manifest.failures[0]  # the configured bucket, quoted, not a substring accident

    def test_foreign_endpoint_style_url_is_refused(self, monkeypatch):
        monkeypatch.setenv("AWS_ENDPOINT_URL", "http://localhost:4566")
        manifest = DeletionManifest(target_type="dataset", target_id="d", subject_user_id="u")
        url = "http://localhost:4566/staging-bucket/datasets/u/file.csv"
        assert _s3_key(url, "bucket", manifest) is None
        assert manifest.failures and "staging-bucket" in manifest.failures[0]

    def test_foreign_bucket_without_a_manifest_still_refuses(self):
        assert _s3_key("s3://other/datasets/u/file.csv", "bucket") is None

    def test_bucketless_url_falls_back_to_the_configured_bucket(self):
        manifest = DeletionManifest(target_type="dataset", target_id="d", subject_user_id="u")
        # parse_s3_url returns bucket=None for an arbitrary https host; the key is
        # the path and the caller's bucket is the only one there is.
        assert _s3_key("https://files.example.com/datasets/u/file.csv", "bucket", manifest) == "datasets/u/file.csv"
        assert manifest.failures == []

    def test_s3_url_with_query_and_fragment(self):
        assert _s3_key("s3://bucket/datasets/u/f.csv?versionId=1#x", "bucket") == "datasets/u/f.csv"

    def test_bare_key_containing_a_question_mark_is_not_truncated(self):
        # `?` is legal in an S3 key and datasets.py puts the raw client filename in
        # file_path; trimming at `?` (an earlier revision of this PR) would delete
        # "…/ds1_what" — a key that does not exist — and report success.
        key = "datasets/u1/ds1_what?.csv"
        assert _s3_key(key, "bucket") == key

    def test_bare_key_containing_a_url_mid_string_is_still_a_key(self):
        # Keys are built from client filenames in places; "://" inside one must not
        # route it to the URL parser, which would fail and skip the delete silently.
        key = "datasets/u1/notes http://example.com.csv"
        assert _s3_key(key, "bucket") == key

    def test_url_without_a_key_returns_none(self):
        assert _s3_key("s3://bucket", "bucket") is None
        assert _s3_key("https://bucket.s3.amazonaws.com/", "bucket") is None

    def test_none_returns_none(self):
        assert _s3_key(None, "bucket") is None

    def test_empty_returns_none(self):
        assert _s3_key("", "bucket") is None


class TestObjectIdGuard:
    def test_valid_objectid(self):
        oid = PydanticObjectId()
        assert _as_object_id(str(oid)) == oid

    def test_dataset_string_is_not_objectid(self):
        # 'dataset_xxx' strings must NOT resolve to an ObjectId, else we'd sweep
        # the wrong id-space.
        assert _as_object_id("dataset_abc123") is None

    def test_garbage_is_none(self):
        assert _as_object_id("not-an-id") is None
