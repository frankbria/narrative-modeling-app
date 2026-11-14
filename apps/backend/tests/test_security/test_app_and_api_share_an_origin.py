"""#1206: a job mail links the app at the API's own origin (`job_notifications._app_url`).

That holds while both are served from one host. If a deploy template ever splits them,
this fails, and the mail needs the app's own setting first.
"""

from urllib.parse import urlsplit

import pytest

from tests.test_security.test_env_templates import PRODUCTION, STAGING, _values


def _origin(url: str) -> tuple[str, str]:
    parts = urlsplit(url)
    return parts.scheme, parts.netloc


@pytest.mark.parametrize("template", [STAGING, PRODUCTION], ids=lambda path: path.name)
def test_the_app_and_the_api_share_an_origin(template):
    values = _values(template)

    assert _origin(values["NEXT_PUBLIC_API_URL"]) == _origin(values["NEXTAUTH_URL"])
