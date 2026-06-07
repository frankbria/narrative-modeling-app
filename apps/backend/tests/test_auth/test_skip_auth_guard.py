"""Tests for the SKIP_AUTH environment guard (issue #149).

SKIP_AUTH=true bypasses all backend authentication, so the backend must
refuse to start (raise at import/startup) unless the environment is
explicitly ``development`` or ``test``:

- ``validate_skip_auth`` raises ``RuntimeError`` for production-like or
  unset environments when SKIP_AUTH is enabled
- ``get_environment`` standardizes ENVIRONMENT (with legacy NODE_ENV
  fallback and pytest detection)
- importing ``app.auth.nextauth_auth`` in a hostile environment fails
  (verified in a fresh subprocess, simulating real app startup)
"""

import logging
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

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

    def test_unset_environment_outside_pytest_raises(self, monkeypatch):
        """Without pytest in the process, an unset ENVIRONMENT must fail."""
        monkeypatch.setenv("SKIP_AUTH", "true")
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.delenv("NODE_ENV", raising=False)

        with patch.dict(sys.modules) as modules:
            modules.pop("pytest", None)
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

    def test_unset_under_pytest_is_test(self, monkeypatch):
        """A pytest run with no explicit environment counts as test."""
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.delenv("NODE_ENV", raising=False)

        assert get_environment() == "test"

    def test_unset_outside_pytest_uses_default(self, monkeypatch):
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.delenv("NODE_ENV", raising=False)

        with patch.dict(sys.modules) as modules:
            modules.pop("pytest", None)
            assert get_environment() == "development"
            assert get_environment(default="") == ""


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
