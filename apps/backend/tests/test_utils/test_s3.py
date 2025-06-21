import pytest
import boto3
import os
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError, NoCredentialsError
import io
from app.utils.s3 import get_s3_client, upload_file_to_s3, get_file_from_s3


@pytest.fixture
def mock_env_vars():
    """Fixture to set up mock environment variables."""
    with patch.dict(
        os.environ,
        {
            "AWS_ACCESS_KEY_ID": "test_access_key",
            "AWS_SECRET_ACCESS_KEY": "test_secret_key",
            "AWS_BUCKET_NAME": "test_bucket",
            "AWS_REGION": "us-east-1",
        },
    ):
        yield


@pytest.fixture
def mock_s3_client():
    """Fixture to create a mock S3 client."""
    mock_client = Mock()
    mock_client.upload_fileobj = Mock()
    mock_client.download_fileobj = Mock()
    return mock_client


def test_get_s3_client_success(mock_env_vars):
    """Test successful S3 client creation."""
    with patch("boto3.client") as mock_boto3_client:
        mock_boto3_client.return_value = Mock()
        client = get_s3_client()

        assert client is not None
        mock_boto3_client.assert_called_once_with(
            "s3",
            aws_access_key_id="test_access_key",
            aws_secret_access_key="test_secret_key",
            region_name="us-east-1",
        )


def test_get_s3_client_missing_env_vars():
    """Test S3 client creation with missing environment variables."""
    with patch.dict(os.environ, {}, clear=True):
        client = get_s3_client()
        assert client is None


def test_get_s3_client_boto3_error():
    """Test S3 client creation when boto3 raises an error."""
    with patch.dict(
        os.environ,
        {
            "AWS_ACCESS_KEY_ID": "test_access_key",
            "AWS_SECRET_ACCESS_KEY": "test_secret_key",
            "AWS_BUCKET_NAME": "test_bucket",
            "AWS_REGION": "us-east-1",
        },
    ):
        with patch("boto3.client", side_effect=Exception("Boto3 error")):
            client = get_s3_client()
            assert client is None


def test_upload_file_to_s3_success(mock_env_vars, mock_s3_client):
    """Test successful file upload to S3."""
    with patch("app.utils.s3.get_s3_client", return_value=mock_s3_client):
        file_content = b"test file content"
        s3_filename = "test_file.txt"
        content_type = "text/plain"

        success, url = upload_file_to_s3(file_content, s3_filename, content_type)

        assert success is True
        assert url == f"https://test_bucket.s3.amazonaws.com/{s3_filename}"
        mock_s3_client.upload_fileobj.assert_called_once()

        # Verify the upload_fileobj call arguments
        # upload_fileobj is called with positional args: (file_obj, bucket, key)
        call_args = mock_s3_client.upload_fileobj.call_args
        assert call_args[0][1] == "test_bucket"  # bucket name
        assert call_args[0][2] == s3_filename    # key
        assert call_args[1]["ExtraArgs"] == {"ContentType": content_type}


def test_upload_file_to_s3_no_client(mock_env_vars):
    """Test file upload when S3 client is not available."""
    with patch("app.utils.s3.get_s3_client", return_value=None):
        file_content = b"test file content"
        s3_filename = "test_file.txt"

        success, url = upload_file_to_s3(file_content, s3_filename)

        assert success is False
        assert url is None


def test_upload_file_to_s3_no_credentials(mock_env_vars, mock_s3_client):
    """Test file upload when AWS credentials are invalid."""
    with patch("app.utils.s3.get_s3_client", return_value=mock_s3_client):
        mock_s3_client.upload_fileobj.side_effect = NoCredentialsError()

        file_content = b"test file content"
        s3_filename = "test_file.txt"

        success, url = upload_file_to_s3(file_content, s3_filename)

        assert success is False
        assert url is None


def test_upload_file_to_s3_client_error(mock_env_vars, mock_s3_client):
    """Test file upload when S3 client raises an error."""
    with patch("app.utils.s3.get_s3_client", return_value=mock_s3_client):
        mock_s3_client.upload_fileobj.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}},
            "upload_fileobj",
        )

        file_content = b"test file content"
        s3_filename = "test_file.txt"

        success, url = upload_file_to_s3(file_content, s3_filename)

        assert success is False
        assert url is None


def test_get_file_from_s3_success(mock_env_vars, mock_s3_client):
    """Test successful file download from S3."""
    with patch("app.utils.s3.get_s3_client", return_value=mock_s3_client):
        s3_url = "https://test_bucket.s3.amazonaws.com/test_file.txt"
        expected_content = b"test file content"

        # Mock the download_fileobj to write content to the BytesIO object
        def mock_download_fileobj(bucket, key, file_obj):
            file_obj.write(expected_content)
            file_obj.seek(0)

        mock_s3_client.download_fileobj.side_effect = mock_download_fileobj

        result = get_file_from_s3(s3_url)

        assert isinstance(result, io.BytesIO)
        assert result.getvalue() == expected_content
        mock_s3_client.download_fileobj.assert_called_once_with(
            "test_bucket", "test_file.txt", result
        )


def test_get_file_from_s3_no_client(mock_env_vars):
    """Test file download when S3 client is not available."""
    with patch("app.utils.s3.get_s3_client", return_value=None):
        s3_url = "https://test_bucket.s3.amazonaws.com/test_file.txt"

        with pytest.raises(Exception) as exc_info:
            get_file_from_s3(s3_url)

        assert str(exc_info.value) == "Failed to initialize S3 client"


def test_get_file_from_s3_invalid_url(mock_env_vars, mock_s3_client):
    """Test file download with an invalid S3 URL."""
    with patch("app.utils.s3.get_s3_client", return_value=mock_s3_client):
        s3_url = "invalid_url"

        with pytest.raises(ValueError) as exc_info:
            get_file_from_s3(s3_url)

        assert "Invalid S3 URL format" in str(exc_info.value)


def test_get_file_from_s3_download_error(mock_env_vars, mock_s3_client):
    """Test file download when S3 client raises an error."""
    with patch("app.utils.s3.get_s3_client", return_value=mock_s3_client):
        s3_url = "https://test_bucket.s3.amazonaws.com/test_file.txt"
        mock_s3_client.download_fileobj.side_effect = ClientError(
            {
                "Error": {
                    "Code": "NoSuchKey",
                    "Message": "The specified key does not exist.",
                }
            },
            "download_fileobj",
        )

        with pytest.raises(Exception):
            get_file_from_s3(s3_url)
