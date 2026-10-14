"""#781: the storage ceiling sums `file_size`, and a dataset's `file_size` is the size
of the file it is on now.

It used to stay the upload's size however a transformation changed the dataset, and
versions were not counted at all, so a tenant's stored bytes could grow without the
ceiling moving. Through the routes against real S3 (LocalStack): the sizes asserted are
the objects' own. Skips locally when LocalStack is down; ``CI_REQUIRE_SERVICES`` makes
that a failure.
"""
import io

import pytest
from beanie import PydanticObjectId

from app.billing import storage
from app.models.dataset import DatasetMetadata
from app.models.user_data import UserData
from app.models.version import DatasetVersion
from app.utils.s3 import parse_s3_url
from tests.test_integration.test_charts_follow_a_transformation_localstack import (  # noqa: F401
    CSV,
    USER,
    client,
    real_s3_env,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

HISTORY = "/api/v1/transformations/datasets/{}/history"


def _stored_size(s3_client, bucket: str, url: str) -> int:
    return s3_client.head_object(Bucket=bucket, Key=parse_s3_url(url)[1])["ContentLength"]


async def test_a_transformation_and_an_undo_keep_the_recorded_size_true(client, s3_client, real_s3_env):  # noqa: F811
    upload = await client.post("/api/v1/upload/secure", files={"file": ("visits.csv", io.BytesIO(CSV), "text/csv")})
    dataset_id = upload.json()["file_id"]
    uploaded = await UserData.get(PydanticObjectId(dataset_id))
    assert uploaded.file_size == len(CSV)

    applied = await client.post(
        "/api/v1/transformations/apply",
        json={"dataset_id": dataset_id, "transformation_type": "remove_duplicates", "parameters": {}},
    )
    assert applied.json()["success"] is True, applied.text

    moved = await UserData.get(PydanticObjectId(dataset_id))
    assert moved.s3_url != uploaded.s3_url
    on_disk = _stored_size(s3_client, real_s3_env, moved.s3_url)
    assert moved.file_size == on_disk != len(CSV)
    twin = await DatasetMetadata.find_one({"user_id": USER, "s3_url": moved.s3_url})
    assert twin.file_size == on_disk

    # The ceiling's sum: the file the dataset is on, plus every version written for it.
    versions = await DatasetVersion.find(DatasetVersion.user_id == USER).to_list()
    assert len(versions) == 2, "the base version and the step's"
    assert await storage.stored_bytes(USER) == on_disk + sum(v.file_size for v in versions)
    for version in versions:
        assert version.file_size == _stored_size(s3_client, real_s3_env, version.s3_url)

    undone = await client.post(HISTORY.format(dataset_id) + "/undo")
    assert undone.status_code == 200, undone.text

    back = await UserData.get(PydanticObjectId(dataset_id))
    assert back.file_size == _stored_size(s3_client, real_s3_env, back.s3_url) != on_disk
    # The dataset now sits on the base version's own object, which is counted once.
    assert back.s3_url in {v.s3_url for v in versions}
    assert await storage.stored_bytes(USER) == sum(v.file_size for v in versions)
