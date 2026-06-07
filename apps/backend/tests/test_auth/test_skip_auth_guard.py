"""Tests for the SKIP_AUTH environment guard (issue #149).

SKIP_AUTH=true bypasses all backend authentication, so the backend must
refuse to start (raise at import/startup) unless the environment is
explicitly ``development`` or ``test``:

- ``validate_skip_auth`` raises ``RuntimeError`` for production-like or
  unset environments when SKIP_AUTH is enabled
- ``get_environment`` standardizes ENVIRONMENT (with legacy NODE_ENV
  fallback; the suite itself sets ENVIRONMENT=test in conftest.py — there
  is deliberately no implicit pytest detection in the guard)
- importing ``app.auth.nextauth_auth`` in a hostile environment fails
  (verified in a fresh subprocess, simulating real app startup)
"""

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from app.config import get_environment, validate_skip_auth

pytestmark = [pytest.mark.unit, pytest.mark.auth]

BACKEND_DIR = Path(__file__).resolve().parents[2]


class TestValidateSkipAuth:
    """validate_skip_auth(skip_auth, environment) — pure validation logic."""

    @pytest.mark.parametrize(
        "environment", ["production", "prod", "staging", "live", "release"]
    )
    def test_skip_auth_in_production_like_env_raises(self, environment):
        with pytest.raises(RuntimeError, match="SKIP_AUTH"):
            validate_skip_auth(skip_auth=True, environment=environment)

    def test_skip_auth_with_unset_environment_raises(self):
        """Unset/blank environment is NOT implicitly development — fail safe."""
        with pytest.raises(RuntimeError, match="SKIP_AUTH"):
            validate_skip_auth(skip_auth=True, environment="")

    def test_skip_auth_with_unknown_environment_raises(self):
        with pytest.raises(RuntimeError, match="SKIP_AUTH"):
            validate_skip_auth(skip_auth=True, environment="qa")

    @pytest.mark.parametrize("environment", ["development", "test"])
    def test_skip_auth_allowed_in_development_and_test(self, environment, caplog):
        with caplog.at_level(logging.WARNING, logger="app.config"):
            validate_skip_auth(skip_auth=True, environment=environment)

        assert any("SKIP_AUTH" in record.message for record in caplog.records)

    @pytest.mark.parametrize("environment", ["Development", "TEST", " development "])
    def test_environment_matching_is_case_insensitive(self, environment):
        validate_skip_auth(skip_auth=True, environment=environment)

    @pytest.mark.parametrize(
        "environment", ["production", "staging", "development", ""]
    )
    def test_skip_auth_disabled_never_raises(self, environment):
        validate_skip_auth(skip_auth=False, environment=environment)

    def test_reads_env_vars_when_args_omitted(self, monkeypatch):
        monkeypatch.setenv("SKIP_AUTH", "true")
        monkeypatch.setenv("ENVIRONMENT", "production")

        with pytest.raises(RuntimeError, match="SKIP_AUTH"):
            validate_skip_auth()

    def test_conflicting_environment_signals_raise(self, monkeypatch):
        """A dev ENVIRONMENT must not outvote a production NODE_ENV.

        Legacy deployments set only NODE_ENV=production; a stray .env
        supplying ENVIRONMENT=development must not win (codex review #149).
        """
        monkeypatch.setenv("SKIP_AUTH", "true")
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setenv("NODE_ENV", "production")

        with pytest.raises(RuntimeError, match="SKIP_AUTH"):
            validate_skip_auth()

    def test_all_signals_development_allowed(self, monkeypatch):
        monkeypatch.setenv("SKIP_AUTH", "true")
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setenv("NODE_ENV", "development")

        validate_skip_auth()

    def test_legacy_node_env_alone_allows_test(self, monkeypatch):
        monkeypatch.setenv("SKIP_AUTH", "true")
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.setenv("NODE_ENV", "test")

        validate_skip_auth()

    def test_unset_environment_vars_raise(self, monkeypatch):
        """An entirely unset environment must fail — no implicit test
        detection (a pytest-in-sys.modules heuristic proved spoofable via
        pytest-cov's subprocess hook)."""
        monkeypatch.setenv("SKIP_AUTH", "true")
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.delenv("NODE_ENV", raising=False)

        with pytest.raises(RuntimeError, match="SKIP_AUTH"):
            validate_skip_auth()


class TestGetEnvironment:
    """get_environment — ENVIRONMENT first, NODE_ENV fallback, normalized."""

    def test_environment_takes_precedence_over_node_env(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("NODE_ENV", "development")

        assert get_environment() == "production"

    def test_falls_back_to_legacy_node_env(self, monkeypatch):
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.setenv("NODE_ENV", "staging")

        assert get_environment() == "staging"

    def test_normalizes_case_and_whitespace(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", " Production ")

        assert get_environment() == "production"

    def test_unset_uses_default(self, monkeypatch):
        """No implicit pytest detection — unset means the default."""
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.delenv("NODE_ENV", raising=False)

        assert get_environment() == "development"
        assert get_environment(default="") == ""

    def test_suite_declares_environment_explicitly(self):
        """conftest.py exports ENVIRONMENT (default: test) for the whole
        suite — the guard has no implicit pytest detection to fall back on."""
        assert os.environ.get(
            "ENVIRONMENT"
        ), "conftest.py must set ENVIRONMENT for the test suite"


class TestCredentialValidationStaysProductionSafe:
    """The #149 precedence refactor must not soften credential validation.

    If ANY set environment signal is production-like, dummy/blank AWS
    credentials are rejected — a stray .env ENVIRONMENT=development must
    not outvote a legacy NODE_ENV=production here either (codex review).
    """

    def test_dummy_credentials_rejected_when_node_env_is_production(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setenv("NODE_ENV", "production")
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "placeholder")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "placeholder")

        from app.config import Settings

        with pytest.raises(ValueError, match="[Dd]ummy credential"):
            Settings(
                AWS_ACCESS_KEY_ID="placeholder",
                AWS_SECRET_ACCESS_KEY="placeholder",  # noqa: S106 - intentional dummy credential for security-guard test
            )


class TestImportTimeGuard:
    """The guard fires at import of app.auth.nextauth_auth (= app startup).

    Run in a fresh subprocess so module import happens outside pytest,
    exactly like a real server boot.
    """

    def _import_auth_module(
        self, environment: str | None
    ) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        env["SKIP_AUTH"] = "true"
        env["PYTHONPATH"] = str(BACKEND_DIR)
        env.pop("NODE_ENV", None)
        if environment is None:
            env.pop("ENVIRONMENT", None)
        else:
            env["ENVIRONMENT"] = environment

        return subprocess.run(
            [sys.executable, "-c", "import app.auth.nextauth_auth"],
            capture_output=True,
            text=True,
            cwd=BACKEND_DIR,
            env=env,
            timeout=60,
        )

    def test_import_fails_with_skip_auth_in_production(self):
        result = self._import_auth_module("production")

        assert result.returncode != 0
        assert "RuntimeError" in result.stderr
        assert "SKIP_AUTH" in result.stderr

    def test_import_succeeds_with_skip_auth_in_development(self):
        result = self._import_auth_module("development")

        assert result.returncode == 0, result.stderr


class TestMainStartupRespectsRealEnvironment:
    """A stray .env must not defeat the guard on the app.main startup path.

    Found by cross-family review of #149: app.main loaded .env with
    override=True before the auth module was imported, so a checked-in
    .env with SKIP_AUTH=true + ENVIRONMENT=development could clobber a
    production host's real environment and silently bypass the guard.

    The app/ tree is copied into a sandbox so the .env that app.main
    resolves (relative to its own __file__) is test-controlled and the
    developer's real .env is never touched.
    """

    def _boot_app_main(
        self, tmp_path, dotenv_text: str, real_env: dict
    ) -> subprocess.CompletedProcess:
        # app/ plus the top-level packages it imports (utils.aws in routes/s3.py)
        for package in ("app", "utils"):
            shutil.copytree(
                BACKEND_DIR / package,
                tmp_path / package,
                ignore=shutil.ignore_patterns("__pycache__"),
            )
        # The hostile .env a developer might leave behind on a server
        (tmp_path / ".env").write_text(dotenv_text)

        env = os.environ.copy()
        env.pop("SKIP_AUTH", None)
        env.pop("NODE_ENV", None)
        env.pop("ENVIRONMENT", None)
        env.update(real_env)
        env["PYTHONPATH"] = str(tmp_path)
        # Non-dummy-looking credentials so the config validator isn't what
        # aborts the import in a production environment (hyphenated fakes
        # also keep the pre-commit secret scanner quiet).
        env["AWS_ACCESS_KEY_ID"] = "real-access-key-id-issue-149"
        env["AWS_SECRET_ACCESS_KEY"] = (
            "real-secret-access-key-issue-149"  # noqa: S105 - non-sensitive test fixture string
        )

        return subprocess.run(
            [sys.executable, "-c", "import app.main"],
            capture_output=True,
            text=True,
            cwd=tmp_path,
            env=env,
            timeout=120,
        )

    def _assert_startup_refused(self, result, scenario: str) -> None:
        # Match the guard's RuntimeError specifically — the SKIP_AUTH warning
        # log also mentions SKIP_AUTH, and an unrelated import error must not
        # masquerade as a pass.
        assert (
            result.returncode != 0
        ), f"app.main started with SKIP_AUTH=true ({scenario})\n{result.stderr}"
        assert "RuntimeError" in result.stderr, result.stderr
        assert "SKIP_AUTH=true is only permitted" in result.stderr, result.stderr

    @pytest.mark.parametrize("real_env_var", ["ENVIRONMENT", "NODE_ENV"])
    def test_dotenv_cannot_override_production_environment(
        self, tmp_path, real_env_var
    ):
        # The host's REAL environment says production (modern ENVIRONMENT or
        # legacy NODE_ENV deployments); .env disagrees.
        result = self._boot_app_main(
            tmp_path,
            dotenv_text="ENVIRONMENT=development\nSKIP_AUTH=true\n",
            real_env={real_env_var: "production"},
        )

        self._assert_startup_refused(
            result, f"from .env despite {real_env_var}=production in the real env"
        )

    def test_unset_environment_refuses_startup(self, tmp_path):
        """The most dangerous production scenario: a host with NO environment
        variable set at all plus a leftover .env enabling SKIP_AUTH."""
        result = self._boot_app_main(
            tmp_path,
            dotenv_text="SKIP_AUTH=true\n",
            real_env={},
        )

        self._assert_startup_refused(result, "with ENVIRONMENT/NODE_ENV unset")
