"""#864: deleting a dataset by its upload's id deletes everything derived from it.

`DELETE /user_data/{id}` removed the `UserData` row and nothing else: the S3 object,
the metadata twin a first transformation creates (#850), its versions and their
objects, and its history all stayed, where nothing would ever find them again. The e2e
cleanup used it for every UI upload. Through the routes against real S3 (LocalStack).
Skips locally when LocalStack is down; ``CI_REQUIRE_SERVICES`` makes that a failure.
"""
import io

import pytest
from beanie import PydanticObjectId

from app.models.dataset import DatasetMetadata
from app.models.transformation import TransformationConfig
from app.models.user_data import UserData
from app.models.version import DatasetVersion
from tests.test_integration.test_charts_follow_a_transformation_localstack import (  # noqa: F401
    CSV,
    USER,
    client,
    real_s3_env,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def _objects_of(s3_client, bucket: str) -> list[str]:
    listed = s3_client.list_objects_v2(Bucket=bucket).get("Contents", [])
    return [o["Key"] for o in listed if f"/{USER}/" in o["Key"]]


async def test_deleting_a_transformed_upload_leaves_nothing_of_it(client, s3_client, real_s3_env):  # noqa: F811
    # Other suites share this bucket and this user, so the count is this test's own.
    already_there = set(_objects_of(s3_client, real_s3_env))
    upload = await client.post("/api/v1/upload/secure", files={"file": ("visits.csv", io.BytesIO(CSV), "text/csv")})
    dataset_id = upload.json()["file_id"]
    applied = await client.post(
        "/api/v1/transformations/apply",
        json={"dataset_id": dataset_id, "transformation_type": "remove_duplicates", "parameters": {}},
    )
    assert applied.json()["success"] is True, applied.text
    assert await DatasetMetadata.find(DatasetMetadata.user_id == USER).count() == 1, "precondition: a twin"
    written = set(_objects_of(s3_client, real_s3_env)) - already_there
    assert len(written) >= 3, "precondition: the upload, its version, the result"

    deleted = await client.delete(f"/api/v1/user_data/{dataset_id}")

    assert (deleted.status_code, deleted.json()) == (200, {"success": True}), deleted.text
    assert await UserData.get(PydanticObjectId(dataset_id)) is None
    assert await DatasetMetadata.find(DatasetMetadata.user_id == USER).count() == 0
    assert await DatasetVersion.find(DatasetVersion.user_id == USER).count() == 0
    assert await TransformationConfig.find(TransformationConfig.user_id == USER).count() == 0
    assert set(_objects_of(s3_client, real_s3_env)) & written == set()


async def test_another_tenants_upload_and_an_unknown_one_answer_alike(client):  # noqa: F811
    theirs = await UserData(
        user_id="someone_else", filename="t.csv", original_filename="t.csv",
        s3_url="s3://bucket/datasets/someone_else/t.csv", num_rows=1, num_columns=1, data_schema=[],
    ).insert()

    for dataset_id in (str(theirs.id), "66f0c0ffee0000000000dead"):
        refused = await client.delete(f"/api/v1/user_data/{dataset_id}")
        assert (refused.status_code, refused.json()["detail"]) == (404, "Dataset not found")

    assert await UserData.get(theirs.id) is not None


async def test_a_cascade_that_kept_the_row_asks_for_a_retry(client, monkeypatch):  # noqa: F811
    from app.api.routes import user_data as route
    from app.schemas.erasure import DeletionManifest

    mine = await UserData(
        user_id=USER, filename="m.csv", original_filename="m.csv",
        s3_url=f"s3://bucket/datasets/{USER}/m.csv", num_rows=1, num_columns=1, data_schema=[],
    ).insert()

    async def left_an_object(*_args, **_kwargs):
        return DeletionManifest(
            target_type="dataset", target_id=str(mine.id), subject_user_id=USER,
            failures=["s3 delete datasets/x: AccessDenied"],
        )

    monkeypatch.setattr(route.dataset_erasure_service, "erase_dataset", left_an_object)

    refused = await client.delete(f"/api/v1/user_data/{mine.id}")

    assert refused.status_code == 502
    assert "AccessDenied" not in refused.text


async def test_an_object_left_after_the_row_is_gone_is_not_a_retry(client, monkeypatch):  # noqa: F811
    """A residual S3 object does not keep the row (#616), and a retry would only 404,
    so the delete has happened as far as the caller can tell (codex review)."""
    from app.api.routes import user_data as route
    from app.schemas.erasure import DeletionManifest

    mine = await UserData(
        user_id=USER, filename="m.csv", original_filename="m.csv",
        s3_url=f"s3://bucket/datasets/{USER}/m.csv", num_rows=1, num_columns=1, data_schema=[],
    ).insert()

    async def deleted_the_row_but_not_an_object(*_args, **_kwargs):
        await mine.delete()
        return DeletionManifest(
            target_type="dataset", target_id=str(mine.id), subject_user_id=USER,
            failures=["s3 delete datasets/x: AccessDenied"],
        )

    monkeypatch.setattr(route.dataset_erasure_service, "erase_dataset", deleted_the_row_but_not_an_object)

    answered = await client.delete(f"/api/v1/user_data/{mine.id}")

    assert (answered.status_code, answered.json()) == (200, {"success": True})
