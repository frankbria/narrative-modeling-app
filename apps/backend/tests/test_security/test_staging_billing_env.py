"""Regression guard: the staging container must actually receive the Stripe config.

Issue #457 (P0.14): `docker-compose.staging.yml` passed no `STRIPE_*` variable to
the backend, so `stripe_client.is_configured()` was false in the only deployed
environment — `/billing/checkout` answered 503, the webhook rejected every event
for want of a signing secret, and `BillingStatus.configured` reported false. None
of that errors: running without Stripe is a supported configuration (ADR-002),
which is exactly why the omission was invisible for as long as it existed. There
was also no env example or deploy doc naming the variables, so no checklist would
have caught it.

These tests parse the REAL compose file and the REAL env examples rather than a
fixture, so dropping a variable from either fails the build.
"""

import re
from pathlib import Path

import yaml

# apps/backend/tests/test_security/ -> repo root
REPO_ROOT = Path(__file__).resolve().parents[4]
COMPOSE_FILE = REPO_ROOT / "docker-compose.staging.yml"
STAGING_ENV_EXAMPLE = REPO_ROOT / ".env.staging.example"
BACKEND_ENV_EXAMPLE = REPO_ROOT / "apps" / "backend" / ".env.example"

#: Every variable the billing surface reads. `STRIPE_SECRET_KEY` gates
#: `is_configured()`; `STRIPE_WEBHOOK_SECRET` gates signature verification; the two
#: price ids are what `_price_for` maps a tier to when starting a checkout.
#: `STRIPE_PUBLISHABLE_KEY` is deliberately absent — it is read into `Settings` but
#: nothing reads it back, and checkout is hosted, so the frontend has no Stripe code.
REQUIRED_STRIPE_VARS = (
    "STRIPE_SECRET_KEY",
    "STRIPE_WEBHOOK_SECRET",
    "STRIPE_PRICE_PRO",
    "STRIPE_PRICE_ENTERPRISE",
)


def _backend_environment() -> dict[str, str]:
    """The backend service's `environment:` mapping from the real compose file."""
    compose = yaml.safe_load(COMPOSE_FILE.read_text())
    env = compose["services"]["backend"]["environment"]
    assert isinstance(env, dict), "backend environment is expected in mapping form"
    return {k: "" if v is None else str(v) for k, v in env.items()}


class TestComposePassesStripeConfig:
    def test_backend_receives_every_stripe_variable(self):
        env = _backend_environment()
        missing = [v for v in REQUIRED_STRIPE_VARS if v not in env]
        assert not missing, (
            "docker-compose.staging.yml must pass these to the backend or billing is "
            f"inert in the deployed environment (#457): {missing}"
        )

    def test_stripe_variables_are_interpolated_from_the_env_file(self):
        """Values must come from `.env.staging`, never be literals in the compose file.

        A hardcoded key would be a secret committed to a public repo; a hardcoded
        price id would silently bill the wrong product after a Stripe change.
        """
        env = _backend_environment()
        for var in REQUIRED_STRIPE_VARS:
            value = env[var]
            assert re.fullmatch(rf"\$\{{{var}(:[-?][^}}]*)?\}}", value), (
                f"{var} must interpolate ${{{var}}} from .env.staging, got {value!r}"
            )

    def test_stripe_variables_do_not_block_the_deploy_before_keys_exist(self):
        """AC2 of #457: passthrough now, `${VAR:?}` once the keys are provisioned.

        `scripts/deploy/preflight_staging_env.sh` derives its required set from the
        `${VAR:?}` guards in this very file, so adding a guard for a variable that is
        not yet in `.env.staging` fails the next deploy and takes staging down. When
        the keys land, flipping `:-` to `:?` here is the whole change — and this test
        is then the thing to update, deliberately.
        """
        env = _backend_environment()
        guarded = [v for v in REQUIRED_STRIPE_VARS if ":?" in env[v]]
        assert not guarded, (
            "these are marked required, so .env.staging must already carry real "
            f"values — confirm that, then update this test: {guarded}"
        )


class TestEnvExamplesDocumentStripe:
    """AC3 of #457 — the omission was invisible partly because nothing listed them."""

    def test_staging_example_documents_every_variable(self):
        text = STAGING_ENV_EXAMPLE.read_text()
        missing = [v for v in REQUIRED_STRIPE_VARS if f"{v}=" not in text]
        assert not missing, f".env.staging.example must document: {missing}"

    def test_backend_example_documents_every_variable(self):
        text = BACKEND_ENV_EXAMPLE.read_text()
        missing = [v for v in REQUIRED_STRIPE_VARS if f"{v}=" not in text]
        assert not missing, f"apps/backend/.env.example must document: {missing}"

    def test_plan_overrides_decision_is_recorded(self):
        """AC4 — `PLAN_*` is not passed through; say so where an operator will look.

        The defaults in `plans.py` are placeholders (#474), and the fix for that is
        real numbers in that one file rather than twelve env passthroughs onto a box
        whose config is hand-maintained (#594).
        """
        assert "PLAN_" in STAGING_ENV_EXAMPLE.read_text(), (
            "an operator reading .env.staging.example must be told why no PLAN_* "
            "override is listed, or they will assume the file is incomplete"
        )
