"""#923: a bulk transformation is a history step.

They used to move the dataset with no step, which closed the history behind them (#851):
the edit was not listed and could not be undone, and every earlier step became
unreachable. Each now records a step and a version like an engine transformation, so
the history lists it and undo restores the dataset to the step before it.

Real routes, real documents, real objects (LocalStack): undo restores a version's own
object, which only a real bucket holds.
"""
import asyncio
import io

import pandas as pd
import pytest

from tests.test_integration import (
    test_transformation_first_apply_localstack as first_apply,
)

client = first_apply.client
real_s3_env = first_apply.real_s3_env
USER = first_apply.USER

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

MESSY = b"id,color,score\n1, red ,10\n2,blue,\n2,blue,\n4,green,\n5,red,45\n6,red,45\n"
T = "/api/v1/transformations"


async def _trimmed_dataset(client) -> tuple[str, str]:
    """A dataset with one engine step already applied (so there is a step before the
    edit): its dataset id and its upload record's id."""
    from app.models.user_data import UserData

    upload = await client.post("/api/v1/datasets/upload", files={"file": ("messy.csv", io.BytesIO(MESSY), "text/csv")})
    assert upload.status_code in (200, 201), upload.text
    dataset_id = upload.json()["dataset_id"]
    applied = await client.post(f"{T}/apply", json={
        "dataset_id": dataset_id, "transformation_type": "trim_whitespace", "parameters": {"columns": ["color"]}})
    assert applied.json()["success"] is True, applied.text
    upload_row = await UserData.find_one(UserData.user_id == USER, UserData.original_filename == "messy.csv")
    return dataset_id, str(upload_row.id)


async def _frame(dataset_id: str) -> pd.DataFrame:
    """The dataset's current file, as both twins name it."""
    from app.models.dataset import DatasetMetadata
    from app.models.user_data import UserData
    from app.services.transformation_engine.data_utils import get_dataframe_from_s3

    meta = await DatasetMetadata.find_one(DatasetMetadata.dataset_id == dataset_id)
    assert await UserData.find_one(UserData.user_id == USER, UserData.s3_url == meta.s3_url), "twins moved together"
    return await get_dataframe_from_s3(meta.s3_url)


async def _history(client, dataset_id: str) -> dict:
    response = await client.get(f"{T}/datasets/{dataset_id}/history")
    assert response.status_code == 200, response.text
    return response.json()


async def _undo_restores(client, dataset_id: str, before: pd.DataFrame) -> None:
    undo = await client.post(f"{T}/datasets/{dataset_id}/history/undo")
    assert undo.status_code == 200, undo.text
    assert undo.json()["current_position"] == 0
    pd.testing.assert_frame_equal(await _frame(dataset_id), before, check_dtype=False)
    history = await _history(client, dataset_id)
    assert history["can_undo"] is True, "the step before the edit is still undoable"
    assert history["can_redo"] is True, "and the edit can be redone"


async def test_a_bulk_transformation_is_a_step_and_can_be_undone(client, real_s3_env):
    dataset_id, _ = await _trimmed_dataset(client)
    before = await _frame(dataset_id)
    base = f"{T}/datasets/{dataset_id}"

    job = await client.post(f"{base}/bulk-apply", json={
        "selected_columns": ["score"], "transformation_type": "fill_missing", "global_parameters": {"method": "mean"}})
    assert job.status_code == 200, job.text
    for _ in range(200):
        status = (await client.get(f"{base}/bulk-jobs/{job.json()['job_id']}")).json()["status"]
        if status not in ("pending", "running"):
            break
        await asyncio.sleep(0.05)
    assert status == "completed"
    assert (await _frame(dataset_id))["score"].isna().sum() == 0

    history = await _history(client, dataset_id)
    assert [h["transformation_type"] for h in history["history"]] == ["trim_whitespace", "fill_missing"]
    assert history["history"][1]["description"] == "Bulk fill missing on score"
    assert history["history"][1]["affected_columns"] == ["score"]
    await _undo_restores(client, dataset_id, before)
