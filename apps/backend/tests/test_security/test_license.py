"""Legal/config guard tests for the project license (issue #260).

The committed ``LICENSE`` used to be a wrong-product copy-paste (CodeFRAME,
AGPL-3.0) that contradicted the README. These static guards keep the AGPL-3.0
declaration correct and self-consistent, mirroring the deploy-config guards in
``test_cors_config.py`` / ``test_staging_ports.py``. They read files only (no
services) so they run in the service-free CI lane.
"""

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
