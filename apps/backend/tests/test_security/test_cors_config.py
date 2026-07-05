"""Tests for the CORS origin resolver (issue #256).

The backend registers CORS with ``allow_credentials=True`` (main.py). With
``allow_origins=["*"]`` Starlette reflects the caller's Origin and emits
``Access-Control-Allow-Credentials: true`` — so a wildcard there lets ANY site
make authenticated cross-origin requests. Staging shipped this because compose
set ``ALLOWED_ORIGINS`` (a name nothing reads) instead of ``BACKEND_CORS_ORIGINS``,
leaving the wildcard default in place.

``resolve_cors_origins`` is the pure guard (mirrors ``validate_skip_auth``):
- parses JSON *or* comma-separated origin lists,
- refuses ``"*"`` in production-like environments (fail-closed startup).
"""

import pytest

from app.config import resolve_cors_origins

pytestmark = [pytest.mark.unit, pytest.mark.security]


class TestResolveCorsOrigins:
    """resolve_cors_origins(raw, environment) — pure origin resolution."""

    # --- parsing -----------------------------------------------------------

    def test_parses_json_list(self):
        assert resolve_cors_origins(
            '["https://a.example.com","https://b.example.com"]',
            environment="development",
        ) == ["https://a.example.com", "https://b.example.com"]

    def test_parses_comma_separated(self):
        """The staging template documents comma-separated origins."""
        assert resolve_cors_origins(
            "https://a.example.com, https://b.example.com",
            environment="staging",
        ) == ["https://a.example.com", "https://b.example.com"]

    def test_unset_defaults_to_wildcard_in_development(self):
        assert resolve_cors_origins(None, environment="development") == ["*"]
        assert resolve_cors_origins("", environment="development") == ["*"]

    # --- production-like refusal (the fix) ---------------------------------

    @pytest.mark.parametrize(
        "environment", ["production", "prod", "staging", "live", "release"]
    )
    def test_wildcard_refused_in_production_like(self, environment):
        with pytest.raises(ValueError, match="BACKEND_CORS_ORIGINS"):
            resolve_cors_origins('["*"]', environment=environment)

    @pytest.mark.parametrize("raw", [None, "", "*", '["*"]'])
    def test_unset_or_wildcard_all_refused_in_staging(self, raw):
        """Fail-closed: a mis/unconfigured staging deploy must not run wildcard."""
        with pytest.raises(ValueError, match="BACKEND_CORS_ORIGINS"):
            resolve_cors_origins(raw, environment="staging")

    def test_wildcard_mixed_with_explicit_origin_still_refused(self):
        """One explicit origin does not 'dilute' a wildcard — any '*' refuses."""
        with pytest.raises(ValueError, match="BACKEND_CORS_ORIGINS"):
            resolve_cors_origins(
                '["*","https://app.example.com"]', environment="production"
            )

    def test_explicit_origins_allowed_in_production_like(self):
        assert resolve_cors_origins(
            '["https://app.example.com"]', environment="production"
        ) == ["https://app.example.com"]

    # --- development keeps wildcard (DX preserved) -------------------------

    @pytest.mark.parametrize("environment", ["development", "test"])
    def test_wildcard_allowed_in_development_and_test(self, environment):
        assert resolve_cors_origins('["*"]', environment=environment) == ["*"]
