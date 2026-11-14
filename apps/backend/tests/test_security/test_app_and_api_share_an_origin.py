"""#1206: a job mail links the app at the API's own origin (`job_notifications._app_url`).

That holds while both are served from one host. If a deploy template ever splits them,
this fails, and the mail needs the app's own setting first.
"""

from urllib.parse import urlsplit

import pytest

from tests.test_security.test_env_templates import (
    COMPOSE_FILE,
    PRODUCTION,
    STAGING,
    _values,
)


def _origin(url: str) -> tuple[str, str]:
    parts = urlsplit(url)
    return parts.scheme, parts.netloc


@pytest.mark.parametrize("template", [STAGING, PRODUCTION], ids=lambda path: path.name)
def test_the_app_and_the_api_share_an_origin(template):
    values = _values(template)

    assert _origin(values["NEXT_PUBLIC_API_URL"]) == _origin(values["NEXTAUTH_URL"])


def test_the_backend_reads_its_public_address_from_the_same_setting():
    """The comparison above holds for the mail only while compose hands the backend the
    frontend's API address as its `PUBLIC_API_URL`."""
    assert "PUBLIC_API_URL: ${NEXT_PUBLIC_API_URL:-}" in COMPOSE_FILE.read_text()
