"""#860: POST /transformations/export-code exists, and returns a script that runs.

The Prepare stage's Export Code button posted to this path when no route served it: a
404, logged to the console, and nothing on screen. The parity of the script with the
engine is held by `tests/test_services/test_pipeline_code_export.py`; this file is the
route.
"""
import pandas as pd
import pytest

pytestmark = pytest.mark.asyncio

URL = "/api/v1/transformations/export-code"
STEPS = [
    {"type": "trim_whitespace", "parameters": {"columns": ["name"]}},
    {"type": "fill_missing", "parameters": {"columns": ["score"], "method": "mean"}},
]


async def test_the_pipeline_comes_back_as_a_script_that_runs(async_authorized_client):
    response = await async_authorized_client.post(URL, json={"steps": STEPS})

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["language"], body["filename"]) == ("python", "transformation_pipeline.py")
    namespace: dict = {"__name__": "exported_pipeline"}
    exec(compile(body["code"], "<exported pipeline>", "exec"), namespace)  # noqa: S102
    out = namespace["transform"](pd.DataFrame({"name": [" ann ", "bo"], "score": [1.0, None]}))
    assert list(out["name"]) == ["ann", "bo"] and list(out["score"]) == [1.0, 1.0]


@pytest.mark.parametrize("steps, said", [
    ([STEPS[0], {"type": "fill_missing", "parameters": {}}], "Step 2 (fill_missing): Either 'value' or 'method'"),
    ([{"type": "one_hot_encode", "parameters": {}}], "Step 1 (one_hot_encode): not a transformation the pipeline can run"),
])
async def test_a_step_that_cannot_run_is_a_422_naming_it(async_authorized_client, steps, said):
    response = await async_authorized_client.post(URL, json={"steps": steps})

    assert response.status_code == 422, response.text
    assert response.json()["detail"].startswith(said)


async def test_the_old_payload_shape_is_refused(async_authorized_client):
    """What the button sent before: `transformations`, where the model reads `steps`."""
    response = await async_authorized_client.post(URL, json={"transformations": STEPS})

    assert response.status_code == 422


async def test_a_saved_recipe_exports_the_same_script(async_authorized_client, setup_database):
    """The recipe export had its own generator, which emitted nothing for drop_missing
    or for a fill with no column named."""
    steps = [{"type": "drop_missing", "parameters": {"columns": ["score"]}}, {"type": "fill_missing", "parameters": {"value": "none"}}]
    created = await async_authorized_client.post(
        "/api/v1/transformations/recipes", json={"name": "Clean", "description": "d", "steps": steps}
    )
    assert created.status_code == 200, created.text

    exported = await async_authorized_client.post(
        f"/api/v1/transformations/recipes/{created.json()['id']}/export", json={"language": "python"}
    )
    direct = await async_authorized_client.post(URL, json={"steps": steps})

    assert exported.status_code == 200, exported.text
    assert exported.json()["code"] == direct.json()["code"]
    assert "dropna" in exported.json()["code"] and "fillna('none')" in exported.json()["code"]


async def test_a_recipe_with_a_step_the_engine_no_longer_runs_is_a_422(async_authorized_client, setup_database):
    created = await async_authorized_client.post(
        "/api/v1/transformations/recipes",
        json={"name": "Old", "description": "d", "steps": [{"type": "one_hot_encode", "parameters": {}}]},
    )
    assert created.status_code == 200, created.text

    exported = await async_authorized_client.post(
        f"/api/v1/transformations/recipes/{created.json()['id']}/export", json={"language": "python"}
    )

    assert exported.status_code == 422, exported.text
    assert "Step 1 (one_hot_encode)" in exported.json()["detail"]
