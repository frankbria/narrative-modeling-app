"""Every route that can reach a paid model call charges `ai_calls` (#461).

Same idea as `test_dataset_routes_are_metered.py` — walk the live route table and fail
on anything this file has no opinion about — but the scope is derived, not listed:

1. a *model module* is any file under `app/` that calls `chat.completions.create`;
2. a *route module* is in scope when its source imports a model module;
3. every route whose handler lives in an in-scope module must be in `_MUST_BE_METERED`
   (with `quota("ai_calls")`) or in `_EXEMPT` with the reason it calls no model.

#461 listed four routes. This walk found eleven more, in three other routers — the
"rule-based" orchestration service takes an OpenAI pass when a key is present, the
feature-suggestion lookups re-run `suggest_features(include_ai=True)` (#522), and the
evaluation report card and error suggestions are OpenAI calls with a rule-based
fallback. A prefix-scoped registry could not have seen any of them.

Scope follows one import hop: a router importing a service that imports a model module
is in scope (#471 made that the common shape). Deeper chains are not followed.
`data_issues.py` reaches `AIIssueAnalyzer` through a lazy import inside its service;
that router is mounted nowhere today (#471), so it is invisible here until #471 mounts
it — at which point the service import should be made direct so this test sees it.
"""
import re
from pathlib import Path

import pytest
from fastapi.routing import APIRoute

from app.main import app

_APP = Path(__file__).resolve().parents[2] / "app"
_MODEL_CALL = re.compile(r"chat\.completions\.create")


def _module_name(path: Path) -> str:
    return ".".join(path.relative_to(_APP.parent).with_suffix("").parts)


def _imports(src: str, mod: str) -> bool:
    pkg, _, name = mod.rpartition(".")
    return re.search(
        rf"^\s*from {re.escape(mod)} import|^\s*from {re.escape(pkg)} import[^\n]*\b{name}\b|^\s*import {re.escape(mod)}\b",
        src, re.M,
    ) is not None


def _model_modules() -> set[str]:
    """Files that call the model, plus files that import one of those (one hop): a route that
    reaches OpenAI through a *service* — data_issues.py via DataIssueDetectionService via
    AIIssueAnalyzer (#471) — is model access too, and the direct-import rule missed it."""
    direct = {_module_name(p) for p in _APP.rglob("*.py") if _MODEL_CALL.search(p.read_text())}
    one_hop = set()
    for p in _APP.rglob("*.py"):
        if "api/routes" in str(p):
            continue
        src = p.read_text()
        if any(_imports(src, mod) for mod in direct):
            one_hop.add(_module_name(p))
    return direct | one_hop


def _route_modules_with_model_access() -> set[str]:
    found = set()
    for p in (_APP / "api" / "routes").glob("*.py"):
        src = p.read_text()
        for mod in _model_modules():
            # `^\s*` on purpose (inside _imports): a lazy import inside a handler is still model access
            if _imports(src, mod):
                found.add(_module_name(p))
                break
    return found


def _in_scope_routes() -> dict[str, APIRoute]:
    modules = _route_modules_with_model_access()
    found: dict[str, APIRoute] = {}

    def walk(routes, prefix: str = "") -> None:
        for route in routes:
            if type(route).__name__ == "_IncludedRouter":
                context = getattr(route, "include_context", None)
                walk(route.original_router.routes, prefix + (getattr(context, "prefix", "") or ""))
            elif isinstance(route, APIRoute) and route.endpoint.__module__ in modules:
                found[prefix + route.path] = route

    walk(app.routes)
    return found


def _metered_metrics(route: APIRoute) -> set[str]:
    return {m for d in route.dependencies if (m := getattr(d.dependency, "__quota_metric__", None))}


_MUST_BE_METERED = {
    # ai_analysis.py — the two 501 stubs (#274) are metered on purpose: the refund
    # middleware hands the unit back today, and the guard is already there when a
    # real model call lands behind them.
    "/api/v1/ai/analyze/{file_id}",
    "/api/v1/ai/insights/{file_id}",
    "/api/v1/ai/chat/{file_id}",
    "/api/v1/ai/chat",  # the frontend proxy forwards here
    "/api/v1/ai/summarize/{file_id}",
    # ai_orchestration.py — rule-based core, OpenAI pass when a key is present
    "/api/v1/ai/recommend-tools",
    "/api/v1/ai/stage-guidance",
    # feature_engineering.py — every one of these reaches suggest_features(include_ai),
    # the lookups included (#522: the cache key mismatch means they re-run the model).
    "/api/v1/datasets/{dataset_id}/features/suggest",
    "/api/v1/datasets/{dataset_id}/features/suggest-more",
    "/api/v1/datasets/{dataset_id}/features/suggestions/{suggestion_id}",
    "/api/v1/features/suggestions/{suggestion_id}/feedback",
    "/api/v1/datasets/{dataset_id}/features/apply",
    "/api/v1/datasets/{dataset_id}/features/apply-multiple",
    # model_training.py — report card / improvement suggestions; both release the
    # unit on the branch that has no artifacts to explain.
    "/api/v1/ml/{model_id}/evaluation",
    "/api/v1/ml/{model_id}/errors",
    # data_issues.py (#471) — detection runs AIIssueAnalyzer (OpenAI) when
    # options.include_ai_analysis, the default; released when it did not run.
    "/api/v1/data-issues/detect",
}

_NO_MODEL_ML = "MLModel CRUD/serving; no LLM call (training and predictions have their own metrics)."
_UPLOAD_SUMMARY = (
    "The upload-time AI summary runs as a background task charged by the `uploads` "
    "unit that starts it, 1:1 — one dataset, one summary."
)
_EXEMPT = {
    "/api/v1/ai/health": "MCP liveness probe; calls no model.",
    "/api/v1/ai/feedback": "Persists a recommendation rating; calls no model.",
    "/api/v1/ai/optimize-parameters": "Rule-based only; never touches the OpenAI client.",
    **{p: "Reads or applies stored detection results; the model ran at /detect." for p in (
        "/api/v1/data-issues/{dataset_id}/issues", "/api/v1/data-issues/{dataset_id}/history",
        "/api/v1/data-issues/preview-fix", "/api/v1/data-issues/apply-fix", "/api/v1/data-issues/batch-fix",
    )},
    **{p: _NO_MODEL_ML for p in (
        "/api/v1/ml/", "/api/v1/ml/compare", "/api/v1/ml/datasets/{dataset_id}/mode-recommendation",
        "/api/v1/ml/jobs", "/api/v1/ml/train", "/api/v1/ml/{model_id}", "/api/v1/ml/{model_id}/cancel",
        "/api/v1/ml/{model_id}/deactivate", "/api/v1/ml/{model_id}/deploy",
        "/api/v1/ml/{model_id}/feature-importance", "/api/v1/ml/{model_id}/features",
        "/api/v1/ml/{model_id}/logs", "/api/v1/ml/{model_id}/predict", "/api/v1/ml/{model_id}/promote",
        "/api/v1/ml/{model_id}/sdk", "/api/v1/ml/{model_id}/sdk/postman", "/api/v1/ml/{model_id}/sdk/{language}",
        "/api/v1/ml/{model_id}/shap", "/api/v1/ml/{model_id}/status", "/api/v1/ml/{model_id}/tuning-results",
        "/api/v1/ml/{model_id}/versions",
    )},
    **{p: _UPLOAD_SUMMARY for p in (
        "/api/v1/upload/", "/api/v1/upload/secure", "/api/v1/upload/confirm-pii-upload",
        "/api/v1/upload/chunked/{session_id}/complete",
    )},
    **{p: "Upload plumbing; no model call." for p in (
        "/api/v1/upload/test", "/api/v1/upload/cleanup", "/api/v1/upload/chunked/init",
        "/api/v1/upload/chunked/{session_id}", "/api/v1/upload/chunked/{session_id}/chunk/{chunk_number}",
        "/api/v1/upload/chunked/{session_id}/resume",
    )},
}


def test_the_scope_is_derived_and_not_empty():
    assert {"app.services.ai_chat", "app.services.feature_engineering_service"} <= _model_modules()
    assert {"app.api.routes.ai_analysis", "app.api.routes.model_training"} <= _route_modules_with_model_access()
    assert len(_in_scope_routes()) >= 40


@pytest.mark.parametrize("path", sorted(_MUST_BE_METERED))
def test_a_model_calling_route_charges_ai_calls(path):
    routes = _in_scope_routes()
    assert path in routes, f"{path} is no longer mounted; update this registry"
    assert "ai_calls" in _metered_metrics(routes[path]), (
        f"{path} reaches (or is written to reach) a paid model call and must carry "
        f'quota("ai_calls") as a route dependency'
    )


def test_no_route_with_model_access_is_unaccounted_for():
    unaccounted = set(_in_scope_routes()) - _MUST_BE_METERED - set(_EXEMPT)
    assert not unaccounted, (
        f"Route(s) in a module that imports a model-calling service: {sorted(unaccounted)}. "
        f'Add each to _MUST_BE_METERED with quota("ai_calls"), or to _EXEMPT with the reason '
        f"it calls no model."
    )


def test_exemptions_are_not_stale():
    stale = set(_EXEMPT) - set(_in_scope_routes())
    assert not stale, f"_EXEMPT lists routes that are gone or out of scope: {sorted(stale)}"
