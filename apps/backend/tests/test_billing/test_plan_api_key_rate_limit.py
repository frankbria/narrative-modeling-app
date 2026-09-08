"""The per-tier API-key rate-limit ceiling (issue #455).

`production.py` clamps a caller-supplied `rate_limit` to this value, so it must
exist for every tier and must be finite — `UNLIMITED` (-1) would be read by the
rate-limit store as "no enforcement" and reopen the hole this closes.
"""

import logging

import pytest

from app.billing.plans import (
    METERED_METRICS,
    PLAN_LIMITS,
    _env_positive_int,
    api_key_rate_limit_ceiling,
)
from app.models.subscription import PlanTier


class TestApiKeyRateLimitCeiling:
    def test_every_tier_has_a_finite_positive_ceiling(self):
        for tier in PlanTier:
            ceiling = api_key_rate_limit_ceiling(tier)
            assert isinstance(ceiling, int)
            assert ceiling > 0, f"{tier} ceiling must be finite and positive"

    def test_ceilings_are_monotonic_by_tier(self):
        free = api_key_rate_limit_ceiling(PlanTier.FREE)
        pro = api_key_rate_limit_ceiling(PlanTier.PRO)
        enterprise = api_key_rate_limit_ceiling(PlanTier.ENTERPRISE)
        assert free <= pro <= enterprise

    def test_is_not_a_metered_metric(self):
        # It is a throughput ceiling, not a per-period counter — keeping it out of
        # METERED_METRICS stops `quota()` ever trying to reserve against it.
        assert "api_key_rate_limit" not in METERED_METRICS
        for limits in PLAN_LIMITS.values():
            try:
                limits.limit_for("api_key_rate_limit")
            except KeyError:
                continue
            raise AssertionError("limit_for must reject api_key_rate_limit")


class TestNonPositiveEnvOverride:
    """`UNLIMITED = -1` is this module's sentinel everywhere else — here it bricks.

    The limiter reads `limit <= 0` as "no enforcement", so an operator following the
    convention in `plans.py` would cap the tier at one request per window rather
    than uncapping it. `_env_positive_int` refuses the value and says so.

    Tested directly rather than by reloading the module: `importlib.reload` rebinds
    `PLAN_LIMITS` to a new dict while other suites still hold the old one, which
    broke `test_subscription.py` from across the suite.
    """

    @pytest.mark.parametrize("value", ["-1", "0", "-1000"])
    def test_non_positive_override_falls_back_and_warns(
        self, value, monkeypatch, caplog
    ):
        monkeypatch.setenv("PLAN_ENTERPRISE_API_KEY_RATE_LIMIT", value)
        with caplog.at_level(logging.WARNING):
            resolved = _env_positive_int("PLAN_ENTERPRISE_API_KEY_RATE_LIMIT", 60_000)

        assert resolved == 60_000, "must fall back to the default, not floor to 1"
        assert "PLAN_ENTERPRISE_API_KEY_RATE_LIMIT" in caplog.text

    def test_a_valid_override_is_honoured(self, monkeypatch, caplog):
        monkeypatch.setenv("PLAN_ENTERPRISE_API_KEY_RATE_LIMIT", "25000")
        with caplog.at_level(logging.WARNING):
            resolved = _env_positive_int("PLAN_ENTERPRISE_API_KEY_RATE_LIMIT", 60_000)

        assert resolved == 25_000
        assert caplog.text == ""

    def test_unset_uses_the_default(self, monkeypatch):
        monkeypatch.delenv("PLAN_ENTERPRISE_API_KEY_RATE_LIMIT", raising=False)
        assert _env_positive_int("PLAN_ENTERPRISE_API_KEY_RATE_LIMIT", 60_000) == 60_000
