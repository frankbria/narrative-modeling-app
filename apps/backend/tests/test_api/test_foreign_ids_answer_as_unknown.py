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
