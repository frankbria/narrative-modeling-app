"""#472: `POST /api/v1/` (store.py) could never succeed and had no caller — it is gone.

The handler built a `UserData` with fields the model does not have, so every call 500'd
on the paid API. Removal was the chosen outcome; this pins that nothing serves the bare
prefix again.
"""
import pytest
from fastapi.routing import APIRoute

from app.main import app

pytestmark = pytest.mark.asyncio


def _post_paths() -> set[str]:
    found: set[str] = set()

    def walk(routes, prefix: str = "") -> None:
        for route in routes:
            if type(route).__name__ == "_IncludedRouter":
                context = getattr(route, "include_context", None)
                walk(route.original_router.routes, prefix + (getattr(context, "prefix", "") or ""))
            elif isinstance(route, APIRoute) and "POST" in (route.methods or ()):
                found.add(prefix + route.path)

    walk(app.routes)
    return found


def test_nothing_serves_a_post_to_the_bare_api_prefix():
    assert "/api/v1/" not in _post_paths()
    assert "/api/v1" not in _post_paths()


async def test_the_bare_prefix_answers_not_found(async_authorized_client, setup_database):
    response = await async_authorized_client.post(
        "/api/v1/", json={"fileName": "x.csv", "fileType": "csv", "headers": ["a"], "data": [[1]]}
    )
    assert response.status_code in (404, 405), response.text
