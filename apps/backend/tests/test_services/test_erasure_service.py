"""Unit tests for the pure helpers in the erasure service (issue #259).

These need no database — they exercise the S3-key derivation and ObjectId
guard that decide which id-space a target belongs to. The full cascade is
covered by tests/test_integration/test_erasure_cascade.py (real Mongo + S3).
"""

import pytest
from beanie import PydanticObjectId

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
