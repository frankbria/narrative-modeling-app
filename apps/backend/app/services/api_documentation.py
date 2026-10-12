"""The published description of the API (#512).

One rule: nothing here is typed by hand that the running app can state itself.
The paths, schemas and each route's own authentication requirement are FastAPI's
generated document, which is the live route table. The rate limits are read from
the settings and the plan table that enforce them. The server is the instance
that answered.

The service this replaces layered claims over that document which were not true:
a rule that every endpoint takes a bearer token or an API key, per-plan rate
limits no code enforced, an MIT licence, a production host on a domain the
product does not own, and client libraries for endpoints that do not exist.

A client for a deployed model is generated per model, against its real serving
URL, by ``sdk_generator.py`` (``GET /api/v1/ml/{model_id}/sdk``).
"""

import copy
from typing import Any

from fastapi import FastAPI

from app.billing.plans import PLAN_LIMITS
from app.config import SUPPORT_EMAIL, settings

_LICENSE = {
    "name": "AGPL-3.0-or-later",
    "url": "https://www.gnu.org/licenses/agpl-3.0.html",
}


def _caller_limit() -> str:
    if not settings.RATE_LIMIT_ENABLED:
        return "Requests under `/api/v1` are not rate limited on this instance."
    return (
        f"Requests under `/api/v1` are counted per caller: "
        f"{settings.RATE_LIMIT_DEFAULT_REQUESTS} requests per "
        f"{settings.RATE_LIMIT_DEFAULT_WINDOW_SECONDS} seconds. A request over the "
        "limit is answered `429` with a `Retry-After` header, and every allowed "
        "response carries `X-RateLimit-Limit`, `X-RateLimit-Remaining` and "
        "`X-RateLimit-Reset`."
    )


def _api_key_limits() -> str:
    hours = settings.RATE_LIMIT_APIKEY_WINDOW_SECONDS / 3600
    ceilings = "\n".join(
        f"- {tier.value.capitalize()}: {limits.api_key_rate_limit:,}"
        for tier, limits in PLAN_LIMITS.items()
    )
    return (
        "An API key carries its own limit, set when the key is created and counted "
        f"over {hours:g} hour(s) on the model-serving routes. The most a key may be "
        f"given depends on the account's plan:\n\n{ceilings}"
    )


def api_description() -> str:
    """The prose of the published document, with every number read from what enforces it."""
    return f"""# {settings.PROJECT_NAME}

Upload a dataset, train a model on it, and serve predictions from it.

## Authentication

Each operation below states what it requires.

- The application's own routes take the signed-in session's token:
  `Authorization: Bearer <token>`.
- The model-serving routes, `POST /api/v1/production/v1/models/{{model_id}}/predict`
  and `GET /api/v1/production/v1/models/{{model_id}}/info`, take an API key:
  `X-API-Key: <key>`. Keys are created with `POST /api/v1/production/api-keys`.

## Rate limits

{_caller_limit()}

## API keys

{_api_key_limits()}

## Plan limits

Training runs, predictions, uploads and AI-assisted calls are counted per month
against the account's plan. A request over a plan limit is answered `402` with
the limit, what has been used and when it resets. `GET /api/v1/billing/status`
shows the current counts.

## Versioning

The version is in the path (`/api/v1/...`). It can also be requested with
`Accept: application/vnd.narrativeml.v1+json`.

## Client code for a deployed model

`GET /api/v1/ml/{{model_id}}/sdk` returns client code generated for that model,
pointed at its serving URL.

## Support

{SUPPORT_EMAIL}
"""


def published_spec(app: FastAPI, base_url: str) -> dict[str, Any]:
    """FastAPI's generated document for ``app``, described for the instance at ``base_url``.

    A copy: ``app.openapi()`` caches and returns one dict, which also backs
    ``/api/v1/openapi.json`` and the interactive docs."""
    spec = copy.deepcopy(app.openapi())
    spec["info"]["description"] = api_description()
    spec["info"]["contact"] = {"name": "Support", "email": SUPPORT_EMAIL}
    spec["info"]["license"] = _LICENSE
    spec["servers"] = [{"url": base_url.rstrip("/"), "description": "This instance"}]
    return spec
