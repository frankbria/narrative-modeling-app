"""#893: content deduplication in `create_transformation_version`, on real documents.

A result whose bytes the caller already has as a version of the dataset is not stored
again: the existing version is returned, carrying the new description, and the lineage
row records the transformation from the parent to it. The match is the caller's own
(#447). Only the S3 put is stubbed; the documents and their queries are real.
"""

from unittest.mock import patch

import pytest

from app.models.dataset import DatasetMetadata
from app.models.version import DatasetVersion, TransformationLineage
from app.services.versioning_service import VersioningService

pytestmark = pytest.mark.asyncio

USER = "u893"
OTHER = "someone_else"
RESULT = b"id,score\n1,10\n2,20\n"


def _dataset() -> DatasetMetadata:
    return DatasetMetadata(
        user_id=USER, dataset_id="d893", filename="d.csv", original_filename="d.csv", file_type="csv",
        file_path=f"datasets/{USER}/d893.csv", s3_url=f"s3://bucket/datasets/{USER}/d893.csv",
        num_rows=2, num_columns=2,
    )


async def _version(version_id: str, number: int, content: bytes, user_id: str = USER) -> DatasetVersion:
    return await DatasetVersion(
        version_id=version_id, dataset_id="d893", version_number=number, user_id=user_id,
        content_hash=DatasetVersion.compute_content_hash(content), file_size=len(content),
        file_path=f"datasets/{user_id}/d893/versions/{version_id}/data.parquet",
        s3_url=f"s3://bucket/datasets/{user_id}/d893/versions/{version_id}/data.parquet",
        num_rows=2, num_columns=2, schema_hash="schema", created_by=user_id,
    ).insert()


async def _derive(service: VersioningService, description: str) -> DatasetVersion:
    version, _ = await service.create_transformation_version(
        parent_version_id="v_upload", transformed_content=RESULT, transformation_steps=[],
        dataset_metadata=_dataset(), user_id=USER, description=description,
    )
    return version


@pytest.fixture
async def service(setup_database):
    await _version("v_upload", 1, b"id,score\n1,\n2,20\n")
    service = VersioningService()
    with patch.object(
        service, "_upload_version", side_effect=lambda key, *_: (f"{key}/data.parquet", f"s3://bucket/{key}/data.parquet")
    ) as put:
        service.put = put
        yield service


async def test_the_same_result_twice_is_one_version_carrying_the_latest_description(service):
    first = await _derive(service, "fill the blank")
    again = await _derive(service, "fill the blank, again")

    assert again.version_id == first.version_id
    assert service.put.call_count == 1, "the second result was not stored again"
    assert await DatasetVersion.find(DatasetVersion.dataset_id == "d893").count() == 2
    assert (await DatasetVersion.find_one(DatasetVersion.version_id == first.version_id)).description == (
        "fill the blank, again"
    )
    links = await TransformationLineage.find(TransformationLineage.child_version_id == first.version_id).to_list()
    assert [(link.parent_version_id, link.child_version_id) for link in links] == [
        ("v_upload", first.version_id),
        ("v_upload", first.version_id),
    ], "each transformation is recorded from its parent, never from the version to itself"


async def test_another_tenants_version_of_the_same_bytes_is_never_the_match(service):
    """Found reviewing #447: the lookup once had no owner predicate, so it returned the
    other tenant's row and wrote the caller's description onto it."""
    theirs = await _version("v_theirs", 7, RESULT, user_id=OTHER)

    mine = await _derive(service, "mine")

    assert (mine.version_id, mine.user_id) != (theirs.version_id, OTHER)
    assert mine.user_id == USER
    assert (await DatasetVersion.find_one(DatasetVersion.version_id == "v_theirs")).description is None
