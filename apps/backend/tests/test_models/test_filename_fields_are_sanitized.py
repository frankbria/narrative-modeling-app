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
def test_stored_name_is_sanitised(build, name):
    doc = build(name)
    for value in (doc.filename, doc.original_filename):
        assert value != name
        assert "/" not in value and "\\" not in value and ".." not in value
        assert "\r" not in value and "\n" not in value
        assert len(value) <= 255
