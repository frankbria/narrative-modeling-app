import os
import tempfile

import pytest

from mcp.utils.s3_service import download_dataset_file, parse_and_validate_s3_url

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


def test_download_removes_temp_file_on_failed_download(tmp_path, monkeypatch):
    """A failed S3 download must not leave the just-created temp file behind.

    Real filesystem (temp file created and removed); only the network S3 client
    is stubbed to force the failure path.
    """
    monkeypatch.setenv("AWS_S3_BUCKET", "app-bucket")
    created: dict[str, str] = {}
    real_ntf = tempfile.NamedTemporaryFile

    def fake_ntf(*args, **kwargs):
        kwargs["dir"] = str(tmp_path)
        f = real_ntf(*args, **kwargs)
        created["path"] = f.name
        return f

    monkeypatch.setattr(
        "mcp.utils.s3_service.tempfile.NamedTemporaryFile", fake_ntf
    )

    class FailingClient:
        def download_file(self, *args, **kwargs):
            raise RuntimeError("AccessDenied")

    monkeypatch.setattr(
        "mcp.utils.s3_service.boto3.client", lambda *a, **k: FailingClient()
    )

    with pytest.raises(RuntimeError):
        download_dataset_file("s3://app-bucket/data/f.csv")

    assert not os.path.exists(created["path"])
