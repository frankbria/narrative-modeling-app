import io
import os
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError, NoCredentialsError

from app.utils.s3 import (
    MAX_DOWNLOAD_BYTES,
    allowed_bucket,
    create_s3_client,
    dataset_s3_key,
    get_file_from_s3,
    get_s3_client,
    parse_s3_url,
    resolve_validated_object,
    upload_file_to_s3,
    validate_object_key,
)


def test_create_s3_client_falls_back_to_aws_default_region(monkeypatch):
    """The boto3 client picks up AWS_DEFAULT_REGION when AWS_REGION is unset —
    the exact region mismatch that broke staging (#257)."""
    monkeypatch.delenv("AWS_REGION", raising=False)
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-central-1")
    with patch("boto3.client") as mock_boto3_client:
        create_s3_client()
    _, kwargs = mock_boto3_client.call_args
    assert kwargs["region_name"] == "eu-central-1"


@pytest.fixture
def mock_env_vars():
    """Fixture to set up mock environment variables (no custom endpoint)."""
    with patch.dict(
        os.environ,
        {
            "AWS_ACCESS_KEY_ID": "test_access_key",
            "AWS_SECRET_ACCESS_KEY": "test_secret_key",
            "AWS_BUCKET_NAME": "test_bucket",
            "AWS_REGION": "us-east-1",
        },
    ):
        # Ensure no endpoint override leaks in from the host environment
        os.environ.pop("AWS_ENDPOINT_URL", None)
        yield


@pytest.fixture
def mock_env_vars_with_endpoint():
    """Fixture with AWS_ENDPOINT_URL set (S3-compatible storage, e.g. MinIO)."""
    with patch.dict(
        os.environ,
        {
            "AWS_ACCESS_KEY_ID": "test_access_key",
            "AWS_SECRET_ACCESS_KEY": "test_secret_key",
            "AWS_BUCKET_NAME": "test_bucket",
            "AWS_REGION": "us-east-1",
            "AWS_ENDPOINT_URL": "http://localhost:9000",
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


def test_get_s3_client_with_endpoint_url(mock_env_vars_with_endpoint):
    """Test S3 client creation routes to a custom endpoint when AWS_ENDPOINT_URL is set."""
    with patch("boto3.client") as mock_boto3_client:
        mock_boto3_client.return_value = Mock()
        client = get_s3_client()

        assert client is not None
        mock_boto3_client.assert_called_once()
        args, kwargs = mock_boto3_client.call_args
        assert args == ("s3",)
        assert kwargs["aws_access_key_id"] == "test_access_key"
        assert kwargs["aws_secret_access_key"] == "test_secret_key"
        assert kwargs["region_name"] == "us-east-1"
        assert kwargs["endpoint_url"] == "http://localhost:9000"
        # Path-style addressing must be pinned for S3-compatible endpoints
        assert kwargs["config"].s3 == {"addressing_style": "path"}


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


class TestParseS3Url:
    """parse_s3_url must handle every URL shape the app persists."""

    def test_s3_scheme(self, mock_env_vars):
        assert parse_s3_url("s3://my-bucket/datasets/u1/data.csv") == (
            "my-bucket", "datasets/u1/data.csv"
        )

    def test_amazonaws_virtual_hosted(self, mock_env_vars):
        assert parse_s3_url("https://my-bucket.s3.amazonaws.com/datasets/u1/data.csv") == (
            "my-bucket", "datasets/u1/data.csv"
        )

    def test_amazonaws_presigned_query_stripped(self, mock_env_vars):
        bucket, key = parse_s3_url(
            "https://my-bucket.s3.amazonaws.com/datasets/u1/data.csv"
            "?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Expires=3600"
        )
        assert bucket == "my-bucket"
        assert key == "datasets/u1/data.csv"

    def test_endpoint_style(self, mock_env_vars_with_endpoint):
        assert parse_s3_url("http://localhost:9000/test_bucket/datasets/u1/data.csv") == (
            "test_bucket", "datasets/u1/data.csv"
        )

    def test_endpoint_style_with_query(self, mock_env_vars_with_endpoint):
        bucket, key = parse_s3_url(
            "http://localhost:9000/test_bucket/datasets/u1/data.csv?X-Amz-Expires=3600"
        )
        assert bucket == "test_bucket"
        assert key == "datasets/u1/data.csv"

    def test_unknown_https_falls_back_to_path(self, mock_env_vars):
        bucket, key = parse_s3_url("https://example.com/some/path/file.csv")
        assert bucket is None
        assert key == "some/path/file.csv"

    def test_endpoint_lookalike_host_not_matched(self, mock_env_vars_with_endpoint):
        """A host that merely starts with the endpoint string must not be
        parsed as endpoint-style (e.g. http://localhost:9000.attacker.com)."""
        bucket, key = parse_s3_url(
            "http://localhost:9000.attacker.com/real-bucket/datasets/u1/data.csv"
        )
        # Falls through to the generic http(s) path fallback — no bucket
        assert bucket is None
        assert key == "real-bucket/datasets/u1/data.csv"

    def test_missing_key_raises(self, mock_env_vars_with_endpoint):
        with pytest.raises(ValueError):
            parse_s3_url("http://localhost:9000/test_bucket")

    def test_empty_url_raises(self, mock_env_vars):
        with pytest.raises(ValueError):
            parse_s3_url("")


def test_upload_file_to_s3_endpoint_url(mock_env_vars_with_endpoint, mock_s3_client):
    """Test uploaded file URL is derived from AWS_ENDPOINT_URL when set."""
    with patch("app.utils.s3.get_s3_client", return_value=mock_s3_client):
        file_content = b"test file content"
        s3_filename = "test_file.txt"

        success, url = upload_file_to_s3(file_content, s3_filename, "text/plain")

        assert success is True
        assert url == "http://localhost:9000/test_bucket/test_file.txt"
        mock_s3_client.upload_fileobj.assert_called_once()


def test_get_file_from_s3_endpoint_url(mock_env_vars_with_endpoint, mock_s3_client):
    """Test downloading a file referenced by an endpoint-style URL (MinIO)."""
    with patch("app.utils.s3.get_s3_client", return_value=mock_s3_client):
        # #531: keys live under a tenant prefix (or the transitional legacy root shape).
        s3_url = "http://localhost:9000/test_bucket/datasets/u1/test_file.txt"
        expected_content = b"test file content"

        def mock_download_fileobj(bucket, key, file_obj):
            file_obj.write(expected_content)
            file_obj.seek(0)

        mock_s3_client.download_fileobj.side_effect = mock_download_fileobj
        mock_s3_client.head_object.return_value = {"ContentLength": len(expected_content)}

        result = get_file_from_s3(s3_url)

        assert result.getvalue() == expected_content
        mock_s3_client.download_fileobj.assert_called_once_with(
            "test_bucket", "datasets/u1/test_file.txt", result
        )


def test_get_file_from_s3_endpoint_url_missing_key(mock_env_vars_with_endpoint, mock_s3_client):
    """Test endpoint-style URL without an object key is rejected."""
    with patch("app.utils.s3.get_s3_client", return_value=mock_s3_client):
        with pytest.raises(ValueError) as exc_info:
            get_file_from_s3("http://localhost:9000/test_bucket")

        assert "Invalid S3 URL format" in str(exc_info.value)


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
        # #531: keys must sit under a tenant prefix (or be the transitional legacy
        # root shape) — a bare "test_file.txt" at the root is refused now.
        s3_url = "https://test_bucket.s3.amazonaws.com/datasets/user1/test_file.txt"
        expected_content = b"test file content"

        # Mock the download_fileobj to write content to the BytesIO object
        def mock_download_fileobj(bucket, key, file_obj):
            file_obj.write(expected_content)
            file_obj.seek(0)

        mock_s3_client.download_fileobj.side_effect = mock_download_fileobj
        mock_s3_client.head_object.return_value = {"ContentLength": len(expected_content)}

        result = get_file_from_s3(s3_url)

        assert isinstance(result, io.BytesIO)
        assert result.getvalue() == expected_content
        mock_s3_client.download_fileobj.assert_called_once_with(
            "test_bucket", "datasets/user1/test_file.txt", result
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
        s3_url = "https://test_bucket.s3.amazonaws.com/datasets/user1/test_file.txt"
        mock_s3_client.head_object.return_value = {"ContentLength": 10}
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


class TestDatasetS3Key:
    """#581: every dataset object lives under its owner's prefix.

    The strict downloader, erasure and any per-tenant lifecycle rule all key on
    ``datasets/{user_id}/``; a bare ``{uuid}.{ext}`` is invisible to all three.
    """

    UUID_RE = r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"

    def test_key_is_owner_prefixed_with_a_server_generated_name(self):
        import re

        key = dataset_s3_key("tenant_a", "sales Q3 (final).CSV")
        assert re.fullmatch(rf"datasets/tenant_a/{self.UUID_RE}\.csv", key), key
        # The client filename never reaches the key.
        assert "sales" not in key and " " not in key and "(" not in key

    def test_masked_variant_keeps_the_prefix(self):
        import re

        key = dataset_s3_key("tenant_a", "people.csv", masked=True)
        assert re.fullmatch(rf"datasets/tenant_a/masked_{self.UUID_RE}\.csv", key), key

    def test_no_extension_yields_no_trailing_dot(self):
        key = dataset_s3_key("tenant_a", "README")
        assert key.startswith("datasets/tenant_a/")
        assert not key.endswith(".")
        assert "." not in key.rsplit("/", 1)[1]

    def test_two_calls_never_collide(self):
        assert dataset_s3_key("t", "a.csv") != dataset_s3_key("t", "a.csv")

    @pytest.mark.parametrize("bad", ["", "a/b", "..", "."])
    def test_a_user_id_that_could_fold_into_another_prefix_is_refused(self, bad):
        with pytest.raises(ValueError):
            dataset_s3_key(bad, "a.csv")

    def test_traversal_in_the_filename_cannot_escape_the_prefix(self):
        key = dataset_s3_key("tenant_a", "../../etc/passwd.csv")
        assert key.startswith("datasets/tenant_a/")
        assert ".." not in key and "passwd" not in key


# --------------------------------------------------------------------------- #
# One validated download core (#531, #567)
# --------------------------------------------------------------------------- #
class TestParseS3UrlRegional:
    def test_regional_virtual_host_is_parsed(self, mock_env_vars):
        # The utils reader used to derive the bucket from the host's first label
        # for this shape; the parser handles it now so no fallback is needed.
        assert parse_s3_url("https://b.s3.us-east-1.amazonaws.com/datasets/u/f.csv") == (
            "b",
            "datasets/u/f.csv",
        )


class TestAllowedBucket:
    def test_readers_and_writers_agree_when_two_names_differ(self, monkeypatch):
        # claude-review on #621: the allowlist preferred AWS_S3_BUCKET while the
        # writers preferred AWS_BUCKET_NAME — set both, differently, and the app
        # wrote to one bucket and refused to read from it. Writers now resolve
        # through configured_bucket(), the readers' own expression.
        from app.services.s3_service import S3Service
        from app.utils.s3 import configured_bucket

        monkeypatch.setenv("AWS_S3_BUCKET", "allow")
        monkeypatch.setenv("AWS_BUCKET_NAME", "other")
        monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)  # mock mode: no client
        assert allowed_bucket() == "allow"
        assert configured_bucket() == "allow"
        assert S3Service().bucket_name == "allow"

    def test_explicit_allowlist_var_alone_is_honoured(self, monkeypatch):
        for name in ("AWS_BUCKET_NAME", "S3_BUCKET", "S3_BUCKET_NAME"):
            monkeypatch.delenv(name, raising=False)
        monkeypatch.setenv("AWS_S3_BUCKET", "allow")
        assert allowed_bucket() == "allow"

    def test_falls_back_to_the_canonical_resolver(self, monkeypatch):
        monkeypatch.delenv("AWS_S3_BUCKET", raising=False)
        monkeypatch.setenv("AWS_BUCKET_NAME", "canon")
        assert allowed_bucket() == "canon"

    def test_fails_closed_when_unconfigured(self, monkeypatch):
        for name in ("AWS_S3_BUCKET", "AWS_BUCKET_NAME", "S3_BUCKET_NAME", "S3_BUCKET"):
            monkeypatch.delenv(name, raising=False)
        with pytest.raises(ValueError, match="not configured"):
            allowed_bucket()


class TestValidateObjectKey:
    @pytest.mark.parametrize(
        "key",
        [
            "datasets/user1/file.csv",
            "transformed/user-1/out_2.parquet",
            "datasets%2Fuser1%2Ffile.csv",  # URL-encoded, decodes to a valid key
            # datasets.py stores the raw client filename — spaces, parentheses,
            # unicode — and refusing them made the app's own objects unreadable (#496).
            "datasets/user1/ds1_my data.csv",
            "datasets/user1/ds1_data (1).csv",
            "datasets/user1/ds1_r\u00e9sum\u00e9.xlsx",
            # The versioning layout, feature-builder outputs — any depth under the tenant.
            "datasets/user1/ds1/versions/v1/data.csv",
            "datasets/user1/ds1/data_1700000000.parquet",
            # ".." inside a filename is a name, not a traversal (codex review).
            "datasets/user1/ds1_experiment..csv",
            # The other namespaces the key-based reader serves (CI integration runs).
            "models/user1/model_abc/model.pkl",
            "models/user1/model_abc/evaluation_data.json",
            "batch-jobs/user1/model_abc/20260912T000000/input.csv",
            "exports/user1/file1/export.csv",
        ],
    )
    def test_accepts_the_app_namespaces(self, key):
        from urllib.parse import unquote

        assert validate_object_key(key) == unquote(key)

    @pytest.mark.parametrize(
        "key",
        [
            "datasets/../../admin/secrets.csv",
            "datasets%2F..%2F..%2Fadmin%2Fsecrets.csv",
            "/etc/passwd",
            "//root/.ssh/id_rsa",
            "unauthorized/path/file.csv",
            "datasets/file.csv",  # no tenant segment
            "datasets/user1/",  # nothing after the tenant
            "predictions/user1/x.csv",  # not a namespace the app writes
            "datasets/user 1/file.csv",  # the user_id segment stays bounded
            "datasets/user1/..",  # a ".." *segment* is traversal
            "datasets//file.csv",  # an empty segment is not a namespace
            "models/model.pkl",  # a namespace without a tenant segment
            "file.csv",
            "",
        ],
    )
    def test_refuses_traversal_absolute_and_out_of_namespace(self, key):
        with pytest.raises(ValueError):
            validate_object_key(key)

    def test_legacy_root_shape_only_when_allowed(self):
        # Exactly what #615 reconciles: (masked_){uuid}.{ext} at the bucket root.
        legacy = "masked_3fa85f64-5717-4562-b3fc-2c963f66afa6.csv"
        with pytest.raises(ValueError):
            validate_object_key(legacy)
        assert validate_object_key(legacy, allow_legacy_root=True) == legacy
        # ...and nothing else at the root, even with the allowance.
        with pytest.raises(ValueError):
            validate_object_key("report.csv", allow_legacy_root=True)
        with pytest.raises(ValueError):
            validate_object_key("../3fa85f64-5717-4562-b3fc-2c963f66afa6.csv", allow_legacy_root=True)


class TestResolveValidatedObject:
    def test_foreign_bucket_is_refused(self, mock_env_vars):
        with pytest.raises(ValueError, match="not permitted"):
            resolve_validated_object("https://victim.s3.amazonaws.com/datasets/u/f.csv")

    def test_unattributable_url_is_refused(self, mock_env_vars):
        with pytest.raises(ValueError, match="Invalid S3 URL"):
            resolve_validated_object("https://example.com/datasets/u/f.csv")

    def test_own_bucket_and_valid_key_pass(self, mock_env_vars):
        assert resolve_validated_object("s3://test_bucket/transformed/u/f.parquet") == (
            "test_bucket",
            "transformed/u/f.parquet",
        )

    def test_legacy_root_needs_the_allowance(self, mock_env_vars):
        url = "https://test_bucket.s3.amazonaws.com/3fa85f64-5717-4562-b3fc-2c963f66afa6.csv"
        with pytest.raises(ValueError):
            resolve_validated_object(url)
        assert resolve_validated_object(url, allow_legacy_root=True)[1].endswith(".csv")


class TestGetFileFromS3Validation:
    def test_root_non_uuid_key_is_refused_before_any_download(self, mock_env_vars, mock_s3_client):
        with patch("app.utils.s3.get_s3_client", return_value=mock_s3_client):
            with pytest.raises(ValueError):
                get_file_from_s3("https://test_bucket.s3.amazonaws.com/test_file.txt")
        mock_s3_client.download_fileobj.assert_not_called()

    def test_foreign_bucket_is_refused_before_any_download(self, mock_env_vars, mock_s3_client):
        with patch("app.utils.s3.get_s3_client", return_value=mock_s3_client):
            with pytest.raises(ValueError):
                get_file_from_s3("https://victim.s3.amazonaws.com/datasets/u/f.csv")
        mock_s3_client.download_fileobj.assert_not_called()

    def test_legacy_root_uuid_object_still_downloads(self, mock_env_vars, mock_s3_client):
        # Production still holds these until the operator runs #615.
        mock_s3_client.head_object.return_value = {"ContentLength": 3}
        mock_s3_client.download_fileobj.side_effect = lambda b, k, f: f.write(b"a,b")
        with patch("app.utils.s3.get_s3_client", return_value=mock_s3_client):
            out = get_file_from_s3(
                "https://test_bucket.s3.amazonaws.com/3fa85f64-5717-4562-b3fc-2c963f66afa6.csv"
            )
        assert out.getvalue() == b"a,b"

    def test_regional_url_downloads_without_the_old_fallback(self, mock_env_vars, mock_s3_client):
        mock_s3_client.head_object.return_value = {"ContentLength": 1}
        mock_s3_client.download_fileobj.side_effect = lambda b, k, f: f.write(b"x")
        with patch("app.utils.s3.get_s3_client", return_value=mock_s3_client):
            get_file_from_s3("https://test_bucket.s3.eu-west-1.amazonaws.com/datasets/u/f.csv")
        mock_s3_client.download_fileobj.assert_called_once()
        assert mock_s3_client.download_fileobj.call_args[0][:2] == ("test_bucket", "datasets/u/f.csv")

    def test_oversize_object_is_refused_before_download(self, mock_env_vars, mock_s3_client):
        mock_s3_client.head_object.return_value = {"ContentLength": MAX_DOWNLOAD_BYTES + 1}
        with patch("app.utils.s3.get_s3_client", return_value=mock_s3_client):
            with pytest.raises(ValueError, match="too large"):
                get_file_from_s3("https://test_bucket.s3.amazonaws.com/datasets/u/f.csv")
        mock_s3_client.download_fileobj.assert_not_called()


class TestGetS3ClientBucketResolution:
    def test_any_bucket_variable_name_is_enough(self, monkeypatch):
        # Column stats broke on deployments that set only S3_BUCKET_NAME because
        # this used to hard-require AWS_BUCKET_NAME (codex review).
        for name in ("AWS_BUCKET_NAME", "AWS_S3_BUCKET", "S3_BUCKET"):
            monkeypatch.delenv(name, raising=False)
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "k")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "s")
        monkeypatch.setenv("S3_BUCKET_NAME", "only-this-name")
        with patch("app.utils.s3.create_s3_client", return_value=Mock()) as make:
            assert get_s3_client() is not None
        make.assert_called_once()

    def test_no_bucket_at_all_still_yields_no_client(self, monkeypatch):
        for name in ("AWS_BUCKET_NAME", "AWS_S3_BUCKET", "S3_BUCKET", "S3_BUCKET_NAME"):
            monkeypatch.delenv(name, raising=False)
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "k")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "s")
        assert get_s3_client() is None

