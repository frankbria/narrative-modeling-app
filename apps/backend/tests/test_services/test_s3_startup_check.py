"""S3Service.verify_bucket_writable — fail-fast startup guard (#495).

Runs only in a production-like environment (wired in main.py's lifespan), so a
deployment refuses to boot on a missing/unwritable bucket rather than writing to a
guessed one (AC2/AC4). dev/test/CI never invoke it (is_production_like() is False),
which these tests also assert so the guard can't silently start tripping CI.
"""

from unittest.mock import MagicMock, patch

import pytest

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
    with patch("app.services.s3_service.configured_bucket", return_value="b"):
        svc = _svc(mock_mode=False, client=client)
        svc.verify_bucket_writable()  # no raise
    client.put_object.assert_called_once()
    # The probe object is removed, not left behind.
    client.delete_object.assert_called_once()
    assert client.put_object.call_args.kwargs["Bucket"] == "b"
    assert client.delete_object.call_args.kwargs["Key"] == client.put_object.call_args.kwargs["Key"]


@pytest.mark.unit
def test_guard_does_not_run_in_the_test_environment():
    """The lifespan only calls verify_bucket_writable() when is_production_like();
    in the test env that is False, so CI/test never trip the probe."""
    from app.config import is_production_like

    assert is_production_like() is False
