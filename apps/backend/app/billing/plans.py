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


@dataclass(frozen=True)
class PlanLimits:
    """What one tier may do per billing period."""

    training_runs: int
    predictions: int
    uploads: int

    def limit_for(self, metric: str) -> int:
        """Look a metric up by the name the metering store uses."""
        try:
            return getattr(self, metric)
        except AttributeError as exc:  # pragma: no cover - programmer error
            raise KeyError(f"unknown metered metric: {metric}") from exc

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
    ),
    PlanTier.PRO: PlanLimits(
        training_runs=_env_int("PLAN_PRO_TRAINING_RUNS", 200),
        predictions=_env_int("PLAN_PRO_PREDICTIONS", 100_000),
        uploads=_env_int("PLAN_PRO_UPLOADS", 500),
    ),
    PlanTier.ENTERPRISE: PlanLimits(
        training_runs=_env_int("PLAN_ENTERPRISE_TRAINING_RUNS", UNLIMITED),
        predictions=_env_int("PLAN_ENTERPRISE_PREDICTIONS", UNLIMITED),
        uploads=_env_int("PLAN_ENTERPRISE_UPLOADS", UNLIMITED),
    ),
}

#: The metered actions. Named here so the metering store, the enforcement
#: dependency and PlanLimits cannot drift apart.
METERED_METRICS = ("training_runs", "predictions", "uploads")


def limits_for(tier: PlanTier) -> PlanLimits:
    """Limits for a tier, falling back to FREE for anything unrecognised."""
    return PLAN_LIMITS.get(tier, PLAN_LIMITS[PlanTier.FREE])
