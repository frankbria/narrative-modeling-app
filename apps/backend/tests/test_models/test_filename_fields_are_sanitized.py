"""A client filename cannot round-trip unchanged into UserData / DatasetMetadata (#585 AC4)."""

import pytest

from app.models.dataset import DatasetMetadata
from app.models.user_data import UserData

BAD = ["../../etc/passwd.csv", "a\r\nb.csv", "x" * 300 + ".csv"]


def _user_data(name: str) -> UserData:
    return UserData(
        user_id="u", filename=name, original_filename=name,
        s3_url="https://test-bucket.s3.amazonaws.com/datasets/u/k.csv",
        num_rows=1, num_columns=1, data_schema=[], file_type="csv",
    )


def _metadata(name: str) -> DatasetMetadata:
    return DatasetMetadata(
        dataset_id="d", user_id="u", filename=name, original_filename=name,
        file_type="csv", file_path="datasets/u/k.csv", file_size=1, s3_url="https://test-bucket.s3.amazonaws.com/datasets/u/k.csv",
        num_rows=1, num_columns=1,
    )


@pytest.mark.parametrize("name", BAD)
@pytest.mark.parametrize("build", [_user_data, _metadata], ids=["UserData", "DatasetMetadata"])
def test_stored_name_is_sanitised(setup_database, build, name):
    # setup_database: constructing a Beanie Document needs an initialised Beanie,
    # or the run order decides whether this file passes.
    doc = build(name)
    for value in (doc.filename, doc.original_filename):
        assert value != name
        assert "/" not in value and "\\" not in value and ".." not in value
        assert "\r" not in value and "\n" not in value
        assert len(value) <= 255


@pytest.mark.asyncio
@pytest.mark.parametrize("name", BAD)
async def test_update_route_cannot_write_a_raw_name_either(async_authorized_client, name):
    """PUT /user_data/{id} setattr()s client fields onto a loaded document; without
    validate_on_save the field validators never ran on that path."""
    doc = await _user_data("clean.csv").model_copy(update={"user_id": "test_user_123"}).insert()
    try:
        response = await async_authorized_client.put(
            f"/api/v1/user_data/{doc.id}", json={"filename": name, "original_filename": name}
        )
        assert response.status_code == 200, response.text
        # Read the raw document: Beanie re-validates on *read* too, so a model-level
        # reload would look clean even if the raw name had been written to Mongo.
        raw = await UserData.get_motor_collection().find_one({"_id": doc.id})
        for value in (raw["filename"], raw["original_filename"]):
            assert value != name
            assert "/" not in value and "\r" not in value and "\n" not in value and len(value) <= 255
    finally:
        await doc.delete()
