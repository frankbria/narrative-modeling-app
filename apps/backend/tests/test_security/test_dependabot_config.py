"""Regression guard: .github/dependabot.yml must stay valid for Dependabot.

An invalid key anywhere in this file invalidates the WHOLE config — Dependabot
rejects it outright and every ecosystem silently stops updating, security bumps
included. That is a supply-chain control failing closed with no local signal:
nothing in `ci.yml` parses this file, and the only feedback is a
`.github/dependabot.yml` check-run that GitHub posts *after* a merge, and only
on commits that touch the file.

That is exactly how it broke: the `github-actions` block carried
`semver-{major,minor,patch}-days` cooldown keys, which Dependabot supports for
npm but NOT for github-actions. It sat there unnoticed until PR #347 touched the
file for an unrelated reason and triggered revalidation, which reported:

    The property '#/updates/5/cooldown/semver-major-days' is not supported
    for the package ecosystem 'github-actions'.

These tests parse the real file so a reintroduction fails the build instead of
quietly stopping dependency updates.
"""

from pathlib import Path

import yaml

# apps/backend/tests/test_security/ -> repo root
REPO_ROOT = Path(__file__).resolve().parents[4]
DEPENDABOT_CONFIG = REPO_ROOT / ".github" / "dependabot.yml"

# Cooldown keys Dependabot rejects for the github-actions ecosystem.
SEMVER_COOLDOWN_KEYS = (
    "semver-major-days",
    "semver-minor-days",
    "semver-patch-days",
)


def _updates() -> list[dict]:
    config = yaml.safe_load(DEPENDABOT_CONFIG.read_text())
    assert config["version"] == 2, "Dependabot config must declare version 2"
    return config["updates"]


def test_dependabot_config_is_parseable() -> None:
    """The file must be valid YAML with a non-empty `updates` list."""
    updates = _updates()
    assert updates, "dependabot.yml declares no update blocks"
    for i, update in enumerate(updates):
        assert update.get("package-ecosystem"), f"updates[{i}] has no package-ecosystem"
        assert update.get("directory"), f"updates[{i}] has no directory"


def test_github_actions_cooldown_has_no_semver_day_keys() -> None:
    """github-actions cooldown accepts `default-days` only.

    Dependabot rejects the per-semver variants for this ecosystem, and one bad
    key takes the entire file down with it.
    """
    for i, update in enumerate(_updates()):
        if update.get("package-ecosystem") != "github-actions":
            continue
        cooldown = update.get("cooldown") or {}
        offenders = sorted(k for k in SEMVER_COOLDOWN_KEYS if k in cooldown)
        assert not offenders, (
            f"updates[{i}] (github-actions) sets {offenders} under `cooldown`. "
            "Dependabot does not support these for github-actions and will "
            "reject the whole dependabot.yml, silently stopping ALL dependency "
            "updates including security patches. Use `default-days` only."
        )
