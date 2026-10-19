"""#985: another account's object answers exactly as an unknown id does.

The routes answered 403 "Access denied" for a foreign object and 404 for an unknown one,
so any signed-in caller could tell which ids exist (#751 fixed the same for datasets).
One test per object type, with real documents owned by another account.
"""


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
