"""#850: a dataset uploaded the way the UI uploads it can be transformed.

`/upload/secure` writes only a legacy `UserData` row, and the Prepare stage hands its
ObjectId to `/transformations/preview` and `/transformations/apply`, which looked the
dataset up as `DatasetMetadata` by `dataset_id`. So every transformation on a
UI-uploaded dataset answered 404. Real routes, real S3 (LocalStack), real documents.
"""
import io

import pytest

from tests.test_integration import (
    test_transformation_first_apply_localstack as first_apply,
)

client = first_apply.client
real_s3_env = first_apply.real_s3_env
USER = first_apply.USER

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

# No PII-shaped columns, so /upload/secure stores the file instead of asking for consent.
CSV = b"id,color,score\n1, red ,10\n2,blue,\n3,green,30\n"


async def _ui_upload(client) -> str:
    upload = await client.post(
        "/api/v1/upload/secure", files={"file": ("d.csv", io.BytesIO(CSV), "text/csv")}
    )
    assert upload.status_code == 200, upload.text
    return upload.json()["file_id"]


async def test_a_ui_upload_can_be_previewed_transformed_and_undone(client, real_s3_env):
    from app.models.user_data import UserData

    dataset_id = await _ui_upload(client)

    preview = await client.post("/api/v1/transformations/preview", json={
        "dataset_id": dataset_id,
        "transformation_steps": [{"transformation_type": "trim_whitespace", "parameters": {"columns": ["color"]}}],
    })
    assert preview.status_code == 200, preview.text

    for step in (
        {"transformation_type": "trim_whitespace", "parameters": {"columns": ["color"]}},
        {"transformation_type": "fill_missing", "parameters": {"columns": ["score"], "method": "mean"}},
    ):
        applied = await client.post("/api/v1/transformations/apply", json={"dataset_id": dataset_id, **step})
        assert applied.status_code == 200 and applied.json()["success"] is True, applied.text

    history = await client.get(f"/api/v1/transformations/datasets/{dataset_id}/history")
    assert history.status_code == 200, history.text
    assert [h["transformation_type"] for h in history.json()["history"]] == ["trim_whitespace", "fill_missing"]

    # Training reads the UserData row the UI uploaded; it must follow every move.
    latest = (await UserData.get(dataset_id)).s3_url
    undo = await client.post(f"/api/v1/transformations/datasets/{dataset_id}/history/undo")
    assert undo.status_code == 200, undo.text
    assert (await UserData.get(dataset_id)).s3_url != latest, "undo must move the uploaded dataset back"


async def test_the_twin_is_created_once_and_linked_to_the_upload(client, real_s3_env):
    from app.models.dataset import DatasetMetadata
    from app.models.user_data import UserData
    from app.models.version import DatasetVersion

    dataset_id = await _ui_upload(client)
    for _ in range(2):
        applied = await client.post("/api/v1/transformations/apply", json={
            "dataset_id": dataset_id, "transformation_type": "trim_whitespace",
            "parameters": {"columns": ["color"]},
        })
        assert applied.status_code == 200, applied.text

    twins = await DatasetMetadata.find(DatasetMetadata.dataset_id == dataset_id).to_list()
    assert len(twins) == 1, "one twin per upload, not one per transformation"
    ud = await UserData.get(dataset_id)
    assert twins[0].s3_url == ud.s3_url and twins[0].user_id == USER, "the (user_id, s3_url) link holds"
    base = await DatasetVersion.find_one(DatasetVersion.dataset_id == dataset_id, DatasetVersion.is_base_version == True)  # noqa: E712
    assert base is not None, "the twin gets the base version undo restores to"


async def test_another_tenants_upload_id_is_not_found(client, real_s3_env):
    from app.services.exceptions import NotFoundError
    from app.services.transformation_service import TransformationService

    dataset_id = await _ui_upload(client)
    with pytest.raises(NotFoundError):
        await TransformationService().apply_transformation(
            user_id="someone_else", dataset_id=dataset_id,
            transformation_type="trim_whitespace", parameters={"columns": ["color"]},
        )


async def test_a_dataset_without_a_base_version_still_gets_a_restorable_history(client, real_s3_env):
    """#850 review: a missing base version (a failed write, or a dataset the feature
    builder created) left every step with version_id=None, so undo refused forever.
    The first apply now creates the base version from the frame it is about to change."""
    from app.models.version import DatasetVersion

    dataset_id = await _ui_upload(client)
    first = await client.post("/api/v1/transformations/preview", json={
        "dataset_id": dataset_id,
        "transformation_steps": [{"transformation_type": "trim_whitespace", "parameters": {"columns": ["color"]}}],
    })
    assert first.status_code == 200, first.text
    await DatasetVersion.find(DatasetVersion.dataset_id == dataset_id).delete()  # the write that failed

    for step in (
        {"transformation_type": "trim_whitespace", "parameters": {"columns": ["color"]}},
        {"transformation_type": "fill_missing", "parameters": {"columns": ["score"], "method": "mean"}},
    ):
        applied = await client.post("/api/v1/transformations/apply", json={"dataset_id": dataset_id, **step})
        assert applied.status_code == 200, applied.text

    undo = await client.post(f"/api/v1/transformations/datasets/{dataset_id}/history/undo")
    assert undo.status_code == 200, undo.text
