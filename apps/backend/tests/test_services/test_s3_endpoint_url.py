"""
Tests for AWS_ENDPOINT_URL support in S3 download operations.

When AWS_ENDPOINT_URL is set (S3-compatible storage such as MinIO in CI),
stored URLs have the form {endpoint}/{bucket}/{key} instead of
https://{bucket}.s3.amazonaws.com/{key}. These tests verify:
1. Endpoint-style URLs are parsed correctly
2. All security validations (bucket whitelist, path traversal,
   path structure) still apply to endpoint-style URLs
3. The amazonaws URL path is unchanged when no endpoint is configured
"""

import os
from unittest.mock import Mock, patch

import pytest
from tenacity import RetryError

from app.services.s3_service import download_file_from_s3
from app.utils.circuit_breaker import CircuitBreakerOpen


def get_error_message(exc_value):
    """Extract error message from ValueError, RetryError, or CircuitBreakerOpen."""
    if isinstance(exc_value, CircuitBreakerOpen):
        return "Circuit breaker activated (security validation failures)"
    elif isinstance(exc_value, RetryError):
        return str(exc_value.last_attempt.exception())
    return str(exc_value)


ENDPOINT_ENV = {
    "AWS_S3_BUCKET": "test-bucket",
    "AWS_ACCESS_KEY_ID": "minioadmin",
    "AWS_SECRET_ACCESS_KEY": "minioadmin",
    "AWS_REGION": "us-east-1",
    "AWS_ENDPOINT_URL": "http://localhost:9000",
}


@pytest.mark.unit
class TestEndpointUrlParsing:
    """Endpoint-style URL parsing with security validation intact."""

    def test_valid_endpoint_url_downloads(self):
        """A well-formed endpoint URL is parsed and downloaded."""
        with patch.dict(os.environ, ENDPOINT_ENV):
            with patch("app.utils.s3.boto3.client") as mock_client_factory:
                mock_client = Mock()
                mock_client.head_object.return_value = {"ContentLength": 1024}
                mock_client.download_file.return_value = None
                mock_client_factory.return_value = mock_client

                result = download_file_from_s3(
                    "http://localhost:9000/test-bucket/datasets/user123/data.csv"
                )

                assert result  # temp file path returned
                mock_client.download_file.assert_called_once()
                args = mock_client.download_file.call_args[0]
                assert args[0] == "test-bucket"
                assert args[1] == "datasets/user123/data.csv"
                # Client must be created against the custom endpoint
                _, kwargs = mock_client_factory.call_args
                assert kwargs.get("endpoint_url") == "http://localhost:9000"

    def test_endpoint_url_bucket_whitelist_enforced(self):
        """Cross-bucket access via endpoint URL is denied."""
        with patch.dict(os.environ, ENDPOINT_ENV):
            with pytest.raises((ValueError, RetryError, CircuitBreakerOpen)) as exc_info:
                download_file_from_s3(
                    "http://localhost:9000/victim-bucket/datasets/user123/data.csv"
                )
            msg = get_error_message(exc_info.value)
            assert "not allowed" in msg or "Circuit breaker" in msg

    def test_endpoint_url_path_traversal_blocked(self):
        """Path traversal in endpoint URL is rejected."""
        with patch.dict(os.environ, ENDPOINT_ENV):
            with pytest.raises((ValueError, RetryError, CircuitBreakerOpen)) as exc_info:
                download_file_from_s3(
                    "http://localhost:9000/test-bucket/datasets/../admin/secrets.csv"
                )
            msg = get_error_message(exc_info.value)
            assert (
                "path traversal" in msg.lower()
                or "path structure" in msg.lower()
                or "Circuit breaker" in msg
            )

    def test_endpoint_url_missing_key_rejected(self):
        """Endpoint URL without an object key is rejected."""
        with patch.dict(os.environ, ENDPOINT_ENV):
            with pytest.raises((ValueError, RetryError, CircuitBreakerOpen)) as exc_info:
                download_file_from_s3("http://localhost:9000/test-bucket")
            msg = get_error_message(exc_info.value)
            assert "Invalid S3 URL format" in msg or "Circuit breaker" in msg

    def test_amazonaws_url_still_works_without_endpoint(self):
        """The amazonaws URL path is unchanged when AWS_ENDPOINT_URL is unset."""
        env = {k: v for k, v in ENDPOINT_ENV.items() if k != "AWS_ENDPOINT_URL"}
        with patch.dict(os.environ, env):
            os.environ.pop("AWS_ENDPOINT_URL", None)
            with patch("app.utils.s3.boto3.client") as mock_client_factory:
                mock_client = Mock()
                mock_client.head_object.return_value = {"ContentLength": 1024}
                mock_client.download_file.return_value = None
                mock_client_factory.return_value = mock_client

                result = download_file_from_s3(
                    "https://test-bucket.s3.amazonaws.com/datasets/user123/data.csv"
                )

                assert result
                args = mock_client.download_file.call_args[0]
                assert args[0] == "test-bucket"
                assert args[1] == "datasets/user123/data.csv"
                _, kwargs = mock_client_factory.call_args
                assert "endpoint_url" not in kwargs
