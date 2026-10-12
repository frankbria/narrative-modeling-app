"""#512: the published API description states what the running app does.

The old service layered hand-written claims over the generated document: a blanket
authentication rule, rate limits no code enforced, an MIT licence, a production
host on a domain the product does not own, and whole client libraries for
endpoints that do not exist. These tests hold the description to the app itself.
"""

import json
import re

import pytest
from starlette.routing import Match

from app.billing.plans import PLAN_LIMITS
from app.config import settings
from app.main import app
from app.models.subscription import PlanTier
from app.services.api_documentation import api_description, published_spec

BASE_URL = "https://api.example.test"


@pytest.fixture(scope="module")
def spec() -> dict:
    return published_spec(app, BASE_URL)


def _is_served(path: str, method: str) -> bool:
    """Whether the live route table answers this method on this path."""
    scope = {"type": "http", "path": re.sub(r"\{[^}]+\}", "x", path), "method": method.upper()}
    return any(route.matches(scope)[0] == Match.FULL for route in app.routes)


def test_every_documented_operation_is_a_live_route(spec):
    operations = [
        (path, method)
        for path, item in spec["paths"].items()
        for method in item
        if method in {"get", "post", "put", "patch", "delete"}
    ]

    assert len(operations) > 100  # the whole API, not a hand-picked subset
    assert [op for op in operations if not _is_served(*op)] == []


def test_the_document_is_the_apps_own_route_table(spec):
    assert spec["paths"] == app.openapi()["paths"]
    assert spec["components"] == app.openapi()["components"]


def test_building_the_document_does_not_change_the_apps_cached_one():
    published_spec(app, BASE_URL)

    assert app.openapi()["info"].get("description") is None
    assert "servers" not in app.openapi()


def test_the_description_names_no_path_the_app_does_not_serve():
    paths = set(re.findall(r"`(?:GET|POST|PUT|PATCH|DELETE) (/[^`\s]+)`", api_description()))

    assert paths, "the description should point at real routes"
    for path in paths:
        assert any(_is_served(path, method) for method in ("GET", "POST")), path


@pytest.fixture
def limiter_on(monkeypatch):
    """The test environment runs with the limiter off, as the middleware reads it."""
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)


def test_the_rate_limits_are_the_ones_enforced(limiter_on):
    text = api_description()

    assert (
        f"{settings.RATE_LIMIT_DEFAULT_REQUESTS} requests per "
        f"{settings.RATE_LIMIT_DEFAULT_WINDOW_SECONDS} seconds"
    ) in text
    for tier in PlanTier:
        assert f"{tier.value.capitalize()}: {PLAN_LIMITS[tier].api_key_rate_limit:,}" in text
    # The numbers the old description advertised and nothing enforced.
    assert "100 requests/hour" not in text and "Custom limits" not in text


def test_the_description_follows_the_settings(monkeypatch, limiter_on):
    monkeypatch.setattr(settings, "RATE_LIMIT_DEFAULT_REQUESTS", 7)
    monkeypatch.setattr(settings, "RATE_LIMIT_DEFAULT_WINDOW_SECONDS", 13)

    assert "7 requests per 13 seconds" in api_description()


def test_a_disabled_limiter_is_not_described_as_a_limit(monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", False)

    text = api_description()

    assert "requests per" not in text.split("## API keys")[0].split("## Rate limits")[1]
    assert "not rate limited on this instance" in text


def test_authentication_is_stated_per_route_not_as_a_blanket_rule(spec):
    assert "security" not in spec  # no top-level rule covering every operation

    live = spec["paths"]["/health/live"]["get"]
    assert not live.get("security")
    serving = spec["paths"]["/api/v1/production/v1/models/{model_id}/predict"]["post"]
    assert ("X-API-Key", "header") in [(p["name"], p["in"]) for p in serving["parameters"]]
    training = spec["paths"]["/api/v1/ml/train"]["post"]
    assert training["security"] == [{"HTTPBearer": []}]


def test_the_server_is_the_instance_that_answered(spec):
    assert spec["servers"] == [{"url": BASE_URL, "description": "This instance"}]
    assert published_spec(app, BASE_URL + "/")["servers"][0]["url"] == BASE_URL


def test_the_licence_and_contact_are_the_projects(spec):
    from app.config import SUPPORT_EMAIL

    assert spec["info"]["license"]["name"] == "AGPL-3.0-or-later"
    assert spec["info"]["contact"]["email"] == SUPPORT_EMAIL


def test_nothing_published_names_a_domain_the_product_does_not_own(spec):
    published = json.dumps(spec)

    assert "narrativeml.com" not in published and "narrativemodeling.ai" not in published
