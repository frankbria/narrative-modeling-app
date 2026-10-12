"""#962: the first transformation on a dataset can be undone, and redone.

The history had no position for "the dataset before any step", so undo worked from the
second step back to the first and never further: a single step could only be taken back
by uploading the file again. Through the routes against real S3 (LocalStack); the box
plot's median says which file the dataset is at (1000 as uploaded, 10 once the duplicate
rows are removed). Skips locally when LocalStack is down; ``CI_REQUIRE_SERVICES`` makes
that a failure.
"""
import asyncio
import io

import pytest

from tests.test_integration.test_charts_follow_a_transformation_localstack import (  # noqa: F401
    CSV,
    client,
    real_s3_env,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

HISTORY = "/api/v1/transformations/datasets/{}/history"


async def _median(client, dataset_id: str) -> float:  # noqa: F811
    box = await client.get(f"/api/v1/visualizations/boxplot/{dataset_id}/spend")
    assert box.status_code == 200, box.text
    return box.json()["median"]


async def _one_step(client) -> str:  # noqa: F811
    upload = await client.post("/api/v1/upload/secure", files={"file": ("visits.csv", io.BytesIO(CSV), "text/csv")})
    dataset_id = upload.json()["file_id"]
    applied = await client.post(
        "/api/v1/transformations/apply",
        json={"dataset_id": dataset_id, "transformation_type": "remove_duplicates", "parameters": {}},
    )
    assert applied.json()["success"] is True, applied.text
    return dataset_id


async def test_one_step_can_be_undone_and_redone(client):  # noqa: F811
    dataset_id = await _one_step(client)
    history = (await client.get(HISTORY.format(dataset_id))).json()
    assert (history["current_position"], history["can_undo"]) == (0, True)
    assert await _median(client, dataset_id) == 10.0

    undone = await client.post(HISTORY.format(dataset_id) + "/undo")

    assert undone.status_code == 200, undone.text
    assert undone.json()["current_position"] == -1
    assert await _median(client, dataset_id) == 1000.0, "the dataset is the upload again"
    history = (await client.get(HISTORY.format(dataset_id))).json()
    assert (history["can_undo"], history["can_redo"]) == (False, True)

    redone = await client.post(HISTORY.format(dataset_id) + "/redo")

    assert (redone.status_code, redone.json()["current_position"]) == (200, 0)
    assert await _median(client, dataset_id) == 10.0


async def test_at_the_start_another_undo_is_refused(client):  # noqa: F811
    dataset_id = await _one_step(client)
    await client.post(HISTORY.format(dataset_id) + "/undo")

    again = await client.post(HISTORY.format(dataset_id) + "/undo")

    assert again.status_code == 400
    assert "beginning of history" in again.json()["detail"]


async def test_a_different_first_step_after_undoing_can_be_undone_too(client):  # noqa: F811
    """Undoing to the start and applying something else replaces the step. The base is
    still the upload, so the new step can be taken back as well."""
    dataset_id = await _one_step(client)
    await client.post(HISTORY.format(dataset_id) + "/undo")
    applied = await client.post(
        "/api/v1/transformations/apply",
        json={"dataset_id": dataset_id, "transformation_type": "trim_whitespace", "parameters": {}},
    )
    assert applied.json()["success"] is True, applied.text
    history = (await client.get(HISTORY.format(dataset_id))).json()
    assert (history["current_position"], history["can_undo"], history["can_redo"]) == (0, True, False)

    undone = await client.post(HISTORY.format(dataset_id) + "/undo")

    assert undone.status_code == 200, undone.text
    assert await _median(client, dataset_id) == 1000.0


async def test_a_dataset_edited_before_its_first_step_keeps_that_step(client):  # noqa: F811
    """The upload has moved (here by a bulk change, which records no step) before any
    step exists. No version describes the edited file, so the first step has nothing
    certain to go back to and stays as it was before: not undoable."""
    upload = await client.post("/api/v1/upload/secure", files={"file": ("visits.csv", io.BytesIO(CSV), "text/csv")})
    dataset_id = upload.json()["file_id"]
    base = f"/api/v1/transformations/datasets/{dataset_id}"
    job = await client.post(f"{base}/bulk-apply", json={
        "selected_columns": ["spend"], "transformation_type": "fill_missing", "global_parameters": {"method": "mean"},
    })
    assert job.status_code == 200, job.text
    for _ in range(200):
        status = (await client.get(f"{base}/bulk-jobs/{job.json()['job_id']}")).json()["status"]
        if status not in ("pending", "running"):
            break
        await asyncio.sleep(0.05)
    assert status == "completed", status
    applied = await client.post(
        "/api/v1/transformations/apply",
        json={"dataset_id": dataset_id, "transformation_type": "remove_duplicates", "parameters": {}},
    )
    assert applied.json()["success"] is True, applied.text

    history = (await client.get(HISTORY.format(dataset_id))).json()

    assert (history["current_position"], history["can_undo"]) == (0, False)

