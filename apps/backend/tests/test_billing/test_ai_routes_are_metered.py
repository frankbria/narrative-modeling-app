"""Every route under `/api/v1/ai` must charge the `ai_calls` quota (#461).

Same shape as `test_dataset_routes_are_metered.py`: walk the live route table and fail
on any AI route this file has no opinion about. All methods are in scope, not just
POST — `GET /insights/{file_id}` is one of the four.

The two 501 stubs (`/insights`, `/chat/{file_id}`, #274) are metered on purpose: the
refund middleware hands the unit back on 501 today, and when #274 lands a real model
call behind them the guard is already there rather than one more thing to remember.
"""
import pytest

from tests.test_billing.test_dataset_routes_are_metered import (
    _metered_metric,
    _post_routes,
)

_PREFIX = "/api/v1/ai"
_MUST_BE_METERED = {
    "/api/v1/ai/analyze/{file_id}",
    "/api/v1/ai/insights/{file_id}",
    "/api/v1/ai/chat/{file_id}",
    "/api/v1/ai/chat",  # the frontend proxy forwards here (#461)
    "/api/v1/ai/summarize/{file_id}",
    # ai_orchestration.py: rule-based core, but an OpenAI pass "enhances the summary
    # when a key is present" — a paid call is a paid call, and #461 undercounted
    # these (this registry found them).
    "/api/v1/ai/recommend-tools",
    "/api/v1/ai/stage-guidance",
}
_EXEMPT = {
    "/api/v1/ai/health": "MCP liveness probe; calls no model.",
    "/api/v1/ai/feedback": "Persists a recommendation rating; calls no model.",
    "/api/v1/ai/optimize-parameters": "Rule-based only; never touches the OpenAI client.",
}


def _ai_routes():
    return _post_routes(prefixes=(_PREFIX,), exact="", methods=("GET", "POST", "PUT", "PATCH", "DELETE"))


def test_the_ai_route_table_is_not_empty():
    assert len(_ai_routes()) >= 5


@pytest.mark.parametrize("path", sorted(_MUST_BE_METERED))
def test_an_ai_route_charges_ai_calls(path):
    routes = _ai_routes()
    assert path in routes, f"{path} is no longer mounted; update this registry"
    assert _metered_metric(routes[path]) == "ai_calls", (
        f"{path} reaches (or is written to reach) a paid model call and must carry "
        f"quota(\"ai_calls\") as a route dependency"
    )


def test_no_ai_route_is_unaccounted_for():
    unaccounted = set(_ai_routes()) - _MUST_BE_METERED - set(_EXEMPT)
    assert not unaccounted, (
        f"New route(s) under {_PREFIX}: {sorted(unaccounted)}. Add each to _MUST_BE_METERED "
        f"with quota(\"ai_calls\"), or to _EXEMPT with the reason it calls no model."
    )
