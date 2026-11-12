"""The frontend's notification-preference body is the API's own request model (#494).

The settings switch builds `PUT /users/me/notification-preferences`'s body by hand and the
model forbids undeclared fields, so a field renamed on one side is a 422 for every save.
The frontend's `notificationPreferences.contract.test.ts` checks the body it builds
against this fixture, and this test keeps the fixture equal to the model the route declares.

Regenerate after a deliberate request-model change:
    UPDATE_FIXTURES=1 PYTHONPATH=. uv run pytest tests/test_api/test_notification_preferences_schema_fixture.py
"""

import json
import os
from pathlib import Path

from app.api.routes.users import NotificationPreferences

FIXTURE = (
    Path(__file__).resolve().parents[4]
    / "apps/frontend/__tests__/fixtures/notificationPreferencesSchema.json"
)


def test_the_frontend_fixture_is_the_api_request_schema():
    schema = NotificationPreferences.model_json_schema()
    if os.getenv("UPDATE_FIXTURES"):
        FIXTURE.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
    assert json.loads(FIXTURE.read_text()) == schema, (
        "regenerate the fixture: the notification preference model changed"
    )


def test_the_route_still_takes_this_model():
    from app.main import app

    # The OpenAPI document, not app.routes: routers are lazy wrappers (#459).
    operation = app.openapi()["paths"]["/api/v1/users/me/notification-preferences"]["put"]
    body = operation["requestBody"]["content"]["application/json"]

    assert body["schema"]["$ref"].rsplit("/", 1)[-1] == NotificationPreferences.__name__
