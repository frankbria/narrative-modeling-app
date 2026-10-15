"""#985: another account's object answers exactly as an unknown id does.

The routes answered 403 "Access denied" for a foreign object and 404 for an unknown one,
so any signed-in caller could tell which ids exist (#751 fixed the same for datasets).
One test per object type, with real documents owned by another account.
"""

import uuid
from datetime import UTC, datetime

import pytest
from beanie import PydanticObjectId

from tests.test_api.test_public_handlers_closed import _recipe

pytestmark = pytest.mark.asyncio

OTHER = "another-tenant"


async def _same_answer(client, method: str, foreign: str, unknown: str, **kwargs):
    theirs = await client.request(method, foreign, **kwargs)
    nobodys = await client.request(method, unknown, **kwargs)
    assert theirs.status_code == nobodys.status_code == 404, (theirs.text, nobodys.text)
    return theirs, nobodys


async def test_a_private_recipe(setup_database, async_authorized_client):
    recipe = await _recipe(OTHER, "theirs", public=False)
    base = "/api/v1/transformations/recipes"

    for suffix in ("", "/versions", "/export/json"):
        theirs, nobodys = await _same_answer(
            async_authorized_client, "GET", f"{base}/{recipe.id}{suffix}", f"{base}/{PydanticObjectId()}{suffix}"
        )
        assert theirs.json() == nobodys.json()


async def test_a_transformation_config(setup_database, async_authorized_client):
    from app.models.transformation import TransformationConfig

    await TransformationConfig(user_id=OTHER, dataset_id="d985", config_id="config_985").insert()

    await _same_answer(
        async_authorized_client, "GET", "/api/v1/transformations/config_985/history",
        "/api/v1/transformations/config_nobody/history",
    )


async def test_a_plot(setup_database, async_authorized_client):
    from app.models.plot import Plot

    plot = await Plot(userId=OTHER, datasetId=None, type="histogram", imageUrl="https://example.com/p.png").insert()

    theirs, nobodys = await _same_answer(
        async_authorized_client, "GET", f"/api/v1/plots/{plot.id}", f"/api/v1/plots/{PydanticObjectId()}"
    )
    assert theirs.json() == nobodys.json()


async def test_an_analytics_result(setup_database, async_authorized_client):
    from app.models.analytics_result import AnalyticsResult
    from app.models.user_data import UserData

    dataset = await UserData(
        user_id=OTHER, filename="d.csv", original_filename="d.csv", s3_url=f"s3://b/datasets/{OTHER}/d.csv",
        num_rows=1, num_columns=1, data_schema=[],
    ).insert()
    result = await AnalyticsResult(userId=OTHER, datasetId=dataset, analysisType="EDA").insert()

    theirs, nobodys = await _same_answer(
        async_authorized_client, "GET", f"/api/v1/analytics/{result.id}", f"/api/v1/analytics/{PydanticObjectId()}"
    )
    assert theirs.json() == nobodys.json()


async def _stored_feature(owner: str, *, shared_with: list[str] | None = None):
    from app.models.feature_store import StoredFeature

    return await StoredFeature(
        feature_id=f"feat_{uuid.uuid4().hex[:8]}", user_id=owner, name="ratio", description="a ratio",
        category="numeric", definition_type="transformation", definition_code="a / b",
        input_requirements={"a": "numeric", "b": "numeric"}, output_type="numeric", output_column_name="ratio",
        created_by=owner,
        shared_with=shared_with or [], created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
    ).insert()


async def test_a_feature_store_feature_the_caller_cannot_see(setup_database, async_authorized_client):
    feature = await _stored_feature(OTHER)
    base = "/api/v1/feature-store/features"

    await _same_answer(async_authorized_client, "GET", f"{base}/{feature.feature_id}", f"{base}/feat_nobody")
    await _same_answer(
        async_authorized_client, "PUT", f"{base}/{feature.feature_id}", f"{base}/feat_nobody", json={"name": "mine"}
    )


async def test_a_shared_reader_who_changes_a_feature_is_refused_with_a_403(setup_database, async_authorized_client):
    """They may read it, so they already know it exists: a 403 here is a real answer."""
    feature = await _stored_feature(OTHER, shared_with=["test_user_123"])
    base = f"/api/v1/feature-store/features/{feature.feature_id}"

    assert (await async_authorized_client.get(base)).status_code == 200
    changed = await async_authorized_client.put(base, json={"name": "mine"})
    assert changed.status_code == 403


async def test_a_dataset_for_feature_suggestions(setup_database, async_authorized_client):
    from app.models.dataset import DatasetMetadata

    await DatasetMetadata(
        user_id=OTHER, dataset_id="ds_985", filename="d.csv", original_filename="d.csv", file_type="csv",
        file_path=f"datasets/{OTHER}/d.csv", s3_url=f"s3://b/datasets/{OTHER}/d.csv", num_rows=1, num_columns=1,
    ).insert()

    await _same_answer(
        async_authorized_client, "POST", "/api/v1/datasets/ds_985/features/suggest",
        "/api/v1/datasets/ds_nobody/features/suggest", json={},
    )


async def test_a_private_recipe_cannot_be_applied_or_checked(setup_database, async_authorized_client):
    recipe = await _recipe(OTHER, "theirs", public=False)
    base = "/api/v1/transformations/recipes"

    await _same_answer(
        async_authorized_client, "POST", f"{base}/{recipe.id}/apply", f"{base}/{PydanticObjectId()}/apply",
        json={"dataset_id": "d985"},
    )
    await _same_answer(
        async_authorized_client, "POST", f"{base}/{recipe.id}/check-compatibility",
        f"{base}/{PydanticObjectId()}/check-compatibility", json={"dataset_schema": {"a": "numeric"}},
    )


async def test_a_readable_recipe_is_checked(setup_database, async_authorized_client):
    recipe = await _recipe(OTHER, "shared", public=True)

    checked = await async_authorized_client.post(
        f"/api/v1/transformations/recipes/{recipe.id}/check-compatibility", json={"dataset_schema": {"a": "numeric"}}
    )
    assert checked.status_code == 200, checked.text
    assert "is_compatible" in checked.json()


async def test_redo_on_a_dataset_with_no_history(setup_database, async_authorized_client):
    redo = await async_authorized_client.post("/api/v1/transformations/datasets/ds_nobody/history/redo")
    assert redo.status_code == 404


async def test_a_feature_collection(setup_database, async_authorized_client):
    from app.models.feature_store import FeatureCollection
    from app.services.exceptions import NotFoundError
    from app.services.feature_store_service import FeatureStoreService

    await FeatureCollection(
        collection_id="col_985", user_id=OTHER, created_by=OTHER, name="c", description="c", domain="retail",
        created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
    ).insert()
    service = FeatureStoreService()

    assert (await service.get_collection("col_985", OTHER)).collection_id == "col_985"
    for collection_id in ("col_985", "col_nobody"):
        with pytest.raises(NotFoundError):
            await service.get_collection(collection_id, "test_user_123")


async def test_the_base_service_changes_only_the_callers_own_documents(setup_database):
    from app.models.workflow import WorkflowState
    from app.services.exceptions import NotFoundError
    from app.services.workflow_service import WorkflowService

    await WorkflowState(workflow_id="wf_985", user_id=OTHER, dataset_id="d985", current_stage="upload").insert()
    service = WorkflowService()

    for change in (
        service.update("wf_985", "test_user_123", {"current_stage": "train"}),
        service.delete("wf_985", "test_user_123"),
    ):
        with pytest.raises(NotFoundError):
            await change

    updated = await service.update("wf_985", OTHER, {"current_stage": "train", "nope": 1}, allowed_fields=["current_stage"])
    assert updated.current_stage == "train"
    assert await service.delete("wf_985", OTHER, soft_delete=True) is True
    assert await WorkflowState.find_one(WorkflowState.workflow_id == "wf_985") is None


async def test_the_callers_own_dataset_is_loaded(setup_database, monkeypatch):
    import pandas as pd

    from app.api.routes import feature_engineering
    from app.models.dataset import DatasetMetadata

    await DatasetMetadata(
        user_id=OTHER, dataset_id="ds_985_own", filename="d.csv", original_filename="d.csv", file_type="csv",
        file_path=f"datasets/{OTHER}/d.csv", s3_url=f"s3://b/datasets/{OTHER}/d.csv", num_rows=1, num_columns=1,
    ).insert()
    monkeypatch.setattr(feature_engineering, "load_dataframe_from_s3", lambda url, kind: pd.DataFrame({"a": [1]}))

    frame = await feature_engineering._load_dataset_dataframe("ds_985_own", OTHER)
    assert list(frame.columns) == ["a"]


async def test_the_callers_dataset_of_another_type_or_unreadable_is_refused(setup_database, monkeypatch):
    from fastapi import HTTPException

    from app.api.routes import feature_engineering
    from app.models.dataset import DatasetMetadata

    for dataset_id, file_type in (("ds_985_json", "json"), ("ds_985_bad", "csv")):
        await DatasetMetadata(
            user_id=OTHER, dataset_id=dataset_id, filename="d", original_filename="d", file_type=file_type,
            file_path=f"datasets/{OTHER}/d", s3_url=f"s3://b/datasets/{OTHER}/d", num_rows=1, num_columns=1,
        ).insert()

    def unreadable(url, kind):
        raise OSError("gone")

    monkeypatch.setattr(feature_engineering, "load_dataframe_from_s3", unreadable)
    monkeypatch.setattr(feature_engineering, "ALLOWED_FILE_TYPES", {"csv"})
    for dataset_id, status in (("ds_985_json", 400), ("ds_985_bad", 500)):
        with pytest.raises(HTTPException) as refused:
            await feature_engineering._load_dataset_dataframe(dataset_id, OTHER)
        assert refused.value.status_code == status
