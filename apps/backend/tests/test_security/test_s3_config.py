"""Tests for the S3 bucket/region env resolvers (issue #257).

One logical bucket was historically read under three names (uploads via
``AWS_BUCKET_NAME``/``S3_BUCKET_NAME``, the download allowlist via
``AWS_S3_BUCKET``, versioning via ``S3_BUCKET``) and the region under two
(``AWS_REGION`` vs boto3's ``AWS_DEFAULT_REGION``). Staging set only one name of
each, so downloads raised and versioning targeted the wrong bucket.

``resolve_s3_bucket`` / ``resolve_aws_region`` are the pure resolvers so a deploy
that sets any one name works everywhere.
"""

import pytest

from app.config import S3_BUCKET_ENV_NAMES, resolve_aws_region, resolve_s3_bucket

pytestmark = [pytest.mark.unit, pytest.mark.security]

_ALL_BUCKET_VARS = (
    "AWS_BUCKET_NAME",
    "AWS_S3_BUCKET",
    "S3_BUCKET",
    "S3_BUCKET_NAME",
)
_ALL_REGION_VARS = ("AWS_REGION", "AWS_DEFAULT_REGION")


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    for name in _ALL_BUCKET_VARS + _ALL_REGION_VARS:
        monkeypatch.delenv(name, raising=False)


class TestResolveS3Bucket:
    @pytest.mark.parametrize("name", _ALL_BUCKET_VARS)
    def test_reads_any_single_name(self, monkeypatch, name):
        monkeypatch.setenv(name, "my-bucket")
        assert resolve_s3_bucket() == "my-bucket"

    def test_none_when_unset(self):
        assert resolve_s3_bucket() is None

    def test_precedence_prefers_aws_bucket_name(self, monkeypatch):
        monkeypatch.setenv("S3_BUCKET", "loser")
        monkeypatch.setenv("AWS_BUCKET_NAME", "winner")
        assert resolve_s3_bucket() == "winner"

    def test_strips_and_skips_blank(self, monkeypatch):
        monkeypatch.setenv("AWS_BUCKET_NAME", "   ")
        monkeypatch.setenv("AWS_S3_BUCKET", "  real-bucket  ")
        assert resolve_s3_bucket() == "real-bucket"

    def test_env_name_list_matches_precedence(self):
        # Guard: the documented precedence order is what the resolver iterates.
        assert S3_BUCKET_ENV_NAMES[0] == "AWS_BUCKET_NAME"


class TestResolveAwsRegion:
    def test_prefers_aws_region(self, monkeypatch):
        monkeypatch.setenv("AWS_REGION", "eu-west-1")
        monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-2")
        assert resolve_aws_region() == "eu-west-1"

    def test_falls_back_to_aws_default_region(self, monkeypatch):
        monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-2")
        assert resolve_aws_region() == "us-east-2"

    def test_default_when_unset(self):
        assert resolve_aws_region() == "us-east-1"

    def test_blank_value_falls_through_to_default(self, monkeypatch):
        monkeypatch.setenv("AWS_REGION", "   ")
        assert resolve_aws_region() == "us-east-1"
