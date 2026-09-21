"""Legal/config guard tests for the project license (issue #260).

The committed ``LICENSE`` used to be a wrong-product copy-paste (CodeFRAME,
AGPL-3.0) that contradicted the README. These static guards keep the AGPL-3.0
declaration correct and self-consistent, mirroring the deploy-config guards in
``test_cors_config.py`` / ``test_staging_ports.py``. They read files only (no
services) so they run in the service-free CI lane.
"""

import re
from pathlib import Path

import pytest

# apps/backend/tests/test_security/test_license.py -> repo root is 4 parents up.
REPO_ROOT = Path(__file__).resolve().parents[4]
LICENSE = REPO_ROOT / "LICENSE"
README = REPO_ROOT / "README.md"

HOLDER = "Noatak Enterprises, LLC"
SOURCE_URL = "https://github.com/frankbria/narrative-modeling-app"


@pytest.fixture(scope="module")
def license_text() -> str:
    return LICENSE.read_text(encoding="utf-8")


def test_license_is_agpl3(license_text: str) -> None:
    assert "GNU AFFERO GENERAL PUBLIC LICENSE" in license_text
    assert "Version 3" in license_text
    # Full license text, not just the 15-line notice the wrong file shipped.
    assert "How to Apply These Terms to Your New Programs" in license_text


def test_license_names_correct_product_and_holder(license_text: str) -> None:
    assert "Narrative Modeling App" in license_text
    assert HOLDER in license_text
    # The wrong-product leftovers must be gone.
    assert "CodeFRAME" not in license_text
    assert "Fully Remote Autonomous Multi-Agent Environment" not in license_text


def test_license_surfaces_source_offer(license_text: str) -> None:
    # AGPL §13: the corresponding-source location must be discoverable.
    assert SOURCE_URL in license_text


def test_readme_reconciled_to_agpl() -> None:
    readme = README.read_text(encoding="utf-8")
    assert "MIT or Apache 2.0 TBD" not in readme
    assert "AGPL" in readme


@pytest.mark.asyncio
async def test_root_endpoint_offers_source() -> None:
    """The deployed API root offers the corresponding source (AGPL §13)."""
    from app.main import root

    payload = await root()
    assert payload["license"] == "AGPL-3.0-or-later"
    assert payload["source_code"] == SOURCE_URL
    assert "source" in payload["source_offer"].lower()


# ── The legal pages must name the same entity as the licence ──────────────────
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
        f"company.ts names '{entity}', but the LICENSE and README name "
        f"'{HOLDER}'. The Terms and Privacy pages render this string, so the two "
        f"must agree — change both or neither."
    )
