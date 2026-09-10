"""Every route that creates a dataset must charge the `uploads` quota (#459).

This is a *registry* test, not one test per route, and the difference is the point.
Per-route tests only cover routes somebody thought to write one for — which is exactly
how several dataset-creating routes ended up unmetered while the metering tests looked
healthy, because the one route they exercised (`/datasets/upload`) is one the UI never
calls.

So the assertion runs the other way round: walk the app's real route table and fail on
any POST route **under the prefixes listed in `_IN_SCOPE_PREFIXES`** that this file has
no opinion about. A new route under one of those then fails here, with instructions,
rather than silently joining the gap.

That scope is the honest limit of this test, and it is worth stating rather than
implying it covers everything: a dataset-creating route mounted on some *other* prefix
is invisible here. That is not hypothetical — the onboarding sample-dataset loader was
exactly that, creating a full UserData row per call with no guard, and a review caught it
only because a human went looking outside the prefixes. When a new router starts creating
datasets, add its prefix here.

Enforcement is the only thing that counts these metrics (CLAUDE.md) — an unguarded route
is not "counted later", it is never counted at all, and the limit becomes advisory.
"""

import pytest
from fastapi.routing import APIRoute

from app.main import app

#: Prefixes whose POST routes are in scope, plus store.py's bare-prefix route, which
#: has to match exactly or the whole API would be in scope.
_IN_SCOPE_PREFIXES = (
    "/api/v1/upload",
    "/api/v1/datasets",
    # Not an upload surface by name, but `sample-datasets/{id}/load` creates a real
    # dataset row, so the whole prefix is policed rather than that one path.
    "/api/v1/onboarding",
)
_STORE_ROUTE = "/api/v1/"

#: POST routes that create a dataset and MUST carry `quota("uploads")` as a route
#: dependency.
_MUST_BE_METERED = {
    "/api/v1/datasets/upload",
    "/api/v1/upload/secure",
    "/api/v1/upload/confirm-pii-upload",
    "/api/v1/upload/chunked/{session_id}/complete",
    "/api/v1/upload/",
    # store.py cannot actually persist today — the UserData it builds passes
    # `file_name`/`headers`/`data`, which are not model fields, so it raises before
    # `.insert()` and the bare `except` turns that into the 500 of #472. Metered anyway:
    # the handler is *written* to create a dataset, so exempting it would let #472's fix
    # silently reopen this hole. The reserve is refunded by the 500 in the meantime.
    "/api/v1/",
    # A sample load is a real dataset: a full UserData row with rows, columns, schema
    # and a preview, which the tenant then uses like any other. The insert is
    # unconditional — the `sample_datasets_loaded` check afterwards only guards a
    # bookkeeping list — so calling it N times creates N datasets. Unmetered it was an
    # unlimited mint past the cap, which is the whole bug class of #459. It costs the
    # tenant one of FREE's 20 uploads, and it is a deliberate click (the user picks a
    # dataset in SampleDatasetSelector), not something onboarding does to them.
    "/api/v1/onboarding/sample-datasets/{dataset_id}/load",
}

#: Routes that create a dataset only on a branch, so they reserve inside the handler
#: rather than through a route dependency. Charging every call would bill work that is
#: not an upload.
_CONDITIONALLY_METERED = {
    # `create_new_dataset` defaults to false; when true this calls the same
    # `DatasetService.create_dataset` as `/datasets/upload`.
    "/api/v1/datasets/{dataset_id}/features/{feature_id}/apply",
}

#: In-scope POST routes that create no dataset. Each carries the reason, because
#: "it looked fine" is how the original gap survived review.
_EXEMPT = {
    "/api/v1/upload/chunked/init": "Opens a session; the unit is charged at /complete.",
    "/api/v1/upload/chunked/{session_id}/chunk/{chunk_number}": (
        "Transfers bytes into an already-admitted session."
    ),
    "/api/v1/datasets/{dataset_id}/versions": (
        "A version of a dataset the tenant already paid to upload."
    ),
    "/api/v1/datasets/{dataset_id}/erase": "Deletes.",
    "/api/v1/datasets/{dataset_id}/process": "Processes the dataset in place.",
    "/api/v1/datasets/{dataset_id}/features": "Defines a Feature, not a dataset.",
    "/api/v1/datasets/{dataset_id}/transformations/preview": "Preview; persists nothing.",
    # The feature compute/inspect family: all of these load a dataframe, compute, and
    # return. Note `features/apply` and `features/apply-multiple` here are
    # feature_engineering.py's in-memory versions — distinct from features.py's
    # `{feature_id}/apply` above, which does persist.
    "/api/v1/datasets/{dataset_id}/features/apply": "Computes in memory; returns.",
    "/api/v1/datasets/{dataset_id}/features/apply-multiple": "Computes in memory.",
    "/api/v1/datasets/{dataset_id}/features/compare": "Read-only comparison.",
    "/api/v1/datasets/{dataset_id}/features/importance": "Read-only scoring.",
    "/api/v1/datasets/{dataset_id}/features/preview": "Preview; persists nothing.",
    "/api/v1/datasets/{dataset_id}/features/redundancy": "Read-only analysis.",
    "/api/v1/datasets/{dataset_id}/features/select": "Read-only selection.",
    "/api/v1/datasets/{dataset_id}/features/suggest": "Read-only suggestion.",
    "/api/v1/datasets/{dataset_id}/features/suggest-more": "Read-only suggestion.",
    "/api/v1/datasets/{dataset_id}/features/validate": "Read-only validation.",
    # Onboarding bookkeeping. All three reach `_save_user_progress`, which touches a
    # UserData used purely as a progress carrier — no s3_url, no rows, no dataset.
    "/api/v1/onboarding/steps/{step_id}/complete": "Records progress.",
    "/api/v1/onboarding/skip-step/{step_id}": "Records progress.",
    "/api/v1/onboarding/reset": "Clears progress.",
}


def _post_routes() -> dict[str, APIRoute]:
    """Every mounted POST route on a dataset-owning router, by path.

    `app.routes` is **not** a flat list on this FastAPI version (0.139): routers are
    included lazily as `_IncludedRouter` wrappers, so iterating `app.routes` and
    filtering for `APIRoute` finds only the handful declared on the app itself and
    silently reports that nothing is metered. Ask an empty route table whether every
    upload route is guarded and it says yes.

    Walking `original_router.routes` through the wrappers is what actually enumerates
    them. Reading the live app rather than importing the routers matters too: this repo
    has a router aggregator (`app/api/routes/__init__.py`) that is mounted nowhere
    (#530), so importing routers would police dead code and miss live code.
    """
    found: dict[str, APIRoute] = {}

    def walk(routes, prefix: str = "") -> None:
        for route in routes:
            if type(route).__name__ == "_IncludedRouter":
                context = getattr(route, "include_context", None)
                walk(
                    route.original_router.routes,
                    prefix + (getattr(context, "prefix", "") or ""),
                )
            elif isinstance(route, APIRoute) and "POST" in (route.methods or ()):
                path = prefix + route.path
                if path == _STORE_ROUTE or path.startswith(_IN_SCOPE_PREFIXES):
                    found[path] = route

    walk(app.routes)
    return found


def _metered_metric(route: APIRoute) -> str | None:
    """Which metric this route's `quota(...)` dependency charges, if any.

    Reads the marker `quota()` stamps on its closure; digging through `__closure__`
    positionally would break the first time that function grows a free variable.
    """
    for dependency in route.dependencies:
        metric = getattr(dependency.dependency, "__quota_metric__", None)
        if metric:
            return metric
    return None


def test_the_route_table_is_not_empty():
    """The registry's own smoke test.

    Every assertion below is of the form "nothing in this set is wrong", which an empty
    set satisfies. If the walk above ever stops finding routes — a FastAPI change to
    lazy inclusion would do it — this file would go green while enforcing nothing.
    """
    assert len(_post_routes()) > 10


class TestEveryDatasetRouteIsMetered:
    @pytest.mark.parametrize("path", sorted(_MUST_BE_METERED))
    def test_a_dataset_creating_route_charges_uploads(self, path):
        routes = _post_routes()
        assert path in routes, (
            f"{path} is no longer a mounted POST route. If it moved, update "
            f"_MUST_BE_METERED; if it was deleted, remove it."
        )
        assert _metered_metric(routes[path]) == "uploads", (
            f"POST {path} creates a dataset but does not carry "
            f'dependencies=[Depends(quota("uploads"))].'
        )

    def test_no_upload_route_is_unaccounted_for(self):
        """The guard that makes this a registry rather than a list.

        A new POST route on these routers is unmetered the moment it exists, and
        nothing else in the suite would notice.
        """
        known = _MUST_BE_METERED | _CONDITIONALLY_METERED | set(_EXEMPT)
        unaccounted = set(_post_routes()) - known

        assert not unaccounted, (
            f"New POST route(s) on a dataset-owning router: {sorted(unaccounted)}.\n"
            "Decide which this is and record it here:\n"
            '  * always creates a dataset -> add dependencies=[Depends(quota("uploads"))]'
            " and add the path to _MUST_BE_METERED;\n"
            "  * creates one on a branch -> reserve inside the handler and add it to "
            "_CONDITIONALLY_METERED;\n"
            "  * creates none -> add it to _EXEMPT with the reason."
        )

    def test_the_registry_does_not_name_routes_that_are_gone(self):
        """A stale entry reads to the next person as evidence the question was
        considered for a route that no longer exists."""
        live = set(_post_routes())
        stale = (_MUST_BE_METERED | _CONDITIONALLY_METERED | set(_EXEMPT)) - live
        assert not stale, f"registry names routes that no longer exist: {sorted(stale)}"

    def test_the_three_categories_do_not_overlap(self):
        assert not (_MUST_BE_METERED & _CONDITIONALLY_METERED)
        assert not (_MUST_BE_METERED & set(_EXEMPT))
        assert not (_CONDITIONALLY_METERED & set(_EXEMPT))

    @pytest.mark.parametrize("path", sorted(_CONDITIONALLY_METERED))
    def test_a_conditional_route_does_not_also_carry_a_route_dependency(self, path):
        """Both would charge twice on the branch that creates a dataset."""
        routes = _post_routes()
        assert path in routes
        assert _metered_metric(routes[path]) is None


class TestNoRouteDoubleCounts:
    """Enforcement reserves; a guarded route must not also `record()` (CLAUDE.md)."""

    def test_no_metered_upload_route_also_records(self):
        import inspect

        offenders = []
        for path, route in _post_routes().items():
            if _metered_metric(route) is None:
                continue
            try:
                source = inspect.getsource(route.endpoint)
            except OSError:  # pragma: no cover - source is always available in-tree
                continue
            if "metering.record(" in source:
                offenders.append(path)

        assert not offenders, (
            f"{offenders} both reserve (via quota) and record. Enforcement already "
            f"counted the unit; recording again double-charges."
        )
