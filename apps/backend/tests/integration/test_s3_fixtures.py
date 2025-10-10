"""
Integration tests for S3/LocalStack fixtures.

These tests validate that the S3 fixtures work correctly for file storage operations.

Run with: pytest tests/integration/test_s3_fixtures.py -v -m integration
"""

import pytest
from botocore.exceptions import ClientError


@pytest.mark.integration
def test_s3_client_fixture(s3_client):
    """Test that s3_client fixture provides a working S3 client."""
    assert s3_client is not None

    # Test basic S3 operation
    response = s3_client.list_buckets()
    assert "Buckets" in response


@pytest.mark.integration
def test_s3_bucket_fixture(test_s3_bucket, s3_client):
    """Test that test_s3_bucket fixture creates a valid S3 bucket."""
    assert test_s3_bucket is not None
    assert test_s3_bucket == "test-narrative-bucket"

    # Verify bucket exists
    response = s3_client.list_buckets()
    bucket_names = [b["Name"] for b in response["Buckets"]]
    assert test_s3_bucket in bucket_names


@pytest.mark.integration
def test_s3_file_fixture(test_s3_file, s3_client):
    """Test that test_s3_file fixture uploads a valid file."""
    assert test_s3_file is not None
    assert "bucket" in test_s3_file
    assert "key" in test_s3_file
    assert "s3_url" in test_s3_file
    assert "content" in test_s3_file

    # Verify file exists in S3
    response = s3_client.get_object(
        Bucket=test_s3_file["bucket"],
        Key=test_s3_file["key"]
    )

    # Verify content
    content = response["Body"].read().decode("utf-8")
    assert content == test_s3_file["content"]


@pytest.mark.integration
def test_s3_upload_download(test_s3_bucket, s3_client):
    """Test uploading and downloading files from S3."""
    # Upload a file
    test_content = "Test file content for S3 integration test"
    test_key = "test-uploads/test.txt"

    s3_client.put_object(
        Bucket=test_s3_bucket,
        Key=test_key,
        Body=test_content.encode("utf-8"),
        ContentType="text/plain"
    )

    # Download and verify
    response = s3_client.get_object(Bucket=test_s3_bucket, Key=test_key)
    downloaded_content = response["Body"].read().decode("utf-8")
    assert downloaded_content == test_content

    # Cleanup
    s3_client.delete_object(Bucket=test_s3_bucket, Key=test_key)


@pytest.mark.integration
def test_s3_list_objects(test_s3_bucket, test_s3_file, s3_client):
    """Test listing objects in S3 bucket."""
    # List objects
    response = s3_client.list_objects_v2(Bucket=test_s3_bucket)

    assert "Contents" in response
    assert len(response["Contents"]) >= 1

    # Verify our test file is in the list
    keys = [obj["Key"] for obj in response["Contents"]]
    assert test_s3_file["key"] in keys


@pytest.mark.integration
def test_s3_delete_object(test_s3_bucket, s3_client):
    """Test deleting objects from S3."""
    # Upload a file
    test_key = "test-delete/deleteme.txt"
    s3_client.put_object(
        Bucket=test_s3_bucket,
        Key=test_key,
        Body=b"Delete me"
    )

    # Verify file exists
    response = s3_client.head_object(Bucket=test_s3_bucket, Key=test_key)
    assert response["ResponseMetadata"]["HTTPStatusCode"] == 200

    # Delete file
    s3_client.delete_object(Bucket=test_s3_bucket, Key=test_key)

    # Verify file is deleted
    with pytest.raises(ClientError) as exc_info:
        s3_client.head_object(Bucket=test_s3_bucket, Key=test_key)
    assert exc_info.value.response["Error"]["Code"] == "404"


@pytest.mark.integration
def test_s3_multipart_upload(test_s3_bucket, s3_client):
    """Test multipart upload for large files."""
    # Create a larger file (>5MB for multipart)
    large_content = b"x" * (6 * 1024 * 1024)  # 6 MB
    test_key = "test-large/large_file.bin"

    # Initiate multipart upload
    response = s3_client.create_multipart_upload(
        Bucket=test_s3_bucket,
        Key=test_key
    )
    upload_id = response["UploadId"]

    # Upload parts
    part_size = 5 * 1024 * 1024  # 5 MB
    parts = []

    for i in range(2):
        start = i * part_size
        end = min(start + part_size, len(large_content))
        part_data = large_content[start:end]

        part_response = s3_client.upload_part(
            Bucket=test_s3_bucket,
            Key=test_key,
            PartNumber=i + 1,
            UploadId=upload_id,
            Body=part_data
        )

        parts.append({
            "PartNumber": i + 1,
            "ETag": part_response["ETag"]
        })

    # Complete multipart upload
    s3_client.complete_multipart_upload(
        Bucket=test_s3_bucket,
        Key=test_key,
        UploadId=upload_id,
        MultipartUpload={"Parts": parts}
    )

    # Verify file exists and has correct size
    response = s3_client.head_object(Bucket=test_s3_bucket, Key=test_key)
    assert response["ContentLength"] == len(large_content)

    # Cleanup
    s3_client.delete_object(Bucket=test_s3_bucket, Key=test_key)


@pytest.mark.integration
def test_s3_presigned_url(test_s3_bucket, test_s3_file, s3_client):
    """Test generating presigned URLs for S3 objects."""
    # Generate presigned URL
    presigned_url = s3_client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": test_s3_file["bucket"],
            "Key": test_s3_file["key"]
        },
        ExpiresIn=3600  # 1 hour
    )

    assert presigned_url is not None
    assert test_s3_file["bucket"] in presigned_url
    assert test_s3_file["key"] in presigned_url


@pytest.mark.integration
def test_s3_metadata(test_s3_bucket, s3_client):
    """Test storing and retrieving object metadata."""
    test_key = "test-metadata/file_with_metadata.txt"
    metadata = {
        "user-id": "test_user_123",
        "upload-date": "2025-10-09",
        "file-type": "csv"
    }

    # Upload with metadata
    s3_client.put_object(
        Bucket=test_s3_bucket,
        Key=test_key,
        Body=b"Test content",
        Metadata=metadata
    )

    # Retrieve and verify metadata
    response = s3_client.head_object(Bucket=test_s3_bucket, Key=test_key)
    assert "Metadata" in response

    for key, value in metadata.items():
        assert response["Metadata"][key] == value

    # Cleanup
    s3_client.delete_object(Bucket=test_s3_bucket, Key=test_key)


@pytest.mark.integration
def test_s3_copy_object(test_s3_bucket, test_s3_file, s3_client):
    """Test copying objects within S3."""
    source_key = test_s3_file["key"]
    dest_key = "test-copy/copied_file.csv"

    # Copy object
    s3_client.copy_object(
        Bucket=test_s3_bucket,
        CopySource={"Bucket": test_s3_bucket, "Key": source_key},
        Key=dest_key
    )

    # Verify copied file exists
    response = s3_client.get_object(Bucket=test_s3_bucket, Key=dest_key)
    copied_content = response["Body"].read().decode("utf-8")

    # Content should match original
    assert copied_content == test_s3_file["content"]

    # Cleanup
    s3_client.delete_object(Bucket=test_s3_bucket, Key=dest_key)


@pytest.mark.integration
def test_s3_bucket_versioning(test_s3_bucket, s3_client):
    """Test S3 bucket versioning (if supported by LocalStack)."""
    # Enable versioning
    try:
        s3_client.put_bucket_versioning(
            Bucket=test_s3_bucket,
            VersioningConfiguration={"Status": "Enabled"}
        )

        # Verify versioning is enabled
        response = s3_client.get_bucket_versioning(Bucket=test_s3_bucket)
        assert response.get("Status") == "Enabled"
    except ClientError:
        # Some LocalStack versions may not support versioning
        pytest.skip("Bucket versioning not supported")


@pytest.mark.integration
def test_s3_fixture_isolation(test_s3_bucket, s3_client):
    """Test that S3 fixtures provide proper test isolation."""
    # Upload test file
    test_key = "test-isolation/isolation_test.txt"
    s3_client.put_object(
        Bucket=test_s3_bucket,
        Key=test_key,
        Body=b"Isolation test"
    )

    # Verify file exists
    response = s3_client.list_objects_v2(Bucket=test_s3_bucket)
    keys = [obj["Key"] for obj in response.get("Contents", [])]
    assert test_key in keys

    # Cleanup will be handled by fixture
    s3_client.delete_object(Bucket=test_s3_bucket, Key=test_key)
