"""The frontend's recipe-list fixture is what the recipe routes really answer (#859).

The recipe browser listed from `GET /recipes?filter=…&dataset_id=…`, a route that does
not exist, and loading a recipe read `recipe.transformations` where the API sends
`steps`. Nothing tied the UI to the API, so Browse was always empty and nothing said why.
The frontend's `pipelineApi.contract.test.ts` checks every list request it builds against
the routes and query parameters recorded here, and reads recipes out of these captured
responses.

Regenerate after a deliberate change to the routes or to `RecipeResponse`:
    UPDATE_FIXTURES=1 PYTHONPATH=. uv run pytest tests/test_api/test_recipe_list_response_fixture.py
"""

import json
import os
from pathlib import Path

import pytest

FIXTURE = Path(__file__).resolve().parents[4] / "apps/frontend/__tests__/fixtures/recipeLists.json"
ROUTES = ("/transformations/recipes", "/transformations/recipes/popular")
RECIPE = {
    "name": "Tidy names",
    "description": "Trim the names, then fill the scores",
    "dataset_id": "ds1",
    "is_public": True,
    "steps": [
        {"type": "trim_whitespace", "parameters": {"columns": ["name"]}},
        {"type": "fill_missing", "parameters": {"columns": ["score"], "method": "mean"}},
    ],
}


def _stable(body: dict) -> dict:
    """The response with the values that differ on every run replaced."""
    for number, recipe in enumerate(body["recipes"], start=1):
        recipe.update(id=f"recipe-{number}", created_at="2026-10-01T00:00:00", updated_at="2026-10-01T00:00:00")
        for step in recipe["steps"]:
            step["step_id"] = f"step-{step['order'] + 1}"
    return body


def _query_parameters(path: str) -> list[str]:
    from app.main import app

    # The OpenAPI document, not app.routes: on FastAPI 0.139 routers are lazy
    # wrappers and app.routes is not flat (CLAUDE.md, #459).
    operation = app.openapi()["paths"][f"/api/v1{path}"]["get"]
    return sorted(p["name"] for p in operation.get("parameters", []) if p["in"] == "query")


def _shape(value):
    """Keys all the way down; lists are described by their first item."""
    if isinstance(value, dict):
        return {key: _shape(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_shape(value[0])] if value else []
    return type(value).__name__


@pytest.mark.asyncio
async def test_the_frontend_fixture_is_what_the_recipe_routes_answer(async_authorized_client, setup_database):
    created = await async_authorized_client.post("/api/v1/transformations/recipes", json=RECIPE)
    assert created.status_code == 200, created.text

    captured = {}
    for path in ROUTES:
        response = await async_authorized_client.get(f"/api/v1{path}")
        assert response.status_code == 200, response.text
        assert [r["name"] for r in response.json()["recipes"]] == ["Tidy names"], path
        captured[f"GET {path}"] = {"query": _query_parameters(path), "response": _stable(response.json())}

    if os.getenv("UPDATE_FIXTURES"):
        FIXTURE.write_text(json.dumps(captured, indent=2, sort_keys=True) + "\n")
    fixture = json.loads(FIXTURE.read_text())
    assert _shape(fixture) == _shape(captured), "regenerate recipeLists.json: a recipe route changed"
    assert {route: entry["query"] for route, entry in fixture.items()} == {
        route: entry["query"] for route, entry in captured.items()
    }, "regenerate recipeLists.json: a recipe route's query parameters changed"
