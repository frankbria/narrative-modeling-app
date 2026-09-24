"""#770 AC3: every link the onboarding surface hands the user resolves inside the app.

Before #770 onboarding pointed at `/videos/welcome-intro` (no such file), a
`docs.narrativemodeling.ai` domain referenced nowhere else, a sample-download
route that was never mounted, a `/support/chat` page that does not exist and a
support mailbox on a domain the company does not use. This walks everything the
service and the help-tips route return and fails on any URL that is not a page
the frontend actually has.
"""

import asyncio
import re
from pathlib import Path
from typing import Any

import pytest

from app.config import SUPPORT_EMAIL
from app.services.onboarding_service import OnboardingService

_FRONTEND = Path(__file__).resolve().parents[3] / "frontend"
_BACKEND_APP = Path(__file__).resolve().parents[2] / "app"


def _urls(value: Any, key: str = "") -> list[str]:
    """Every string stored under a key ending in `url` (or `docs`), at any depth."""
    if isinstance(value, dict):
        return [u for k, v in value.items() for u in _urls(v, k)]
    if isinstance(value, list):
        return [u for v in value for u in _urls(v, key)]
    if isinstance(value, str) and (key.endswith("url") or key in {"docs", "chat"}):
        return [value]
    return []


def _resolves_to_a_frontend_page(url: str) -> bool:
    if not url.startswith("/") or url.startswith("//"):
        return False
    path = url.split("?", 1)[0].split("#", 1)[0].rstrip("/")
    return (_FRONTEND / "app" / path.lstrip("/") / "page.tsx").is_file()


def _service_output() -> list[Any]:
    service = OnboardingService()
    return [
        asyncio.run(service.get_sample_datasets()),
        service._get_onboarding_steps_config(),
        service.get_help_articles(),
    ]


def test_the_guard_can_fail():
    assert not _resolves_to_a_frontend_page("/videos/welcome-intro")
    assert not _resolves_to_a_frontend_page("https://docs.narrativemodeling.ai/x")
    assert _resolves_to_a_frontend_page("/quickstart")
    assert _urls({"a": [{"video_url": "/v"}], "download_url": "/d"}) == ["/v", "/d"]


@pytest.mark.parametrize("url", sorted(set(_urls(_service_output()))))
def test_every_onboarding_service_url_is_an_app_page(url):
    assert _resolves_to_a_frontend_page(url), f"{url} is not a page in apps/frontend/app"


async def test_help_tips_links_resolve_and_support_mail_is_the_company_address(
    async_authorized_client,
):
    response = await async_authorized_client.get("/api/v1/onboarding/help-tips")
    assert response.status_code == 200
    body = response.json()
    for url in _urls(body):
        assert _resolves_to_a_frontend_page(url), f"help-tips links to {url}"
    assert body["support_contact"] == {"email": SUPPORT_EMAIL}


def test_backend_support_email_is_the_one_the_legal_pages_publish():
    src = (_FRONTEND / "lib" / "legal" / "company.ts").read_text()
    m = re.search(r"supportEmail:\s*'([^']+)'", src)
    assert m, "supportEmail not found in company.ts"
    assert SUPPORT_EMAIL == m.group(1)


def test_no_dead_product_domain_in_backend_code():
    """AC6: the company domain comes from one constant; the old product domains are fiction.

    One exception: the generated SDK in api_documentation.py still defaults to an
    `api.narrativeml.com` host. That surface is #512's, and the real production
    hostname waits on #765, so only that host in that file is tolerated.
    """
    offenders = [
        f"{p.relative_to(_BACKEND_APP)}:{i}"
        for p in _BACKEND_APP.rglob("*.py")
        for i, line in enumerate(p.read_text().splitlines(), 1)
        if re.search(r"narrativeml\.com|narrativemodeling\.ai", line)
        and not (p.name == "api_documentation.py" and "api.narrativeml.com" in line)
    ]
    assert offenders == []
