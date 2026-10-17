"""Legal/config guard tests for the project license (issues #260, Apache-2.0 relicense).

The committed ``LICENSE`` once was a wrong-product copy-paste that contradicted the
README. These static guards keep the Apache-2.0 declaration correct and
self-consistent across LICENSE, NOTICE, README and every place the code states it.
They read files only (no services) so they run in the service-free CI lane.
"""

import re
from pathlib import Path

import pytest

# apps/backend/tests/test_security/test_license.py -> repo root is 4 parents up.
REPO_ROOT = Path(__file__).resolve().parents[4]
LICENSE = REPO_ROOT / "LICENSE"
NOTICE = REPO_ROOT / "NOTICE"
README = REPO_ROOT / "README.md"

HOLDER = "Noatak Enterprises, LLC"
SOURCE_URL = "https://github.com/frankbria/narrative-modeling-app"
SPDX = "Apache-2.0"


@pytest.fixture(scope="module")
def license_text() -> str:
    return LICENSE.read_text(encoding="utf-8")


def test_license_is_the_full_apache_2_text(license_text: str) -> None:
    assert "Apache License" in license_text
    assert "Version 2.0, January 2004" in license_text
    # The whole licence, not a short notice: both ends of the terms are present.
    assert "TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION" in license_text
    assert "END OF TERMS AND CONDITIONS" in license_text
    # A previous licence must not survive alongside it.
    assert "GNU" not in license_text
    assert "CodeFRAME" not in license_text


def test_notice_names_the_product_holder_and_source() -> None:
    notice = NOTICE.read_text(encoding="utf-8")
    assert "SheetPredict" in notice
    assert HOLDER in notice
    assert SOURCE_URL in notice
    assert "Apache License, Version 2.0" in notice


def test_readme_states_the_same_license() -> None:
    readme = README.read_text(encoding="utf-8")
    assert "Apache" in readme
    assert "AGPL" not in readme


@pytest.mark.parametrize(
    "manifest",
    ["apps/backend/pyproject.toml", "apps/mcp/pyproject.toml", "apps/frontend/package.json"],
)
def test_every_package_manifest_declares_the_license(manifest: str) -> None:
    text = (REPO_ROOT / manifest).read_text(encoding="utf-8")
    assert re.search(rf'license"?\s*[=:]\s*"{re.escape(SPDX)}"', text), (
        f"{manifest} must declare license {SPDX!r}"
    )


@pytest.mark.asyncio
async def test_root_endpoint_states_license_and_source() -> None:
    from app.main import root

    payload = await root()
    assert payload["license"] == SPDX
    assert payload["source_code"] == SOURCE_URL


# ── The legal pages must name the same entity as NOTICE ──────────────────
# `company.ts` is the single source for what the Terms and Privacy pages say the
# contracting party IS, and it had "Noaysk Enterprises" — an entity that does not
# exist — while the LICENSE and README correctly said "Noatak". The published legal
# pages therefore named the wrong company, which is worse than naming none: those
# pages are what Stripe's reviewers, regulators and customers read before an account
# exists, and terms signed with a non-existent party are not obviously enforceable.
#
# It survived because the test that "covers" it, `__tests__/app/legal.page.test.tsx`,
# asserts the pages render `COMPANY.legalEntity` — reading the same constant it is
# checking, so any spelling passes. Same shape as #406, where the suite built the
# expected URL with the same expression as the code. The assertion below is against
# the LITERAL holder string, which is the only version that can fail.
COMPANY_TS = REPO_ROOT / "apps" / "frontend" / "lib" / "legal" / "company.ts"


def test_legal_pages_name_the_same_entity_as_the_license() -> None:
    src = COMPANY_TS.read_text(encoding="utf-8")
    m = re.search(r"legalEntity:\s*'([^']+)'", src)
    assert m, f"legalEntity not found in {COMPANY_TS}"
    entity = m.group(1)
    # Anchored, not a bare prefix: `startswith(HOLDER)` also accepts
    # "Noatak Enterprises, LLCs" and "…LLC2", so the guard against a wrong value
    # would pass on the class of typo it exists to catch. The entity is either
    # exactly the holder, or the holder followed by the `, dba …` trading name.
    assert entity == HOLDER or entity.startswith(HOLDER + ","), (
        f"company.ts names '{entity}', but NOTICE names "
        f"'{HOLDER}'. The Terms and Privacy pages render this string, so the two "
        f"must agree — change both or neither."
    )
