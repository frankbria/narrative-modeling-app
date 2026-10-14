"""S3Service.verify_bucket_writable — fail-fast startup guard (#495).

Runs only in a production-like environment (wired in main.py's lifespan), so a
deployment refuses to boot on a missing/unwritable bucket rather than writing to a
guessed one (AC2/AC4). dev/test/CI never invoke it (is_production_like() is False),
which these tests also assert so the guard can't silently start tripping CI.
"""

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from app.services.s3_service import S3Service


def _svc(mock_mode: bool, client: MagicMock | None) -> S3Service:
    svc = S3Service.__new__(S3Service)  # skip __init__ (which reads real env)
    svc.is_mock_mode = mock_mode
    svc.s3_client = client
    return svc


@pytest.mark.unit
def test_raises_when_no_bucket_configured():
    with patch("app.services.s3_service.configured_bucket", return_value=None):
        svc = _svc(mock_mode=False, client=MagicMock())
        with pytest.raises(RuntimeError, match="No S3 bucket is configured"):
            svc.verify_bucket_writable()


@pytest.mark.unit
def test_raises_when_in_mock_mode():
    with patch("app.services.s3_service.configured_bucket", return_value="b"):
        svc = _svc(mock_mode=True, client=None)
        with pytest.raises(RuntimeError, match="mock mode"):
            svc.verify_bucket_writable()


@pytest.mark.unit
def test_raises_when_the_bucket_is_not_writable():
    client = MagicMock()
    client.put_object.side_effect = Exception("AccessDenied")
    with patch("app.services.s3_service.configured_bucket", return_value="b"):
        svc = _svc(mock_mode=False, client=client)
        with pytest.raises(RuntimeError, match="not writable"):
            svc.verify_bucket_writable()


@pytest.mark.unit
def test_happy_path_probes_and_cleans_up():
    client = MagicMock()
    client.put_object.return_value = {}  # a bucket that was never versioned
    with patch("app.services.s3_service.configured_bucket", return_value="b"):
        svc = _svc(mock_mode=False, client=client)
        svc.verify_bucket_writable()  # no raise
    client.put_object.assert_called_once()
    # The probe object is removed, not left behind.
    client.delete_object.assert_called_once()
    assert client.put_object.call_args.kwargs["Bucket"] == "b"
    assert client.delete_object.call_args.kwargs["Key"] == client.put_object.call_args.kwargs["Key"]


@pytest.mark.unit
def test_on_a_versioned_bucket_the_probe_deletes_the_version_it_wrote():
    # #529: a plain delete on a versioned bucket keeps the bytes as a noncurrent
    # version and adds a delete marker, one of each per boot, for ever.
    client = MagicMock()
    client.put_object.return_value = {"VersionId": "v-1"}
    with patch("app.services.s3_service.configured_bucket", return_value="b"):
        _svc(mock_mode=False, client=client).verify_bucket_writable()
    client.delete_object.assert_called_once()
    assert client.delete_object.call_args.kwargs["VersionId"] == "v-1"


@pytest.mark.unit
def test_a_refused_version_delete_falls_back_to_the_plain_one_and_boots():
    # Deleting a version needs s3:DeleteObjectVersion. A policy without it must not
    # turn a writable bucket into a refused boot.
    client = MagicMock()
    client.put_object.return_value = {"VersionId": "v-1"}
    client.delete_object.side_effect = [
        ClientError({"Error": {"Code": "AccessDenied"}}, "DeleteObject"),
        {},
    ]
    with patch("app.services.s3_service.configured_bucket", return_value="b"):
        _svc(mock_mode=False, client=client).verify_bucket_writable()  # no raise
    first, second = client.delete_object.call_args_list
    assert first.kwargs["VersionId"] == "v-1"
    assert "VersionId" not in second.kwargs
    assert second.kwargs["Key"] == client.put_object.call_args.kwargs["Key"]


@pytest.mark.unit
def test_a_bucket_that_cannot_delete_at_all_still_refuses_the_boot():
    client = MagicMock()
    client.put_object.return_value = {}
    client.delete_object.side_effect = ClientError({"Error": {"Code": "AccessDenied"}}, "DeleteObject")
    with patch("app.services.s3_service.configured_bucket", return_value="b"):
        with pytest.raises(RuntimeError, match="not writable"):
            _svc(mock_mode=False, client=client).verify_bucket_writable()


@pytest.mark.unit
def test_guard_does_not_run_in_the_test_environment():
    """The lifespan only calls verify_bucket_writable() when is_production_like();
    in the test env that is False, so CI/test never trip the probe."""
    from app.config import is_production_like

    assert is_production_like() is False
