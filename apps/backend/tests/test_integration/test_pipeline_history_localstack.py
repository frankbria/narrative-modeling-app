"""#851: an edit made by a pipeline is in the history, and undo never discards an edit
the history does not list.

`POST /transformations/pipeline/apply` moved the dataset with no history step or
version. An undo afterwards restored the version of an earlier step, so the pipeline's
work vanished while the history had never shown it. Real documents, real versions in S3
(LocalStack), the real routes.
"""
import io

import pytest

from tests.test_integration import (
    test_transformation_first_apply_localstack as first_apply,
)
from tests.test_integration import (
    test_transformation_history_localstack as history,
)

client = first_apply.client
real_s3_env = first_apply.real_s3_env

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

CSV = b"id,name,score\n1, alice ,10\n2,bob,\n3,carol,30\n3,carol,30\n"
PIPELINE = [
    {"type": "trim_whitespace", "parameters": {"columns": ["name"]}},
    {"type": "fill_missing", "parameters": {"columns": ["score"], "method": "mean"}},
]


async def _upload_and_dedupe(client) -> str:
    upload = await client.post(
        "/api/v1/datasets/upload", files={"file": ("d.csv", io.BytesIO(CSV), "text/csv")}
    )
    assert upload.status_code in (200, 201), upload.text
    dataset_id = upload.json()["dataset_id"]
    applied = await client.post(
        "/api/v1/transformations/apply",
        json={"dataset_id": dataset_id, "transformation_type": "remove_duplicates", "parameters": {}},
    )
    assert applied.status_code == 200 and applied.json()["success"] is True, applied.text
    return dataset_id


async def _history(client, dataset_id: str) -> dict:
    listing = await client.get(f"/api/v1/transformations/datasets/{dataset_id}/history")
    assert listing.status_code == 200, listing.text
    return listing.json()


async def _undone(client, dataset_id: str):
    """Undo one step; the dataset's current file, read the way training reads it."""
    _, twin = await history._undo(client, dataset_id)
    return await history._read_as_a_training_stage_does(twin)


async def test_undo_after_a_pipeline_walks_back_through_its_steps(client, real_s3_env):
    dataset_id = await _upload_and_dedupe(client)

    applied = await client.post(
        "/api/v1/transformations/pipeline/apply",
        json={"dataset_id": dataset_id, "transformations": PIPELINE},
    )
    assert applied.status_code == 200 and applied.json()["success"] is True, applied.text

    listing = await _history(client, dataset_id)
    assert [h["transformation_type"] for h in listing["history"]] == [
        "remove_duplicates", "trim_whitespace", "fill_missing",
    ]
    assert listing["current_position"] == 2

    # One step back: the fill is gone, the trim (the pipeline's first step) is kept.
    frame = await _undone(client, dataset_id)
    assert frame["score"].isna().sum() == 1 and list(frame["name"]) == ["alice", "bob", "carol"]

    # Another: the trim is gone too, the de-duplication from before the pipeline is kept.
    frame = await _undone(client, dataset_id)
    assert list(frame["name"]) == [" alice ", "bob", "carol"]
    assert (await _history(client, dataset_id))["current_position"] == 0


async def _bulk_fill(client, dataset_id: str) -> None:
    """A bulk transformation, run to completion: it moves the dataset and records no step."""
    import asyncio

    base = f"/api/v1/transformations/datasets/{dataset_id}"
    job = await client.post(f"{base}/bulk-apply", json={
        "selected_columns": ["score"], "transformation_type": "fill_missing",
        "global_parameters": {"method": "mean"},
    })
    assert job.status_code == 200, job.text
    for _ in range(200):
        status = (await client.get(f"{base}/bulk-jobs/{job.json()['job_id']}")).json()["status"]
        if status not in ("pending", "running"):
            break
        await asyncio.sleep(0.05)
    assert status == "completed", status


async def test_undo_stops_at_an_edit_the_history_does_not_list(client, real_s3_env):
    """Bulk transformations, data-issue fixes and a feature column added in place all move
    the dataset through `record_new_file` without a step. A bulk fill is that move here."""
    from app.models.dataset import DatasetMetadata

    dataset_id = await _upload_and_dedupe(client)
    piped = await client.post(
        "/api/v1/transformations/pipeline/apply",
        json={"dataset_id": dataset_id, "transformations": PIPELINE[:1]},
    )
    assert piped.json()["success"] is True, piped.text

    await _bulk_fill(client, dataset_id)
    edited = (await DatasetMetadata.find_one(DatasetMetadata.dataset_id == dataset_id)).s3_url

    listing = await _history(client, dataset_id)
    assert (listing["current_position"], listing["can_undo"], listing["can_redo"]) == (1, False, False)
    undo = await client.post(f"/api/v1/transformations/datasets/{dataset_id}/history/undo")
    assert undo.status_code == 400 and "not in this history" in undo.text, undo.text
    jump = await client.post(
        f"/api/v1/transformations/datasets/{dataset_id}/history/jump", params={"position": 0}
    )
    assert jump.status_code == 400 and "not in this history" in jump.text, jump.text
    current = await DatasetMetadata.find_one(DatasetMetadata.dataset_id == dataset_id)
    assert current.s3_url == edited, "the bulk fill must still be the dataset's current file"

    # A step recorded after the edit can be undone, back to the edit and no further.
    again = await client.post(
        "/api/v1/transformations/apply",
        json={"dataset_id": dataset_id, "transformation_type": "drop_missing", "parameters": {"columns": ["name"]}},
    )
    assert again.json()["success"] is True, again.text
    assert (await _history(client, dataset_id))["can_undo"] is False, "the only earlier steps predate the edit"
