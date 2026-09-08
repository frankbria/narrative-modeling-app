"""Plan limits (#366/#368).

**These numbers are an assumption, not a product decision.** The billing issues
specify the mechanism but never the tiers, limits or pricing. They are set here, in
one place, with env overrides, precisely so changing them is a config edit rather
than a code change — and so it is obvious where to look when the real numbers
arrive.

Kept out of the `Subscription` document deliberately: a limit changes without a
migration, whereas the document records what a tenant actually bought.
"""

import os
from dataclasses import dataclass

from app.models.subscription import PlanTier

#: Sentinel for "no ceiling". Comparisons use `>=`, so this is never reached.
UNLIMITED = -1

#: The metered actions. Named once so the metering store, the enforcement
#: dependency and PlanLimits cannot drift apart — and so `limit_for` has an
#: allow-list to validate against rather than trusting getattr.
METERED_METRICS = ("training_runs", "predictions", "uploads")


@dataclass(frozen=True)
class PlanLimits:
    """What one tier may do per billing period.

    ``api_key_rate_limit`` is the odd one out: a throughput ceiling per hour, not a
    per-period counter, so it is deliberately absent from ``METERED_METRICS`` and
    from ``limit_for`` — nothing reserves against it.
    """

    training_runs: int
    predictions: int
    uploads: int
    #: Ceiling for a production API key's ``rate_limit`` (requests per
    #: RATE_LIMIT_APIKEY_WINDOW_SECONDS). Must stay finite and positive on every
    #: tier: the rate-limit store reads ``limit <= 0`` as "no enforcement", so
    #: UNLIMITED here would disable the only limiter on the paid serving surface
    #: — which is the hole #455 closes.
    api_key_rate_limit: int

    def limit_for(self, metric: str) -> int:
        """Look a metric up by the name the metering store uses.

        Restricted to the declared fields rather than a raw `getattr`: a metric name
        colliding with a method — `"allows"`, `"limit_for"` — would otherwise return
        that bound method instead of raising, silently defeating the clear-error
        guarantee this is here to provide.
        """
        if metric not in METERED_METRICS:
            raise KeyError(f"unknown metered metric: {metric}")
        return getattr(self, metric)

    def allows(self, metric: str, used: int) -> bool:
        limit = self.limit_for(metric)
        return limit == UNLIMITED or used < limit


def _env_int(name: str, default: int) -> int:
    """Read an override, falling back rather than failing on a bad value.

    A malformed limit must not stop the app booting — the consequence would be an
    outage over a typo in a number that has a perfectly good default.
    """
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


#: Per-tier, per-period ceilings. FREE is intentionally usable rather than a
#: teaser: the app is an invite-only beta today (ADR-001), and a free tier that
#: cannot train a single model would make the beta unusable the moment enforcement
#: is switched on.
PLAN_LIMITS: dict[PlanTier, PlanLimits] = {
    PlanTier.FREE: PlanLimits(
        training_runs=_env_int("PLAN_FREE_TRAINING_RUNS", 10),
        predictions=_env_int("PLAN_FREE_PREDICTIONS", 1_000),
        uploads=_env_int("PLAN_FREE_UPLOADS", 20),
        api_key_rate_limit=_env_int("PLAN_FREE_API_KEY_RATE_LIMIT", 1_000),
    ),
    PlanTier.PRO: PlanLimits(
        training_runs=_env_int("PLAN_PRO_TRAINING_RUNS", 200),
        predictions=_env_int("PLAN_PRO_PREDICTIONS", 100_000),
        uploads=_env_int("PLAN_PRO_UPLOADS", 500),
        api_key_rate_limit=_env_int("PLAN_PRO_API_KEY_RATE_LIMIT", 10_000),
    ),
    PlanTier.ENTERPRISE: PlanLimits(
        training_runs=_env_int("PLAN_ENTERPRISE_TRAINING_RUNS", UNLIMITED),
        predictions=_env_int("PLAN_ENTERPRISE_PREDICTIONS", UNLIMITED),
        uploads=_env_int("PLAN_ENTERPRISE_UPLOADS", UNLIMITED),
        api_key_rate_limit=_env_int("PLAN_ENTERPRISE_API_KEY_RATE_LIMIT", 60_000),
    ),
}


def limits_for(tier: PlanTier) -> PlanLimits:
    """Limits for a tier, falling back to FREE for anything unrecognised."""
    return PLAN_LIMITS.get(tier, PLAN_LIMITS[PlanTier.FREE])
