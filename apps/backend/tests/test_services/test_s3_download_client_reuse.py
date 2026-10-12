"""#722: `download_file_from_s3` built a new boto3 client on every call.

#519 made `get_s3_client()` reuse one bounded client, but this downloader, which
backs `load_dataframe_from_s3` (feature engineering, transformation, EDA), still
called `create_s3_client()` per invocation.
"""

import os
from unittest.mock import MagicMock

import pytest

from app.services.s3_service import download_file_from_s3
from app.utils.s3 import reset_s3_client

URL = "https://reuse-bucket.s3.amazonaws.com/datasets/user1/file.csv"


def _client() -> MagicMock:
    client = MagicMock()
    client.head_object.return_value = {"ContentLength": 10}
    return client


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "reuse-key")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "reuse-secret")
    monkeypatch.setenv("AWS_S3_BUCKET", "reuse-bucket")
    # Nothing listens here. If a client is ever built for real in these tests, it
    # fails on this machine and does not send a request to AWS.
    monkeypatch.setenv("AWS_ENDPOINT_URL", "http://127.0.0.1:9")
    reset_s3_client()
    yield
    reset_s3_client()


def _download() -> None:
    os.unlink(download_file_from_s3(URL))


def test_repeated_downloads_share_one_client(configured, monkeypatch):
    built: list[MagicMock] = []

    def build() -> MagicMock:
        built.append(_client())
        return built[-1]

    monkeypatch.setattr("app.utils.s3.create_s3_client", build)

    for _ in range(3):
        _download()

    assert len(built) == 1
    assert built[0].download_file.call_count == 3


def test_a_rotated_credential_gets_a_new_client(configured, monkeypatch):
    built: list[MagicMock] = []

    def build() -> MagicMock:
        built.append(_client())
        return built[-1]

    monkeypatch.setattr("app.utils.s3.create_s3_client", build)

    _download()
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "rotated")
    _download()

    assert len(built) == 2
    assert built[1].download_file.call_count == 1


def test_without_credentials_it_builds_a_client_per_call_as_before(monkeypatch):
    """The shared client is not available with no credentials in the environment
    (`get_s3_client` returns None). The downloader must not turn that into a new
    failure of its own: it builds a client as it always did, and boto3 reports what
    is missing when the request is made."""
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    monkeypatch.setenv("AWS_S3_BUCKET", "reuse-bucket")
    reset_s3_client()
    built: list[MagicMock] = []

    def build() -> MagicMock:
        built.append(_client())
        return built[-1]

    monkeypatch.setattr("app.services.s3_service.create_s3_client", build)

    _download()
    _download()

    assert len(built) == 2
