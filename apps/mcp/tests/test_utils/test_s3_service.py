import pytest

from mcp.utils.s3_service import parse_and_validate_s3_url

BUCKET = "app-bucket"


def test_parses_s3_scheme_url():
    assert parse_and_validate_s3_url("s3://app-bucket/data/f.csv", BUCKET) == (
        "app-bucket",
        "data/f.csv",
    )


def test_parses_https_virtual_host_url():
    assert parse_and_validate_s3_url(
        "https://app-bucket.s3.amazonaws.com/data/f.csv", BUCKET
    ) == ("app-bucket", "data/f.csv")


def test_parses_https_regional_url_and_url_decodes_key():
    bucket, key = parse_and_validate_s3_url(
        "https://app-bucket.s3.us-east-1.amazonaws.com/data/my%20file.csv?x=1",
        BUCKET,
    )
    assert bucket == "app-bucket"
    assert key == "data/my file.csv"


def test_rejects_other_bucket():
    with pytest.raises(ValueError):
        parse_and_validate_s3_url("s3://other-bucket/data/f.csv", BUCKET)


def test_rejects_when_bucket_unconfigured():
    with pytest.raises(ValueError):
        parse_and_validate_s3_url("s3://app-bucket/data/f.csv", None)


def test_rejects_unrecognized_url():
    with pytest.raises(ValueError):
        parse_and_validate_s3_url("https://evil.example.com/data/f.csv", BUCKET)


def test_rejects_missing_key():
    with pytest.raises(ValueError):
        parse_and_validate_s3_url("s3://app-bucket/", BUCKET)
