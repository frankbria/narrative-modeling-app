"""#914: three handlers in authenticated routers took no credentials.

`GET /transformations/recipes/popular` returned every public recipe, its owner's
user id and its steps' parameters (column names from the owner's datasets) to
anyone. `GET /transformations/available` and `GET /upload/test` were open too.
"""

from datetime import UTC, datetime

import pytest

from app.main import app
from app.services.transformation_engine.recipe_manager import (
    TransformationRecipe,
    TransformationStep,
)

pytestmark = pytest.mark.asyncio

ME = "test_user_123"  # the identity async_authorized_client signs in as
OTHER = "another-tenant"


@pytest.fixture
async def anonymous(async_test_client):
    """A real anonymous request: no auth override installed."""
    saved = dict(app.dependency_overrides)
    app.dependency_overrides.clear()
    try:
        yield async_test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(saved)


async def _recipe(owner: str, name: str, *, public: bool, uses: int = 0) -> TransformationRecipe:
    recipe = TransformationRecipe(
        name=name,
        description="clean it",
        user_id=owner,
        steps=[
            TransformationStep(
                step_id="s1",
                transformation_type="fill_missing",
                parameters={"columns": ["salary"], "method": "median"},
                order=0,
            )
        ],
        is_public=public,
        usage_count=uses,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    await recipe.insert()
    return recipe


@pytest.mark.parametrize(
    "path", ["/api/v1/transformations/recipes/popular", "/api/v1/transformations/available"]
)
async def test_an_anonymous_caller_is_refused(anonymous, setup_database, path):
    await _recipe(OTHER, "Payroll cleanup", public=True, uses=9)

    response = await anonymous.get(path)

    assert response.status_code in (401, 403), response.text
    assert "Payroll cleanup" not in response.text and "salary" not in response.text


async def test_the_leftover_upload_test_route_is_gone(anonymous, async_authorized_client):
    assert (await anonymous.get("/api/v1/upload/test")).status_code in (401, 403, 404, 405)
    assert (await async_authorized_client.get("/api/v1/upload/test")).status_code in (404, 405)


async def test_a_signed_in_caller_still_gets_the_registry(async_authorized_client):
    response = await async_authorized_client.get("/api/v1/transformations/available")

    assert response.status_code == 200
    assert {t["type"] for t in response.json()} >= {"fill_missing", "drop_missing"}


class TestARecipesOwnerIdGoesToItsOwnerOnly:
    """A public recipe is shared with other accounts. Its owner's id is not."""

    async def test_the_popular_list(self, async_authorized_client, setup_database):
        await _recipe(OTHER, "Theirs", public=True, uses=9)
        await _recipe(ME, "Mine", public=True, uses=5)

        response = await async_authorized_client.get("/api/v1/transformations/recipes/popular")

        assert response.status_code == 200, response.text
        by_name = {r["name"]: r for r in response.json()["recipes"]}
        assert by_name["Theirs"]["user_id"] is None
        assert by_name["Mine"]["user_id"] == ME
        assert by_name["Theirs"]["steps"][0]["type"] == "fill_missing"  # still usable
        assert OTHER not in response.text

    async def test_the_callers_own_list_which_includes_public_recipes(
        self, async_authorized_client, setup_database
    ):
        await _recipe(OTHER, "Theirs", public=True)
        await _recipe(OTHER, "Their private one", public=False)
        await _recipe(ME, "Mine", public=False)

        response = await async_authorized_client.get("/api/v1/transformations/recipes")

        assert response.status_code == 200, response.text
        by_name = {r["name"]: r for r in response.json()["recipes"]}
        assert set(by_name) == {"Theirs", "Mine"}
        assert by_name["Theirs"]["user_id"] is None and by_name["Mine"]["user_id"] == ME
        assert OTHER not in response.text

    async def test_a_single_public_recipe(self, async_authorized_client, setup_database):
        theirs = await _recipe(OTHER, "Theirs", public=True)
        mine = await _recipe(ME, "Mine", public=False)
        private = await _recipe(OTHER, "Their private one", public=False)

        seen = await async_authorized_client.get(f"/api/v1/transformations/recipes/{theirs.id}")
        own = await async_authorized_client.get(f"/api/v1/transformations/recipes/{mine.id}")
        refused = await async_authorized_client.get(f"/api/v1/transformations/recipes/{private.id}")

        assert seen.status_code == 200 and seen.json()["user_id"] is None
        assert OTHER not in seen.text
        assert own.status_code == 200 and own.json()["user_id"] == ME
        assert refused.status_code == 403

    async def test_an_unknown_recipe_is_not_found(self, async_authorized_client, setup_database):
        from bson import ObjectId

        response = await async_authorized_client.get(f"/api/v1/transformations/recipes/{ObjectId()}")

        assert response.status_code == 404
        assert response.json()["detail"] == "Recipe not found"


class TestADuplicateDoesNotCarryItsSourcesOwner:
    """Duplicating a public recipe stamped the original owner's id into the copy's
    metadata, and the JSON export and the version history returned it: two requests
    recovered exactly the id the list responses withhold (cross-family review)."""

    async def test_a_new_duplicate_records_no_owner(self, async_authorized_client, setup_database):
        theirs = await _recipe(OTHER, "Theirs", public=True)

        made = await async_authorized_client.post(
            f"/api/v1/transformations/recipes/{theirs.id}/duplicate", json={"new_name": "My copy"}
        )
        assert made.status_code == 200, made.text
        copy_id = made.json()["id"]
        export = await async_authorized_client.get(f"/api/v1/transformations/recipes/{copy_id}/export/json")
        history = await async_authorized_client.get(f"/api/v1/transformations/recipes/{copy_id}/versions")

        assert export.status_code == 200 and history.status_code == 200, (export.text, history.text)
        assert OTHER not in export.text and OTHER not in history.text
        assert OTHER not in made.text
        stored = await TransformationRecipe.get(copy_id)
        assert stored.metadata["duplicated_from"] == str(theirs.id)  # the link survives
        assert "original_owner" not in stored.metadata

    async def test_a_duplicate_stored_before_the_fix_is_read_without_it(
        self, async_authorized_client, setup_database
    ):
        mine = await _recipe(ME, "An older copy", public=False)
        await TransformationRecipe.get_motor_collection().update_one(
            {"_id": mine.id},
            {"$set": {"metadata": {"duplicated_from": "abc", "original_owner": OTHER}}},
        )

        export = await async_authorized_client.get(f"/api/v1/transformations/recipes/{mine.id}/export/json")
        history = await async_authorized_client.get(f"/api/v1/transformations/recipes/{mine.id}/versions")

        assert export.status_code == 200 and history.status_code == 200, (export.text, history.text)
        assert OTHER not in export.text and OTHER not in history.text
        assert export.json()["recipe"]["metadata"]["duplicated_from"] == "abc"
