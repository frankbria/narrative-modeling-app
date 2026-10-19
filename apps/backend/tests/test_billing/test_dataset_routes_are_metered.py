"""Every route that creates a dataset must charge the `uploads` quota (#459).

This is a *registry* test, not one test per route, and the difference is the point.
Per-route tests only cover routes somebody thought to write one for — which is exactly
how several dataset-creating routes ended up unmetered while the metering tests looked
healthy, because the one route they exercised (`/datasets/upload`) is one the UI never
calls.

So the assertion runs the other way round: walk the app's real route table and fail on
any route this file has no opinion about. Two things put a route in scope:

* **where it is mounted**: any POST under the prefixes in `_IN_SCOPE_PREFIXES`; and
* **what it does** (#609): any write route, on any prefix, whose handler can reach the
  construction of a `UserData` or a `DatasetMetadata`. The onboarding sample loader
  created a full dataset row per call on a prefix nobody had listed, and a reviewer
  found it only by looking outside the list. `_chains_to_a_dataset_document` follows
  calls through `app/` so the next one is found by the suite.

The honest limit of the second: it matches calls by **simple name**. Two functions that
share a name share a verdict, so it asks about some routes that are fine (they are in
`_EXEMPT_BY_REACH` with the reason). And a construction reached by something it cannot
read as a call, such as `getattr(module, name)(...)`, is invisible to it.

Enforcement is the only thing that counts these metrics (CLAUDE.md) — an unguarded route
is not "counted later", it is never counted at all, and the limit becomes advisory.
"""

import ast
from pathlib import Path

import pytest
from fastapi.routing import APIRoute

import app as app_package
from app.main import app

#: Prefixes whose POST routes are in scope.
_IN_SCOPE_PREFIXES = (
    "/api/v1/upload",
    "/api/v1/datasets",
    # Not an upload surface by name, but `sample-datasets/{id}/load` creates a real
    # dataset row, so the whole prefix is policed rather than that one path.
    "/api/v1/onboarding",
)

#: POST routes that create a dataset and MUST carry `quota("uploads")` as a route
#: dependency.
_MUST_BE_METERED = {
    "/api/v1/datasets/upload",
    "/api/v1/upload/secure",
    "/api/v1/upload/confirm-pii-upload",
    "/api/v1/upload/chunked/{session_id}/complete",
    "/api/v1/upload/",
    # A sample load creates a real UserData row — rows, columns, schema, preview — and
    # the insert is unconditional: the `sample_datasets_loaded` check afterwards only
    # guards a bookkeeping list, so calling it N times creates N rows. Unmetered that
    # was an unlimited mint past the cap, which is the bug class of #459. It costs one
    # of FREE's 20 uploads, and it is a deliberate click (the user picks a dataset in
    # SampleDatasetSelector) rather than something onboarding does to them.
    #
    # Not claiming more than is true: the row's `s3_url` is fabricated and no file is
    # ever uploaded (#541), so this is not yet a dataset the tenant can *use* like any
    # other. It is metered for what it creates and for the mint, not on the strength of
    # that row being sound.
    "/api/v1/onboarding/sample-datasets/{dataset_id}/load",
}

#: In-scope POST routes that create no dataset. Each carries the reason, because
#: "it looked fine" is how the original gap survived review.
_EXEMPT = {
    "/api/v1/upload/chunked/init": "Opens a session; the unit is charged at /complete.",
    "/api/v1/upload/chunked/{session_id}/chunk/{chunk_number}": (
        "Transfers bytes into an already-admitted session."
    ),
    "/api/v1/datasets/{dataset_id}/erase": "Deletes.",
    "/api/v1/datasets/{dataset_id}/process": "Processes the dataset in place.",
    # Onboarding bookkeeping. All three reach `_save_user_progress`, which touches a
    # UserData used purely as a progress carrier — no s3_url, no rows, no dataset.
    "/api/v1/onboarding/steps/{step_id}/complete": "Records progress.",
    "/api/v1/onboarding/skip-step/{step_id}": "Records progress.",
    "/api/v1/onboarding/reset": "Clears progress.",
}


#: Why most routes found by reach are fine: they resolve the dataset they act on through
#: `dataset_link.ensure_metadata_twin`, which creates the `DatasetMetadata` twin of an
#: upload the first time a transformation touches it (#850).
_TWIN = "Creates at most the DatasetMetadata twin of an upload already charged at upload (#850)."

#: Write routes outside `_IN_SCOPE_PREFIXES` whose handler can reach a dataset document,
#: and why each creates no new dataset.
_EXEMPT_BY_REACH = {
    "/api/v1/transformations/apply": _TWIN,
    "/api/v1/transformations/preview": _TWIN,
    "/api/v1/transformations/pipeline/apply": _TWIN,
    "/api/v1/transformations/auto-clean": _TWIN,
    "/api/v1/transformations/recipes/{recipe_id}/apply": _TWIN,
    "/api/v1/transformations/datasets/{dataset_id}/history/undo": _TWIN,
    "/api/v1/transformations/datasets/{dataset_id}/history/redo": _TWIN,
    "/api/v1/transformations/datasets/{dataset_id}/history/jump": _TWIN,
}


def _post_routes(
    prefixes: tuple[str, ...] = _IN_SCOPE_PREFIXES,
    methods: tuple[str, ...] = ("POST",),
) -> dict[str, APIRoute]:
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
            elif isinstance(route, APIRoute) and set(methods) & (route.methods or set()):
                path = prefix + route.path
                if path.startswith(prefixes):
                    found[path] = route

    walk(app.routes)
    return found


#: The documents a dataset is. A handler that can construct one may be creating a dataset.
_DATASET_DOCUMENTS = {"UserData", "DatasetMetadata"}
_APP_DIR = Path(app_package.__file__).parent


def _called_names(function: ast.AST) -> set[str]:
    """The simple names a function calls: `f(...)` and `anything.f(...)` both give `f`."""
    names = set()
    for node in ast.walk(function):
        if isinstance(node, ast.Call):
            target = node.func
            names.add(getattr(target, "id", None) or getattr(target, "attr", None))
    return names - {None}


def _call_index() -> dict[str, set[str]]:
    """Every function and method under app/, by simple name, with the names it calls."""
    index: dict[str, set[str]] = {}
    for path in _APP_DIR.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                index.setdefault(node.name, set()).update(_called_names(node))
    return index


def _chains_to_a_dataset_document() -> dict[str, list[str]]:
    """Each function name that can reach the construction of a dataset document, with
    one chain of calls that gets there (`[name, ..., "UserData"]`).

    By simple name, so it over-reaches: two functions that share a name share a verdict.
    That errs toward asking about a route that is fine, which costs one line in
    `_EXEMPT_BY_REACH`; the other direction is the bug this file exists for.
    """
    index = _call_index()
    chains: dict[str, list[str]] = {document: [document] for document in _DATASET_DOCUMENTS}
    while _extend(chains, index):
        pass
    return chains


def _extend(chains: dict[str, list[str]], index: dict[str, set[str]]) -> bool:
    """One pass: a chain for every function that calls one which already has one.
    True while that still adds any."""
    added = {
        name: [name, *chains[via]]
        for name, called in index.items()
        if name not in chains
        for via in sorted(called & chains.keys())[:1]
    }
    chains.update(added)
    return bool(added)


def _routes_that_can_create_a_dataset() -> dict[str, list[str]]:
    """Every mounted write route, on any prefix, whose handler can reach one: path -> chain."""
    chains = _chains_to_a_dataset_document()
    routes = _post_routes(prefixes=("",), methods=("POST", "PUT", "PATCH"))
    return {
        path: chains[route.endpoint.__name__]
        for path, route in routes.items()
        if route.endpoint.__name__ in chains
    }


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
        known = _MUST_BE_METERED | set(_EXEMPT)
        unaccounted = set(_post_routes()) - known

        assert not unaccounted, (
            f"New POST route(s) on a dataset-owning router: {sorted(unaccounted)}.\n"
            "Decide which this is and record it here:\n"
            '  * always creates a dataset -> add dependencies=[Depends(quota("uploads"))]'
            " and add the path to _MUST_BE_METERED;\n"
            "  * creates none -> add it to _EXEMPT with the reason."
        )

    def test_the_reachability_pass_finds_what_is_known_to_create_datasets(self):
        """Its own smoke test: an empty or blind pass would report nothing to classify."""
        chains = _chains_to_a_dataset_document()
        assert {"create_dataset", "_create_twin", "secure_upload", "load_sample_dataset"} <= set(chains)
        # Every route listed as a creator is one the pass would have found unlisted.
        assert _MUST_BE_METERED <= set(_routes_that_can_create_a_dataset())

    def test_no_route_on_any_prefix_that_can_create_a_dataset_is_unaccounted_for(self):
        """#609: scope by what a handler can do, wherever it is mounted."""
        known = _MUST_BE_METERED | set(_EXEMPT) | set(_EXEMPT_BY_REACH)
        found = _routes_that_can_create_a_dataset()
        unaccounted = {path: " -> ".join(chain) for path, chain in found.items() if path not in known}

        assert not unaccounted, (
            "Write route(s) whose handler can reach the construction of a dataset document, "
            "with the calls that lead there:\n"
            + "\n".join(f"  {path}\n    {chain}" for path, chain in sorted(unaccounted.items()))
            + "\nDecide which each is and record it here:\n"
            '  * always creates a dataset -> add dependencies=[Depends(quota("uploads"))]'
            " and add the path to _MUST_BE_METERED;\n"
            "  * creates none (the chain is a twin of an existing upload, or only a shared "
            "function name) -> add it to _EXEMPT_BY_REACH with the reason."
        )

    def test_no_exemption_by_reach_outlives_its_reason(self):
        """An entry for a route the pass no longer flags reads as a question considered
        for a route that never raised it."""
        stale = set(_EXEMPT_BY_REACH) - set(_routes_that_can_create_a_dataset())
        assert not stale, f"no longer reachable, drop from _EXEMPT_BY_REACH: {sorted(stale)}"

    def test_the_registry_does_not_name_routes_that_are_gone(self):
        """A stale entry reads to the next person as evidence the question was
        considered for a route that no longer exists."""
        live = set(_post_routes())
        stale = (_MUST_BE_METERED | set(_EXEMPT)) - live
        assert not stale, f"registry names routes that no longer exist: {sorted(stale)}"

    def test_the_categories_do_not_overlap(self):
        assert not (_MUST_BE_METERED & set(_EXEMPT))
        assert not (set(_EXEMPT_BY_REACH) & (_MUST_BE_METERED | set(_EXEMPT)))


class TestEveryUploadEnforcesTheStorageCeiling:
    """#768 AC5: every route that creates a dataset from caller bytes checks the FREE
    storage ceiling before storing them. Read from source, one hop deep for the
    onboarding loader whose bytes only exist inside the service."""

    #: Where the check lives when it is not in the handler itself.
    _VIA = {
        "/api/v1/onboarding/sample-datasets/{dataset_id}/load": (
            # The loader's upload step (split out of load_sample_dataset in #808).
            "app.services.onboarding_service", "_upload_sample",
        ),
        # Split out of the handler in #1062.
        "/api/v1/upload/chunked/{session_id}/complete": (
            "app.api.routes.secure_upload", "_admit_assembled",
        ),
    }

    def test_each_metered_upload_calls_the_check(self):
        import importlib
        import inspect

        routes = _post_routes()
        missing = []
        for path in _MUST_BE_METERED:
            if path in self._VIA:
                module, qualname = self._VIA[path]
                target = importlib.import_module(module)
                for part in qualname.split("."):
                    target = getattr(target, part)
            else:
                target = routes[path].endpoint
            if "enforce_storage_ceiling(" not in inspect.getsource(target):
                missing.append(path)
        assert not missing, f"dataset-creating routes without the storage check: {missing}"


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


class TestBatchRetryMetersTheRightMetric:
    """The retry route charges `predictions` from `progress.total_records`, for every
    `BatchJob` regardless of `job_type` (#460).

    That is correct only while every BatchJob *is* a batch prediction. `JobType` also
    declares `MODEL_TRAINING` and `DATA_PROCESSING`, and if either were ever wired up to
    this same document and retry route, the endpoint would silently meter the wrong
    metric — a training re-run billed as N predictions. Nothing today creates those, so
    this pins the assumption instead of adding an unreachable runtime branch: wire up a
    second job type and this fails, forcing the metering question to be answered rather
    than inherited.
    """

    def test_every_batch_job_created_is_a_batch_prediction(self):
        import ast
        import inspect
        import textwrap

        from app.services import batch_prediction

        tree = ast.parse(textwrap.dedent(inspect.getsource(batch_prediction)))
        constructions = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "BatchJob"
        ]
        assert constructions, "no BatchJob(...) found — did the module move?"

        for call in constructions:
            job_type = next(
                (kw.value for kw in call.keywords if kw.arg == "job_type"), None
            )
            rendered = ast.unparse(job_type) if job_type is not None else "<missing>"
            assert rendered == "JobType.BATCH_PREDICTION", (
                f"BatchJob created with job_type={rendered} at relative line "
                f"{call.lineno}. The retry route meters every BatchJob as "
                f"`predictions` sized by progress.total_records — decide what this "
                f"type should charge before letting it reach that route."
            )
