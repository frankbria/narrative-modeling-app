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


# #888: a version held parquet bytes under the upload's own name (`…/versions/{id}/d.csv`).
# Nothing read that object until an undo made it the current file; then `file_type` said
# csv over parquet bytes, and training and column stats misread it.


async def _undo(client, dataset_id: str):
    """Undo one step; the dataset's two twins as stored afterwards."""
    from app.models.dataset import DatasetMetadata
    from app.models.user_data import UserData

    undo = await client.post(f"/api/v1/transformations/datasets/{dataset_id}/history/undo")
    assert undo.status_code == 200, undo.text
    meta = await DatasetMetadata.find_one(DatasetMetadata.dataset_id == dataset_id)
    twin = await UserData.find_one(UserData.user_id == USER, UserData.s3_url == meta.s3_url)
    assert twin is not None, "precondition: the undo moved both twins together"
    return meta, twin


async def _read_as_a_training_stage_does(twin):
    """Feature selection's own read: dispatch on the twin's file_type, checked against the bytes."""
    import asyncio

    from app.services.s3_service import load_dataframe_from_s3

    return await asyncio.to_thread(load_dataframe_from_s3, twin.s3_url, twin.file_type)


async def _store_under_the_uploads_name(s3_client, bucket: str, dataset_id: str) -> None:
    """Re-key the first step's version to the shape every version had before #888."""
    from app.models.version import DatasetVersion

    version = await DatasetVersion.find_one(
        DatasetVersion.dataset_id == dataset_id, DatasetVersion.version_number == 2
    )
    legacy_key = f"{version.file_path.rsplit('/', 1)[0]}/d.csv"
    if version.file_path == legacy_key:
        return  # this code still writes versions that way
    s3_client.copy_object(
        Bucket=bucket, Key=legacy_key, CopySource={"Bucket": bucket, "Key": version.file_path}
    )
    s3_client.delete_object(Bucket=bucket, Key=version.file_path)
    await version.set({"file_path": legacy_key, "s3_url": f"s3://{bucket}/{legacy_key}"})


async def test_after_an_undo_the_dataset_says_what_its_file_holds(client, real_s3_env):
    dataset_id = await _upload_and_transform_twice(client)

    meta, twin = await _undo(client, dataset_id)

    assert meta.s3_url.endswith(".parquet"), "a version object is named for the parquet it holds"
    assert (twin.file_type, meta.file_type) == ("parquet", "parquet")
    frame = await _read_as_a_training_stage_does(twin)
    assert list(frame["name"]) == ["alice", "bob", "carol"], "the first step (trim) is still applied"
    assert frame["score"].isna().sum() == 1, "the second step (fill) is the one that was undone"

    stats = await client.get(f"/api/v1/column_stats/dataset/{twin.id}")
    assert stats.status_code == 200, stats.text
    assert sorted(s["column_name"] for s in stats.json()) == ["id", "name", "score"]


async def test_a_version_stored_under_the_uploads_name_is_restored_as_parquet(
    client, s3_client, real_s3_env
):
    dataset_id = await _upload_and_transform_twice(client)
    await _store_under_the_uploads_name(s3_client, real_s3_env, dataset_id)

    meta, twin = await _undo(client, dataset_id)

    assert meta.s3_url.endswith("/d.csv"), "precondition: the restored object keeps its old name"
    assert (twin.file_type, meta.file_type) == ("parquet", "parquet")
    frame = await _read_as_a_training_stage_does(twin)
    assert list(frame["name"]) == ["alice", "bob", "carol"]


async def test_the_audit_corrects_a_dataset_an_old_undo_left_calling_parquet_csv(
    client, s3_client, real_s3_env
):
    import importlib.util
    from pathlib import Path

    from app.models.dataset import DatasetMetadata
    from app.models.user_data import UserData

    script = Path(__file__).resolve().parents[2] / "scripts" / "audit_dataset_file_types.py"
    spec = importlib.util.spec_from_file_location("audit_dataset_file_types", script)
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)

    dataset_id = await _upload_and_transform_twice(client)
    await _store_under_the_uploads_name(s3_client, real_s3_env, dataset_id)
    meta, twin = await _undo(client, dataset_id)
    # what an undo wrote before #888: the name's type, over parquet bytes
    await twin.set({"file_type": "csv"})
    await meta.set({"file_type": "csv"})

    result = await audit._audit(UserData, apply=True)

    assert (result["mismatched"], result["fixed"]) == (1, 1)
    assert (await UserData.get(twin.id)).file_type == "parquet"
    assert (await audit._audit(DatasetMetadata, apply=True))["fixed"] == 1
