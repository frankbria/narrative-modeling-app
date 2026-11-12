"""A stand-in for a deploy directory on a box, for the tests that run the deploy scripts.

The scripts under ``scripts/deploy`` call ``scripts/deploy/compose.sh`` from the deploy
directory (#831), so a temporary directory needs the same two things a real one has:
that wrapper, and exactly one env file.
"""

import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
COMPOSE_WRAPPER = REPO_ROOT / "scripts" / "deploy" / "compose.sh"


def stand_in_box(directory: Path, env_file: str = ".env.staging") -> Path:
    """Make ``directory`` look like a box's deploy directory and return it."""
    scripts = directory / "scripts" / "deploy"
    scripts.mkdir(parents=True)
    shutil.copy2(COMPOSE_WRAPPER, scripts / "compose.sh")
    (directory / env_file).write_text("")
    return directory
