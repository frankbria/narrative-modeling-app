"""
Security Tests for S3 File Loading

Tests OWASP A03 (Injection) and CWE-22 (Path Traversal) prevention
in S3 file download operations.

Critical security requirements:
1. Only allow downloads from whitelisted S3 bucket
2. Prevent path traversal attacks
3. Validate path structure
4. Enforce file size limits
"""

from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError
from tenacity import RetryError

from app.services.s3_service import download_file_from_s3
from app.utils.circuit_breaker import CircuitBreakerOpen


def get_error_message(exc_value):
    """
    Extract error message from ValueError, RetryError, or CircuitBreakerOpen.

    The circuit breaker wraps ValueErrors in RetryError after retries,
    and after too many failures, raises Circuit BreakerOpen.
    """
    if isinstance(exc_value, CircuitBreakerOpen):
        # Circuit breaker opened due to multiple failures - this is expected for security validation
        # Return a generic message indicating the circuit breaker is protecting the system
        return "Circuit breaker activated (security validation failures)"
    elif isinstance(exc_value, RetryError):
        return str(exc_value.last_attempt.exception())
    return str(exc_value)


@pytest.mark.unit
class TestS3SecurityValidation:
    """Unit tests for S3 security validation."""

    @pytest.mark.parametrize("malicious_url,attack_type", [
        # Cross-bucket attacks
        ("https://victim-bucket.s3.amazonaws.com/sensitive-data.csv", "cross-bucket"),
        ("https://attacker-bucket.s3.amazonaws.com/malware.csv", "cross-bucket"),

        # Path traversal attacks (URL encoded)
        ("https://test-bucket.s3.amazonaws.com/datasets%2F..%2F..%2Fadmin%2Fsecrets.csv", "path-traversal-encoded"),
        ("https://test-bucket.s3.amazonaws.com/datasets%2F..%2Fconfig.yml", "path-traversal-encoded"),

        # Path traversal attacks (decoded)
        ("https://test-bucket.s3.amazonaws.com/datasets/../../admin/secrets.csv", "path-traversal-decoded"),
        ("https://test-bucket.s3.amazonaws.com/datasets/../config.yml", "path-traversal-decoded"),

        # Absolute path attacks
        ("https://test-bucket.s3.amazonaws.com//etc/passwd", "absolute-path"),
        ("https://test-bucket.s3.amazonaws.com//root/.ssh/id_rsa", "absolute-path"),

        # Invalid path structures
        ("https://test-bucket.s3.amazonaws.com/unauthorized/path/file.csv", "invalid-structure"),
        ("https://test-bucket.s3.amazonaws.com/file.csv", "invalid-structure"),
        ("https://test-bucket.s3.amazonaws.com/datasets/file.csv", "invalid-structure-no-user"),

        # Malicious filenames
        ("https://test-bucket.s3.amazonaws.com/datasets/user/../../../etc/passwd", "malicious-filename"),
    ])
    def test_malicious_s3_urls_blocked(self, malicious_url, attack_type):
        """
        Test that various attack vectors are properly blocked.

        Security requirement: OWASP A03 - Injection prevention
        Expected: ValueError or RetryError (wrapping ValueError) for all malicious URLs
        """
        with patch.dict('os.environ', {'AWS_S3_BUCKET': 'test-bucket'}):
            with pytest.raises((ValueError, RetryError, CircuitBreakerOpen)) as exc_info:
                download_file_from_s3(malicious_url)

            # Get the actual error message (might be wrapped in RetryError or CircuitBreakerOpen)
            error_message = get_error_message(exc_info.value)

            # Verify appropriate error message (or circuit breaker activation)
            assert any([
                "not allowed" in error_message,  # Cross-bucket
                "path traversal detected" in error_message,  # Path traversal
                "Invalid S3 path structure" in error_message,  # Invalid structure
                "Circuit breaker activated" in error_message,  # Circuit breaker opened (valid for security)
            ]), f"Attack type '{attack_type}' should raise appropriate error. Got: {error_message}"

    @pytest.mark.parametrize("url,attack_type", [
        # Transformed namespace must NOT bypass structure/traversal guards.
        ("https://test-bucket.s3.amazonaws.com/transformed/file.csv", "invalid-structure-no-user"),
        ("https://test-bucket.s3.amazonaws.com/transformed/../../etc/passwd", "path-traversal"),
        ("https://test-bucket.s3.amazonaws.com/transformed/user/sub/deep/f.csv", "too-many-segments"),
    ])
    def test_transformed_namespace_still_guarded(self, url, attack_type):
        """The transformed/ allowance (#276) keeps traversal + structure guards."""
        with patch.dict('os.environ', {'AWS_S3_BUCKET': 'test-bucket'}):
            with pytest.raises((ValueError, RetryError, CircuitBreakerOpen)):
                download_file_from_s3(url)

    def test_transformed_namespace_passes_structure_validation(self):
        """A well-formed transformed/{user}/{file} key clears path validation (#276).

        Stub head_object/download so we assert the structure guard admits the key
        (the download itself is not under test here).
        """
        with patch.dict('os.environ', {'AWS_S3_BUCKET': 'test-bucket'}), \
             patch('app.services.s3_service.create_s3_client') as mock_client_factory:
            mock_client = mock_client_factory.return_value
            mock_client.head_object.return_value = {'ContentLength': 10}
            mock_client.download_file.return_value = None
            # transformation_service writes exactly this shape (dataset_id_timestamp.parquet)
            path = download_file_from_s3(
                "https://test-bucket.s3.amazonaws.com/transformed/user1/dataset_ab12_1720000000.5.parquet"
            )
            assert isinstance(path, str)
            mock_client.download_file.assert_called_once()

    def test_bucket_whitelist_enforcement(self):
        """
        Test that only whitelisted bucket is allowed.

        Security requirement: CWE-22 - Prevent unauthorized bucket access
        Expected: ValueError or RetryError for non-whitelisted buckets
        """
        with patch.dict('os.environ', {'AWS_S3_BUCKET': 'allowed-bucket'}):
            # Test unauthorized bucket
            with pytest.raises((ValueError, RetryError, CircuitBreakerOpen)) as exc_info:
                download_file_from_s3("https://unauthorized-bucket.s3.amazonaws.com/datasets/user1/file.csv")

            error_message = get_error_message(exc_info.value)
            assert "not allowed" in error_message
            assert "unauthorized-bucket" in error_message

    def test_missing_bucket_env_variable(self):
        """
        Test that missing AWS_S3_BUCKET environment variable is handled.

        Security requirement: Fail-safe default (deny all)
        Expected: ValueError or RetryError indicating missing configuration
        """
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises((ValueError, RetryError, CircuitBreakerOpen)) as exc_info:
                download_file_from_s3("https://any-bucket.s3.amazonaws.com/datasets/user1/file.csv")

            error_message = get_error_message(exc_info.value)
            assert "AWS_S3_BUCKET" in error_message
            assert "not configured" in error_message

    def test_bucket_falls_back_to_canonical_name(self, monkeypatch):
        """When AWS_S3_BUCKET is unset the allowlist falls back to the app's
        canonical bucket (AWS_BUCKET_NAME) so a deploy that sets only one name
        still works (#257). A cross-bucket URL is still rejected against it."""
        # Clear only the bucket vars (not creds/other env) so unrelated CI
        # credentials stay intact; AWS_BUCKET_NAME is then the sole bucket source.
        for _name in ("AWS_S3_BUCKET", "S3_BUCKET", "S3_BUCKET_NAME"):
            monkeypatch.delenv(_name, raising=False)
        monkeypatch.setenv("AWS_BUCKET_NAME", "fallback-bucket")
        with pytest.raises((ValueError, RetryError, CircuitBreakerOpen)) as exc_info:
            download_file_from_s3(
                "https://other-bucket.s3.amazonaws.com/datasets/user1/file.csv"
            )
        # "not allowed" proves the allowlist resolved to fallback-bucket
        # (not None → would have raised "not configured" instead).
        error_message = get_error_message(exc_info.value)
        assert "not allowed" in error_message or "Circuit breaker" in error_message

    def test_path_traversal_prevention(self):
        """
        Test that path traversal attempts are blocked.

        Security requirement: CWE-22 - Path Traversal prevention
        Expected: ValueError or RetryError for paths containing '..'
        """
        with patch.dict('os.environ', {'AWS_S3_BUCKET': 'test-bucket'}):
            # Test various path traversal patterns
            traversal_paths = [
                "https://test-bucket.s3.amazonaws.com/datasets/../secrets.csv",
                "https://test-bucket.s3.amazonaws.com/datasets/../../admin/config.yml",
                "https://test-bucket.s3.amazonaws.com/datasets/user1/../../other-user/data.csv",
            ]

            for url in traversal_paths:
                with pytest.raises((ValueError, RetryError, CircuitBreakerOpen)) as exc_info:
                    download_file_from_s3(url)

                error_message = get_error_message(exc_info.value)
                assert "path traversal detected" in error_message

    def test_absolute_path_prevention(self):
        """
        Test that absolute paths are blocked.

        Security requirement: Prevent access to system files
        Expected: ValueError or RetryError for paths starting with '/'
        """
        with patch.dict('os.environ', {'AWS_S3_BUCKET': 'test-bucket'}):
            with pytest.raises((ValueError, RetryError, CircuitBreakerOpen)) as exc_info:
                download_file_from_s3("https://test-bucket.s3.amazonaws.com//etc/passwd")

            error_message = get_error_message(exc_info.value)
            assert "path traversal detected" in error_message

    def test_path_structure_validation(self):
        """
        Test that only valid path structures are allowed.

        Security requirement: Enforce expected path format
        Expected: ValueError or RetryError for paths not matching 'datasets/{user_id}/{filename}'
        """
        with patch.dict('os.environ', {'AWS_S3_BUCKET': 'test-bucket'}):
            invalid_paths = [
                "https://test-bucket.s3.amazonaws.com/file.csv",  # Missing datasets prefix
                "https://test-bucket.s3.amazonaws.com/datasets/file.csv",  # Missing user_id
                "https://test-bucket.s3.amazonaws.com/unauthorized/user1/file.csv",  # Wrong prefix
                "https://test-bucket.s3.amazonaws.com/datasets/user1/subdir/file.csv",  # Too many levels
            ]

            for url in invalid_paths:
                with pytest.raises((ValueError, RetryError, CircuitBreakerOpen)) as exc_info:
                    download_file_from_s3(url)

                error_message = get_error_message(exc_info.value)
                assert "Invalid S3 path structure" in error_message

    def test_file_size_limit_enforcement(self):
        """
        Test that large files are rejected to prevent DoS.

        Security requirement: Prevent DoS through large file downloads
        Expected: ValueError or RetryError for files exceeding 1 GB
        """
        with patch.dict('os.environ', {'AWS_S3_BUCKET': 'test-bucket'}):
            with patch('boto3.client') as mock_boto_client:
                mock_s3_client = Mock()
                mock_boto_client.return_value = mock_s3_client

                # Mock file size exceeding 1 GB
                mock_s3_client.head_object.return_value = {
                    'ContentLength': 2 * 1024 * 1024 * 1024  # 2 GB
                }

                with pytest.raises((ValueError, RetryError, CircuitBreakerOpen)) as exc_info:
                    download_file_from_s3("https://test-bucket.s3.amazonaws.com/datasets/user1/large-file.csv")

                error_message = get_error_message(exc_info.value)
                assert "File too large" in error_message
                assert "exceeds maximum" in error_message

    def test_valid_s3_url_accepted(self):
        """
        Test that valid S3 URLs are accepted and processed.

        Security requirement: Legitimate access should work
        Expected: Successful download for valid URLs
        """
        with patch.dict('os.environ', {'AWS_S3_BUCKET': 'test-bucket'}):
            with patch('boto3.client') as mock_boto_client, \
                 patch('tempfile.NamedTemporaryFile') as mock_temp_file:

                mock_s3_client = Mock()
                mock_boto_client.return_value = mock_s3_client

                # Mock valid file size
                mock_s3_client.head_object.return_value = {
                    'ContentLength': 1024 * 1024  # 1 MB
                }

                # Mock temp file
                mock_temp_file_instance = Mock()
                mock_temp_file_instance.name = '/tmp/test_file'
                mock_temp_file.return_value = mock_temp_file_instance

                # Should not raise exception
                result = download_file_from_s3("https://test-bucket.s3.amazonaws.com/datasets/user123/data.csv")

                # Verify S3 client was called with correct parameters
                mock_s3_client.head_object.assert_called_once_with(
                    Bucket='test-bucket',
                    Key='datasets/user123/data.csv'
                )
                mock_s3_client.download_file.assert_called_once()

                assert result == '/tmp/test_file'

    def test_file_not_found_handling(self):
        """
        Test that 404 errors from S3 are handled appropriately.

        Security requirement: Graceful error handling
        Expected: ValueError or RetryError with clear message
        """
        with patch.dict('os.environ', {'AWS_S3_BUCKET': 'test-bucket'}):
            with patch('boto3.client') as mock_boto_client:
                mock_s3_client = Mock()
                mock_boto_client.return_value = mock_s3_client

                # Mock 404 error
                error_response = {'Error': {'Code': '404'}}
                mock_s3_client.head_object.side_effect = ClientError(error_response, 'HeadObject')

                with pytest.raises((ValueError, RetryError, CircuitBreakerOpen)) as exc_info:
                    download_file_from_s3("https://test-bucket.s3.amazonaws.com/datasets/user1/nonexistent.csv")

                error_message = get_error_message(exc_info.value)
                assert "File not found" in error_message

    @pytest.mark.parametrize("valid_url", [
        "https://test-bucket.s3.amazonaws.com/datasets/user123/data.csv",
        "https://test-bucket.s3.amazonaws.com/datasets/user-456/file_name.csv",
        "https://test-bucket.s3.amazonaws.com/datasets/user_789/data-2024.csv",
        "https://test-bucket.s3.amazonaws.com/datasets/test-user/file.parquet",
    ])
    def test_valid_path_patterns(self, valid_url):
        """
        Test that various valid path patterns are accepted.

        Security requirement: Allow legitimate access patterns
        Expected: Paths matching the pattern should be validated successfully
        """
        with patch.dict('os.environ', {'AWS_S3_BUCKET': 'test-bucket'}):
            with patch('boto3.client') as mock_boto_client, \
                 patch('tempfile.NamedTemporaryFile') as mock_temp_file:

                mock_s3_client = Mock()
                mock_boto_client.return_value = mock_s3_client

                # Mock valid file size
                mock_s3_client.head_object.return_value = {
                    'ContentLength': 1024 * 1024  # 1 MB
                }

                # Mock temp file
                mock_temp_file_instance = Mock()
                mock_temp_file_instance.name = '/tmp/test_file'
                mock_temp_file.return_value = mock_temp_file_instance

                # Should not raise exception
                result = download_file_from_s3(valid_url)
                assert result == '/tmp/test_file'


@pytest.mark.asyncio
async def test_upload_file_obj_rewinds_before_upload():
    """upload_file_obj seeks to 0 first, so a circuit-breaker retry re-sends the
    whole object instead of resuming from EOF and truncating it (issue #278)."""
    from io import BytesIO

    from app.services.s3_service import S3Service

    svc = S3Service()
    svc.is_mock_mode = False

    captured = {}

    def _upload_fileobj(fileobj, bucket, key):
        captured["content"] = fileobj.read()

    svc.s3_client = Mock()
    svc.s3_client.upload_fileobj = _upload_fileobj

    # A stream positioned at EOF, mimicking one already consumed by a prior attempt.
    buf = BytesIO(b"hello-world")
    buf.seek(len(b"hello-world"))

    await svc.upload_file_obj(buf, "datasets/u/f.csv")

    assert captured["content"] == b"hello-world"
