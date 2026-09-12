"""Every module under app/api/routes/ is reachable on the live app (#471 AC5).

`app/api/routes/__init__.py` mounts routers on an `api_router` aggregator that nothing
attaches to the app, so a router registered only there is dead — the whole data-issues
feature 404'd that way while the frontend called it and zero backend tests noticed. This
walks the real route table (lazy `_IncludedRouter` wrappers included — see
test_dataset_routes_are_metered.py) and fails on any route module that is not mounted,
unless it is allow-listed here with the reason.
"""
import pkgutil

from fastapi.routing import APIRoute

import app.api.routes as routes_pkg
from app.main import app

#: Route modules that are deliberately NOT mounted. Each carries its reason; a new dead
#: module must be added here consciously or this test fails.
_UNMOUNTED_ON_PURPOSE = {
    # CRUD over the legacy `TrainedModel` document. No frontend caller (grep
    # `trained-model|trained_model` in apps/frontend finds nothing); the real trained-model
    # surface is `MLModel` under /api/v1/ml (CLAUDE.md "Two model surfaces"). Mounted only on
    # the dead aggregator; removal belongs to #530.
    "trained_model": "legacy TrainedModel CRUD, superseded by /api/v1/ml; removal tracked in #530",
}


def _mounted_modules() -> set[str]:
    found: set[str] = set()

    def walk(routes) -> None:
        for route in routes:
            if type(route).__name__ == "_IncludedRouter":
                walk(route.original_router.routes)
            elif isinstance(route, APIRoute):
                found.add(route.endpoint.__module__.rsplit(".", 1)[-1])

    walk(app.routes)
    return found


def _route_modules() -> set[str]:
    return {m.name for m in pkgutil.iter_modules(routes_pkg.__path__) if not m.name.startswith("_")}


def test_the_walk_sees_the_app():
    assert len(_mounted_modules()) > 10


def test_every_route_module_is_mounted_or_allow_listed():
    missing = _route_modules() - _mounted_modules() - set(_UNMOUNTED_ON_PURPOSE)
    assert not missing, (
        f"Route module(s) with no route on the live app: {sorted(missing)}. Mount them in "
        f"app/main.py (the api_router aggregator in app/api/routes/__init__.py is attached to "
        f"nothing), or add them to _UNMOUNTED_ON_PURPOSE with the reason."
    )


def test_the_allow_list_is_not_stale():
    stale = set(_UNMOUNTED_ON_PURPOSE) & _mounted_modules()
    assert not stale, f"{sorted(stale)} are mounted now; drop them from _UNMOUNTED_ON_PURPOSE"
