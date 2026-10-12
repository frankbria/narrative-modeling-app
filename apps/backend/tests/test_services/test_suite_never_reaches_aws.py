"""#878: a test run cannot write to a real bucket, and development says so when it can.

`tests/conftest.py` used to `setdefault` one bucket name and nothing else. `app.config`
then loaded the developer's `.env`, so every S3 client the suite built that a test had
not mocked carried the real bucket's credentials and pointed at AWS: the bucket staging
uses. Staging's audits then counted objects that tests and local runs had put there.
"""
import logging
import os

import pytest

PINNED = os.environ.get("S3_ENDPOINT_URL") or "http://localhost:4566"


def test_the_suite_pins_its_endpoint_and_carries_no_credentials():
    assert os.environ["AWS_ENDPOINT_URL"] == PINNED
    assert os.environ["AWS_ACCESS_KEY_ID"] == "" and os.environ["AWS_SECRET_ACCESS_KEY"] == ""
    assert not os.environ.get("AWS_SESSION_TOKEN")


def test_a_dotenv_file_cannot_put_the_real_settings_back(tmp_path):
    """`app.config` loads `.env` without override, so a variable the suite has set,
    even to nothing, is not replaced."""
    from dotenv import load_dotenv

    env_file = tmp_path / ".env"
    env_file.write_text(
        "AWS_ACCESS_KEY_ID=AKIAREALKEY\nAWS_SECRET_ACCESS_KEY=real-secret\n"
        "AWS_SESSION_TOKEN=real-token\nAWS_ENDPOINT_URL=https://s3.amazonaws.com\n"
    )

    load_dotenv(dotenv_path=env_file)

    assert os.environ["AWS_ENDPOINT_URL"] == PINNED
    assert os.environ["AWS_ACCESS_KEY_ID"] == "" and os.environ["AWS_SECRET_ACCESS_KEY"] == ""
    assert not os.environ.get("AWS_SESSION_TOKEN")


def test_every_client_the_app_builds_points_away_from_aws(monkeypatch):
    """Even holding credentials, as a test that sets its own does."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAEXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "example-secret")
    from app.services.s3_service import S3Service
    from app.services.versioning_service import VersioningService
    from app.utils.s3 import create_s3_client, get_s3_client, reset_s3_client

    reset_s3_client()
    clients = {
        "create_s3_client": create_s3_client(),
        "get_s3_client": get_s3_client(),
        "S3Service": S3Service().s3_client,
        "VersioningService": VersioningService().s3_client,
    }
    reset_s3_client()

    for name, client in clients.items():
        assert client is not None, name
        assert client.meta.endpoint_url == PINNED, f"{name} points at {client.meta.endpoint_url}"
        assert "amazonaws" not in client.meta.endpoint_url


REAL = {"ENVIRONMENT": "development", "AWS_ACCESS_KEY_ID": "AKIAEXAMPLE", "AWS_SECRET_ACCESS_KEY": "s", "AWS_S3_BUCKET": "a-bucket"}


def _environment(monkeypatch, **changes):
    for name in ("NODE_ENV", "AWS_ENDPOINT_URL", "AWS_BUCKET_NAME", "S3_BUCKET_NAME", "S3_BUCKET"):
        monkeypatch.delenv(name, raising=False)
    for name, value in {**REAL, **changes}.items():
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)


class TestDevelopmentOnARealBucket:
    def test_development_with_a_bucket_credentials_and_no_endpoint_is_a_real_bucket(self, monkeypatch):
        from app.config import development_uses_a_real_bucket

        _environment(monkeypatch)

        assert development_uses_a_real_bucket() is True

    @pytest.mark.parametrize("changes", [
        {"AWS_ENDPOINT_URL": "http://localhost:4566"},  # LocalStack: the documented setup
        {"ENVIRONMENT": "test"},
        {"ENVIRONMENT": "staging"},  # a deployed environment owns its bucket
        {"AWS_ACCESS_KEY_ID": ""},  # no credentials: nothing can be written
        {"AWS_S3_BUCKET": None},  # no bucket configured
    ])
    def test_anything_else_is_not(self, monkeypatch, changes):
        from app.config import development_uses_a_real_bucket

        _environment(monkeypatch, **changes)

        assert development_uses_a_real_bucket() is False

    def test_the_backend_says_so_once_when_it_starts(self, monkeypatch, caplog):
        from app.services.s3_service import S3Service

        _environment(monkeypatch)
        with caplog.at_level(logging.WARNING, logger="app.services.s3_service"):
            S3Service()

        warnings = [r.getMessage() for r in caplog.records if "AWS_ENDPOINT_URL" in r.getMessage()]
        assert len(warnings) == 1
        assert "development" in warnings[0] and "http://localhost:4566" in warnings[0]
        assert "a-bucket" not in warnings[0], "the bucket's name stays out of the log line"

    def test_it_says_nothing_when_development_uses_localstack(self, monkeypatch, caplog):
        from app.services.s3_service import S3Service

        _environment(monkeypatch, AWS_ENDPOINT_URL="http://localhost:4566")
        with caplog.at_level(logging.WARNING, logger="app.services.s3_service"):
            S3Service()

        assert [r for r in caplog.records if "AWS_ENDPOINT_URL" in r.getMessage()] == []


def test_a_client_that_cannot_be_built_leaves_the_service_in_mock_mode(monkeypatch):
    """Credentials are present, so the service tries; the failure must not stop the import."""
    from app.services import s3_service as module

    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAEXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "example-secret")

    def refuse():
        raise RuntimeError("no client for you")

    monkeypatch.setattr(module, "create_s3_client", refuse)

    service = module.S3Service()

    assert service.is_mock_mode is True and service.s3_client is None
