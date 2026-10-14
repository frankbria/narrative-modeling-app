"""#1022: an undo that lands while an apply is running waits for it.

Only an apply took the dataset's lease (#853). An undo arriving mid-apply moved the
dataset back, then the apply wrote its result on the file it had read before the undo,
and the history listed a step over a file it was not applied to. Through the routes
against real S3 (LocalStack); the apply's read is slowed so the undo provably lands
while it runs. Skips locally when LocalStack is down; ``CI_REQUIRE_SERVICES`` makes that
a failure.
"""
import asyncio
import io

import pytest

from app.models.dataset import DatasetMetadata
from app.models.transformation import TransformationConfig
from app.services.transformation_engine import data_utils
from tests.test_integration.test_charts_follow_a_transformation_localstack import (  # noqa: F401
    USER,
    client,
    real_s3_env,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

# A repeated row and padded text: each of the two steps changes something the other does not.
CSV = b"city,spend\n paris ,10\n paris ,10\n oslo ,30\nrome,40\n"
#: The cities each history describes, applied to CSV in order.
EXPECTED = {
    ("remove_duplicates",): [" oslo ", " paris ", "rome"],
    ("trim_whitespace",): ["oslo", "paris", "paris", "rome"],
    ("remove_duplicates", "trim_whitespace"): ["oslo", "paris", "rome"],
}


async def _apply(client, dataset_id: str, transformation_type: str) -> dict:  # noqa: F811
    applied = await client.post(
        "/api/v1/transformations/apply",
        json={"dataset_id": dataset_id, "transformation_type": transformation_type, "parameters": {}},
    )
    assert applied.status_code == 200, applied.text
    return applied.json()


async def test_an_undo_during_an_apply_leaves_the_file_the_history_describes(client, monkeypatch):  # noqa: F811
    read = data_utils.get_dataframe_from_s3
    upload = await client.post("/api/v1/upload/secure", files={"file": ("visits.csv", io.BytesIO(CSV), "text/csv")})
    dataset_id = upload.json()["file_id"]
    assert (await _apply(client, dataset_id, "remove_duplicates"))["success"] is True

    async def slow_read(*args, **kwargs):
        frame = await read(*args, **kwargs)
        await asyncio.sleep(1.0)  # the undo below arrives now
        return frame

    monkeypatch.setattr(data_utils, "get_dataframe_from_s3", slow_read)
    apply = asyncio.create_task(_apply(client, dataset_id, "trim_whitespace"))
    await asyncio.sleep(0.3)
    undo = await client.post(f"/api/v1/transformations/datasets/{dataset_id}/history/undo")
    applied = await apply

    assert applied["success"] is True and undo.status_code == 200, (applied, undo.text)
    history = await TransformationConfig.find_one(TransformationConfig.user_id == USER)
    listed = tuple(step.transformation_type for step in history.transformation_steps[: history.current_position + 1])
    twin = await DatasetMetadata.find_one(DatasetMetadata.user_id == USER)
    frame = await read(twin.s3_url)
    assert sorted(frame["city"]) == EXPECTED[listed], f"the history says {listed}"
    assert listed == ("remove_duplicates",), "the undo ran after the apply, and took its step back"
