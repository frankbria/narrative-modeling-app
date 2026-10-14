"""#529: the startup write-probe leaves nothing in the bucket, versioned or not.

On a versioned bucket a plain delete keeps the object as a noncurrent version and adds
a delete marker. The probe runs on every boot of every worker, so the staging bucket
held 154 of each within a month, with no current object anywhere. Against real S3
(LocalStack). Skips locally when LocalStack is down; ``CI_REQUIRE_SERVICES`` makes that
a failure.
"""
import uuid
from unittest.mock import patch

import pytest

from app.services.s3_service import S3Service

pytestmark = pytest.mark.integration


@pytest.fixture
def scratch_bucket(s3_client):
    name = f"startup-probe-{uuid.uuid4().hex[:12]}"
    s3_client.create_bucket(Bucket=name)
    yield name
    listing = s3_client.list_object_versions(Bucket=name)
    for entry in listing.get("Versions", []) + listing.get("DeleteMarkers", []):
        s3_client.delete_object(Bucket=name, Key=entry["Key"], VersionId=entry["VersionId"])
    s3_client.delete_bucket(Bucket=name)


def _probe(s3_client, bucket: str) -> None:
    service = S3Service.__new__(S3Service)  # skip __init__, which reads the environment
    service.is_mock_mode = False
    service.s3_client = s3_client
    with patch("app.services.s3_service.configured_bucket", return_value=bucket):
        service.verify_bucket_writable()


def _left_behind(s3_client, bucket: str) -> dict[str, int]:
    listing = s3_client.list_object_versions(Bucket=bucket)
    return {
        "versions": len(listing.get("Versions", [])),
        "delete_markers": len(listing.get("DeleteMarkers", [])),
    }


def test_a_versioned_bucket_holds_nothing_after_three_boots(s3_client, scratch_bucket):
    s3_client.put_bucket_versioning(Bucket=scratch_bucket, VersioningConfiguration={"Status": "Enabled"})

    for _boot in range(3):
        _probe(s3_client, scratch_bucket)

    assert _left_behind(s3_client, scratch_bucket) == {"versions": 0, "delete_markers": 0}


def test_an_unversioned_bucket_holds_nothing_either(s3_client, scratch_bucket):
    _probe(s3_client, scratch_bucket)

    assert _left_behind(s3_client, scratch_bucket) == {"versions": 0, "delete_markers": 0}
