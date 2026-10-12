"""#851: a pipeline records its steps.

The pipeline route, and the two routes that run through it (auto-clean and recipe
apply), moved the dataset with no history step, so an undo afterwards restored a version
from before them and `GET …/history` never listed them. Real documents here; only
storage is stubbed.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId

from app.models.user_data import UserData
from app.services.transformation_engine.recipe_manager import TransformationRecipe
from tests.test_api import test_object_id_lookups as lookups

# The storage stub and the seeded upload from the id-lookup suite, as this module's own.
s3_stubbed = lookups.s3_stubbed
seed = lookups.seed

_PIPELINE = [
    {"type": "trim_whitespace", "parameters": {"columns": ["name"]}, "description": "Clean name column"},
    {"type": "fill_missing", "parameters": {"columns": ["age"], "method": "mean"}, "description": "Fill ages"},
    {"type": "remove_duplicates", "parameters": {"columns": ["email"], "keep": "first"}},
]


async def _listed(client, dataset_id: str) -> list[str]:
    history = await client.get(f"/api/v1/transformations/datasets/{dataset_id}/history")
    if history.status_code == 404:
        return []
    assert history.status_code == 200, history.text
    return [step["transformation_type"] for step in history.json()["history"]]


pytestmark = pytest.mark.asyncio


class TestThePipelineRecordsItsSteps:
    async def test_each_transformation_is_a_history_step_in_order(
        self, async_authorized_client, setup_database, s3_stubbed
    ):
        upload = await seed()

        response = await async_authorized_client.post(
            "/api/v1/transformations/pipeline/apply",
            json={"dataset_id": str(upload.id), "transformations": _PIPELINE},
        )

        assert response.status_code == 200 and response.json()["success"] is True, response.text
        assert {"age", "name"} <= set(response.json()["affected_columns"])
        assert await _listed(async_authorized_client, str(upload.id)) == [
            "trim_whitespace", "fill_missing", "remove_duplicates",
        ]
        history = await async_authorized_client.get(f"/api/v1/transformations/datasets/{upload.id}/history")
        assert (history.json()["current_position"], history.json()["can_undo"]) == (2, True)

    async def test_a_failing_step_writes_nothing(self, async_authorized_client, setup_database, s3_stubbed):
        upload = await seed()
        steps = [_PIPELINE[0], {"type": "fill_missing", "parameters": {"columns": ["age"], "method": "no_such_method"}}]

        response = await async_authorized_client.post(
            "/api/v1/transformations/pipeline/apply",
            json={"dataset_id": str(upload.id), "transformations": steps},
        )

        body = response.json()
        assert response.status_code == 200 and body["success"] is False, response.text
        assert body["error"].startswith("Transformation 'fill_missing' failed:"), body["error"]
        assert await _listed(async_authorized_client, str(upload.id)) == []
        assert (await UserData.get(upload.id)).s3_url == upload.s3_url, "the first step must not have landed"

    async def test_a_type_the_engine_does_not_run_fails_the_pipeline_by_name(
        self, async_authorized_client, setup_database, s3_stubbed
    ):
        upload = await seed()
        steps = [_PIPELINE[0], {"type": "one_hot_encode", "parameters": {}}]

        response = await async_authorized_client.post(
            "/api/v1/transformations/pipeline/apply",
            json={"dataset_id": str(upload.id), "transformations": steps},
        )

        assert response.json()["success"] is False, response.text
        assert response.json()["error"].startswith("Transformation 'one_hot_encode' failed:")
        assert (await UserData.get(upload.id)).s3_url == upload.s3_url

    async def test_the_pipeline_is_saved_as_a_recipe_with_the_resulting_schema(
        self, async_authorized_client, setup_database, s3_stubbed
    ):
        upload = await seed()
        with patch(
            "app.api.routes.transformations.RecipeManager.create_recipe", new_callable=AsyncMock
        ) as created:
            response = await async_authorized_client.post(
                "/api/v1/transformations/pipeline/apply",
                json={
                    "dataset_id": str(upload.id), "transformations": _PIPELINE[:1],
                    "save_as_recipe": True, "recipe_name": "Data Cleaning Pipeline",
                },
            )

        assert response.json()["success"] is True, response.text
        saved = created.await_args.kwargs
        assert saved["name"] == "Data Cleaning Pipeline"
        assert set(saved["schema_snapshot"]) == {"id", "name", "age", "email"}

    async def test_auto_clean_lists_what_it_did(self, async_authorized_client, setup_database, s3_stubbed):
        upload = await seed()

        response = await async_authorized_client.post(
            "/api/v1/transformations/auto-clean",
            json={"dataset_id": str(upload.id), "options": {"handle_missing": "impute"}},
        )

        assert response.status_code == 200 and response.json()["success"] is True, response.text
        assert await _listed(async_authorized_client, str(upload.id)) == [
            "remove_duplicates", "trim_whitespace", "fill_missing",
        ]

    async def test_auto_clean_drop_missing_actually_drops(
        self, async_authorized_client, setup_database, s3_stubbed
    ):
        """handle_missing='drop' must really drop rows, not silently no-op (#274)."""
        upload = await seed()

        response = await async_authorized_client.post(
            "/api/v1/transformations/auto-clean",
            json={
                "dataset_id": str(upload.id),
                "options": {"remove_duplicates": False, "trim_whitespace": False, "handle_missing": "drop"},
            },
        )

        assert response.json()["success"] is True, response.text
        assert response.json()["affected_rows"] == 1, "one seeded row carries a missing value"
        assert await _listed(async_authorized_client, str(upload.id)) == ["drop_missing"]

    async def test_a_recipe_applied_to_a_dataset_is_listed_and_its_run_recorded(
        self, async_authorized_client, setup_database, s3_stubbed
    ):
        upload = await seed()
        recipe = MagicMock(spec=TransformationRecipe)
        recipe.is_public, recipe.user_id = True, "other_user"
        recipe.steps = [MagicMock(transformation_type="trim_whitespace", parameters={"columns": []}, description="Clean")]
        recipe_id = str(ObjectId())
        with patch(
            "app.api.routes.transformations.RecipeManager.get_recipe", new_callable=AsyncMock, return_value=recipe
        ), patch(
            "app.api.routes.transformations.RecipeManager.record_execution", new_callable=AsyncMock
        ) as recorded:
            response = await async_authorized_client.post(
                f"/api/v1/transformations/recipes/{recipe_id}/apply",
                json={"recipe_id": recipe_id, "dataset_id": str(upload.id)},
            )

        assert response.status_code == 200 and response.json()["success"] is True, response.text
        recorded.assert_called_once()
        assert await _listed(async_authorized_client, str(upload.id)) == ["trim_whitespace"]

    async def test_a_failed_upload_leaves_the_dataset_and_its_history_as_they_were(
        self, async_authorized_client, setup_database, s3_stubbed
    ):
        """Versions and the new file are written before any step is recorded or the
        dataset moved, so storage failing part-way cannot leave half a pipeline applied."""
        upload = await seed()
        with patch(
            "app.services.transformation_engine.data_utils.upload_file_to_s3", return_value=(False, None)
        ):
            response = await async_authorized_client.post(
                "/api/v1/transformations/pipeline/apply",
                json={"dataset_id": str(upload.id), "transformations": _PIPELINE},
            )

        assert response.status_code == 200 and response.json()["success"] is False, response.text
        assert await _listed(async_authorized_client, str(upload.id)) == []
        assert (await UserData.get(upload.id)).s3_url == upload.s3_url

    async def test_auto_clean_with_nothing_to_do_changes_nothing(
        self, async_authorized_client, setup_database, s3_stubbed
    ):
        upload = await seed()

        response = await async_authorized_client.post(
            "/api/v1/transformations/auto-clean",
            json={"dataset_id": str(upload.id), "options": {"remove_duplicates": False, "trim_whitespace": False}},
        )

        assert response.status_code == 200 and response.json()["success"] is True, response.text
        assert response.json()["affected_rows"] == 0
        assert await _listed(async_authorized_client, str(upload.id)) == []
        assert (await UserData.get(upload.id)).s3_url == upload.s3_url

    async def test_one_history_whichever_id_names_the_dataset(
        self, async_authorized_client, setup_database, s3_stubbed
    ):
        """A `/datasets` upload has two ids, one per twin. Keyed on the request's id, a step
        applied through one was missing from the history read through the other."""
        from app.models.dataset import DatasetMetadata

        upload = await seed()
        await DatasetMetadata(
            user_id=upload.user_id, dataset_id="dataset_twin", filename="t.csv", original_filename="t.csv",
            file_type="csv", file_path=upload.s3_url, s3_url=upload.s3_url, num_rows=5, num_columns=4,
        ).insert()

        by_dataset_id = await async_authorized_client.post(
            "/api/v1/transformations/apply",
            json={"dataset_id": "dataset_twin", "transformation_type": "trim_whitespace",
                  "parameters": {"columns": ["name"]}},
        )
        by_upload_id = await async_authorized_client.post(
            "/api/v1/transformations/pipeline/apply",
            json={"dataset_id": str(upload.id), "transformations": _PIPELINE[1:2]},
        )

        assert by_dataset_id.json()["success"] and by_upload_id.json()["success"], by_upload_id.text
        assert await _listed(async_authorized_client, "dataset_twin") == ["trim_whitespace", "fill_missing"]
        assert await _listed(async_authorized_client, str(upload.id)) == ["trim_whitespace", "fill_missing"]

