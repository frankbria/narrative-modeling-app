"""#800: a dataset's transformation history is reachable by dataset id.

`HistoryService` looked the config up with `get_transformation_config(dataset_id)`, a
lookup by `config_id`, and `apply_transformation` minted a new config per call
(`config_{dataset}_{ts}`). So every history route (get, undo, redo, jump, clear)
answered 404 for every dataset. Only the full flow can see that: real documents, real
versions in S3 (LocalStack), the real routes. A patched lookup passes either way.
"""
import io

import pytest

from tests.test_integration import (
    test_transformation_first_apply_localstack as first_apply,
)

# The LocalStack app client and S3 env from the first-apply suite, as this module's fixtures.
client = first_apply.client
real_s3_env = first_apply.real_s3_env
USER = first_apply.USER

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

CSV = b"id,name,score\n1, alice ,10\n2,bob,\n3,carol,30\n"


async def _upload_and_transform_twice(client) -> str:
    upload = await client.post(
        "/api/v1/datasets/upload", files={"file": ("d.csv", io.BytesIO(CSV), "text/csv")}
    )
    assert upload.status_code in (200, 201), upload.text
    dataset_id = upload.json()["dataset_id"]
    for step in (
        {"transformation_type": "trim_whitespace", "parameters": {"columns": ["name"]}},
        {"transformation_type": "fill_missing", "parameters": {"columns": ["score"], "method": "mean"}},
    ):
        applied = await client.post("/api/v1/transformations/apply", json={"dataset_id": dataset_id, **step})
        assert applied.status_code == 200 and applied.json()["success"] is True, applied.text
    return dataset_id


async def test_the_history_lists_both_transformations_in_order(client, real_s3_env):
    dataset_id = await _upload_and_transform_twice(client)

    history = await client.get(f"/api/v1/transformations/datasets/{dataset_id}/history")

    assert history.status_code == 200, history.text
    body = history.json()
    assert [h["transformation_type"] for h in body["history"]] == ["trim_whitespace", "fill_missing"]
    assert body["current_position"] == 1 and body["can_undo"] is True and body["can_redo"] is False


async def test_undo_moves_the_dataset_back_and_redo_forward(client, real_s3_env):
    from app.models.dataset import DatasetMetadata

    dataset_id = await _upload_and_transform_twice(client)
    latest = (await DatasetMetadata.find_one(DatasetMetadata.dataset_id == dataset_id)).s3_url

    undo = await client.post(f"/api/v1/transformations/datasets/{dataset_id}/history/undo")
    assert undo.status_code == 200, undo.text
    assert undo.json()["current_position"] == 0
    after_undo = (await DatasetMetadata.find_one(DatasetMetadata.dataset_id == dataset_id)).s3_url
    assert after_undo != latest, "undo must move the dataset to the first step's version"

    redo = await client.post(f"/api/v1/transformations/datasets/{dataset_id}/history/redo")
    assert redo.status_code == 200 and redo.json()["current_position"] == 1, redo.text


async def test_another_tenant_cannot_read_the_history(client, real_s3_env):
    from app.services.exceptions import NotFoundError
    from app.services.history_service import HistoryService
    from app.services.transformation_service import TransformationService
    from app.services.versioning_service import versioning_service

    dataset_id = await _upload_and_transform_twice(client)
    service = HistoryService(
        versioning_service=versioning_service, transformation_service=TransformationService()
    )

    assert (await service.get_history(dataset_id, USER))["history"], "precondition: the owner sees it"
    with pytest.raises(NotFoundError):
        await service.get_history(dataset_id, "someone_else")
