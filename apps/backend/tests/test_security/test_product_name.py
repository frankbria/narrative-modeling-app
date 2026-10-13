"""The product has one name, SheetPredict (#765 AC1, #770 AC7).

It had three: the browser title and the legal pages said one, the sidebar a second
and onboarding a third, and the API's vendor media type carried a fourth that is
another company's domain. This reads every tracked text file and fails on any of
them, so a retired name cannot come back in a page, a docstring or a guide.

Identifiers are not names: the repository, the packages, the databases and the
buckets keep theirs, and none of them matches the patterns below.
"""

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]

RETIRED = re.compile(
    r"narrative modeling|modeling app\b|(?-i:NarrativeML)|vnd\\?\.narrativeml", re.IGNORECASE
)

# The historical record keeps the name things had when they were written.
_HISTORY = (
    "tasks/",
    "claudedocs/",
    "apps/backend/claudedocs/",
    "docs/archive/",
    "docs/deployment/archive/",
    "docs/sprints/",
)
_NAMES_THEM_ON_PURPOSE = {
    # Records which names were retired, and why.
    "docs/product/positioning.md",
    "apps/backend/tests/test_security/test_product_name.py",
}


# The staging guide records the command that created the deploy account on the box.
# The account's comment field is what it was created with: an identifier, like the
# account's own name, not copy.
_ACCOUNT_COMMENT = "--gecos"


def _tracked_files() -> list[str]:
    listed = subprocess.run(
        ["git", "ls-files", "-z"], cwd=REPO_ROOT, capture_output=True, check=True
    )
    return [name for name in listed.stdout.decode().split("\0") if name]


def _in_scope(name: str) -> bool:
    return not name.startswith(_HISTORY) and name not in _NAMES_THEM_ON_PURPOSE


def _retired_names_in(name: str) -> list[str]:
    try:
        text = (REPO_ROOT / name).read_text(encoding="utf-8")
    except (UnicodeDecodeError, FileNotFoundError):
        return []  # a binary file, or one deleted in the working tree
    return [
        f"{name}:{number}: {line.strip()[:120]}"
        for number, line in enumerate(text.splitlines(), 1)
        if RETIRED.search(line) and _ACCOUNT_COMMENT not in line
    ]


def test_no_tracked_file_uses_a_retired_product_name() -> None:
    files = [name for name in _tracked_files() if _in_scope(name)]
    assert len(files) > 500, "the walk found too few files to mean anything"

    offenders = [hit for name in files for hit in _retired_names_in(name)]

    assert offenders == [], "\n".join(offenders)


def test_the_pattern_matches_each_retired_variant_and_no_identifier() -> None:
    for retired in (
        "Narrative Modeling App",
        "the Narrative Modeling Application",
        "Welcome to Narrative Modeling",
        "<h1>Modeling App</h1>",
        "NarrativeML",
        "application/vnd.narrativeml.v1+json",
        r"application/vnd\.narrativeml\.v(\d+)",
    ):
        assert RETIRED.search(retired), retired
    for kept in (
        "frankbria/narrative-modeling-app",
        "narrative_modeling_test",
        "narrative-modeling-dev",
        "test@narrativeml.com",
        "the modeling approach",
        "SheetPredict",
    ):
        assert not RETIRED.search(kept), kept
