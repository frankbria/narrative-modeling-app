"""Every route is authenticated, or public on purpose (#914).

Routers are mounted without router-level dependencies, so a handler that omits
`Depends(get_current_user_id)` is public by construction (#450, #563). That has
shipped three times: the A/B endpoints, `/ai/health`, and the three routes #914
closed, one of which returned other accounts' recipes and their owners' ids to
anyone. Each was found by reading; nothing failed.

This walks the live route table (lazy `_IncludedRouter` wrappers included) and
follows each route's dependency tree. A route is authenticated when the tree
reaches a session, an API key or the admin allow-list, including through a
router-level dependency. Anything else must be listed here with its reason.
"""

from fastapi.routing import APIRoute

from app.api.routes.production import verify_api_key
from app.auth.nextauth_auth import get_current_user_id, require_admin
from app.main import app

_GATES = {get_current_user_id, verify_api_key, require_admin}

#: `module.function` of every handler that takes no credentials, and why that is
#: right. A new public route has to be added here on purpose.
_PUBLIC_ON_PURPOSE = {
    "main.root": "service banner; no data",
    "main.get_published_openapi": "the published API description (#512)",
    "main.get_published_openapi_yaml": "the published API description (#512)",
    "health.health_check": "liveness for load balancers and uptime monitors",
    "health.liveness_v1": "liveness under /api/v1, for the same callers",
    "health.liveness_check": "liveness for the container healthcheck",
    "health.readiness_check": "readiness: MongoDB only, no third-party call (#503)",
    "billing_webhook.stripe_webhook": "authenticated by Stripe's signature, not a session",
    "user_data.create_user_data_gone": "retired route, answers 410 (#451)",
    "models.train_model": "legacy ModelConfig route, answers 410",
    "models.deploy_model": "legacy ModelConfig route, answers 410",
    "models.get_model_performance": "legacy ModelConfig route, answers 410",
}


def _routes(routes):
    for route in routes:
        if type(route).__name__ == "_IncludedRouter":
            yield from _routes(route.original_router.routes)
        elif isinstance(route, APIRoute):
            yield route


def _dependency_calls(dependant):
    yield dependant.call
    for sub in dependant.dependencies:
        yield from _dependency_calls(sub)


def _name(route: APIRoute) -> str:
    return f"{route.endpoint.__module__.rsplit('.', 1)[-1]}.{route.endpoint.__name__}"


def _unauthenticated() -> set[str]:
    return {
        _name(route)
        for route in _routes(app.routes)
        if not _GATES & set(_dependency_calls(route.dependant))
    }


def test_the_walk_sees_the_app():
    assert len(list(_routes(app.routes))) > 150
    assert "ml_model" not in _unauthenticated()  # sanity: names are module.function


def test_every_route_is_authenticated_or_public_on_purpose():
    unexpected = _unauthenticated() - set(_PUBLIC_ON_PURPOSE)

    assert not unexpected, (
        f"Handler(s) that take no credentials: {sorted(unexpected)}. Add "
        "`current_user_id: str = Depends(get_current_user_id)` (routers carry no "
        "router-level auth), or list the handler in _PUBLIC_ON_PURPOSE with the reason."
    )


#: What FastAPI mounts itself: the interactive docs and the raw document. Public by design.
_FRAMEWORK_ROUTES = {"/api/v1/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"}


def _outside_the_walk(routes) -> set[str]:
    """Routes the walk cannot follow: a mount, a websocket, a bare Starlette route."""
    found: set[str] = set()
    for route in routes:
        if type(route).__name__ == "_IncludedRouter":
            found |= _outside_the_walk(route.original_router.routes)
        elif not isinstance(route, APIRoute):
            found.add(getattr(route, "path", repr(route)))
    return found


def test_nothing_is_served_outside_the_walk():
    """A route added with `app.mount`, `add_route` or a websocket has no dependency
    tree to read, so it would pass this file unseen. It has to be named here first."""
    assert _outside_the_walk(app.routes) == _FRAMEWORK_ROUTES


def test_the_public_list_is_not_stale():
    """An entry that has gained auth, or no longer exists, comes off the list."""
    stale = set(_PUBLIC_ON_PURPOSE) - _unauthenticated()

    assert not stale, f"No longer public, or gone: {sorted(stale)}"


def test_a_router_level_dependency_counts():
    """The admin router guards at the router, on purpose (#769)."""
    admin = [r for r in _routes(app.routes) if r.endpoint.__module__.endswith("routes.admin")]

    assert admin and all(require_admin in set(_dependency_calls(r.dependant)) for r in admin)
