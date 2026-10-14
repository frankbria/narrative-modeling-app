"""#853: two first transformations on one dataset at the same moment (a double-click).

Both used to miss the lookup for the dataset's history and both create one, with ids
that collide inside a second; for a UI upload both created its metadata twin as well.
And each transformed the same starting file, so even one history holding both steps
would have described a file only one of them was applied to. Through the route against
real S3 (LocalStack). Skips locally when LocalStack is down; ``CI_REQUIRE_SERVICES``
makes that a failure.
"""
import asyncio
import io

import pytest

from app.models.dataset import DatasetMetadata
from app.models.transformation import TransformationConfig
from app.services.transformation_engine.data_utils import get_dataframe_from_s3
from tests.test_integration.test_charts_follow_a_transformation_localstack import (  # noqa: F401
    USER,
    client,
    real_s3_env,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

# A repeated row and padded text: each of the two steps changes something the other does not.
CSV = b"city,spend\n paris ,10\n paris ,10\n oslo ,30\nrome,40\n"


async def _apply(client, dataset_id: str, transformation_type: str) -> dict:  # noqa: F811
    applied = await client.post(
        "/api/v1/transformations/apply",
        json={"dataset_id": dataset_id, "transformation_type": transformation_type, "parameters": {}},
    )
    assert applied.status_code == 200, applied.text
    return applied.json()


async def test_two_first_applies_at_once_share_one_history_and_both_are_applied(client):  # noqa: F811
    upload = await client.post("/api/v1/upload/secure", files={"file": ("visits.csv", io.BytesIO(CSV), "text/csv")})
    dataset_id = upload.json()["file_id"]

    answers = await asyncio.gather(
        _apply(client, dataset_id, "remove_duplicates"),
        _apply(client, dataset_id, "trim_whitespace"),
    )

    assert [a["success"] for a in answers] == [True, True], answers
    twins = await DatasetMetadata.find(DatasetMetadata.user_id == USER).to_list()
    assert len(twins) == 1, "one metadata twin for the upload"
    configs = await TransformationConfig.find(TransformationConfig.user_id == USER).to_list()
    assert len(configs) == 1, "one history for the dataset"
    history = configs[0]
    assert sorted(step.transformation_type for step in history.transformation_steps) == [
        "remove_duplicates",
        "trim_whitespace",
    ]
    assert history.current_position == 1

    # The file the dataset is on has both applied: three rows, none padded.
    frame = await get_dataframe_from_s3(twins[0].s3_url)
    assert sorted(frame["city"]) == ["oslo", "paris", "rome"]
