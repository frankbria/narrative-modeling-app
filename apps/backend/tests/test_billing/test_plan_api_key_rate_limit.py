"""The per-tier API-key rate-limit ceiling (issue #455).

`production.py` clamps a caller-supplied `rate_limit` to this value, so it must
exist for every tier and must be finite — `UNLIMITED` (-1) would be read by the
rate-limit store as "no enforcement" and reopen the hole this closes.
"""

from app.billing.plans import METERED_METRICS, PLAN_LIMITS, limits_for
from app.models.subscription import PlanTier


class TestApiKeyRateLimitCeiling:
    def test_every_tier_has_a_finite_positive_ceiling(self):
        for tier in PlanTier:
            ceiling = limits_for(tier).api_key_rate_limit
            assert isinstance(ceiling, int)
            assert ceiling > 0, f"{tier} ceiling must be finite and positive"

    def test_ceilings_are_monotonic_by_tier(self):
        free = limits_for(PlanTier.FREE).api_key_rate_limit
        pro = limits_for(PlanTier.PRO).api_key_rate_limit
        enterprise = limits_for(PlanTier.ENTERPRISE).api_key_rate_limit
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
