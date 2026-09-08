"""Per-key rate-limit ceilings for production API keys (#455).

Lives in `billing/` rather than in the production route because two unrelated
surfaces need the same rule: key *creation* clamps a caller-supplied value, and
the Stripe webhook re-clamps a tenant's existing keys when their plan changes.
Splitting it would put the ceiling in two places, which is exactly what the issue
asked us not to do.

The limiter itself deliberately does not consult a subscription — that would be a
Mongo read per request on the serving hot path — so the ceiling is applied at
these two write points and floored at 1 in the middleware.
"""

import logging

from app.billing import metering
from app.billing.plans import api_key_rate_limit_ceiling
from app.models.api_key import APIKey
from app.models.subscription import PlanTier

logger = logging.getLogger(__name__)


async def clamped_rate_limit(user_id: str, requested: int) -> int:
    """Clamp a caller-supplied per-key rate limit to the tenant's plan ceiling.

    A ceiling, not an override: a tenant may still ask for less than their tier
    allows, which is legitimate blast-radius control on an individual key.
    """
    ceiling = api_key_rate_limit_ceiling(await metering.effective_tier_for(user_id))
    return min(requested, ceiling)


async def clamp_user_api_keys(user_id: str, tier: PlanTier) -> int:
    """Lower any of `user_id`'s keys that sit above `tier`'s ceiling. Returns the count.

    Called after a subscription change: without it, a tenant who held ENTERPRISE
    long enough to mint a 60k/hr key would keep that throughput forever on FREE,
    since nothing else revisits a key once created.

    A no-op filter (`rate_limit > ceiling` matching nothing) is the normal case, so
    this costs one indexed-by-user update per subscription event. Never raises —
    a webhook must still record the subscription change even if this write fails.
    """
    ceiling = api_key_rate_limit_ceiling(tier)
    try:
        result = await APIKey.get_motor_collection().update_many(
            {"user_id": user_id, "rate_limit": {"$gt": ceiling}},
            {"$set": {"rate_limit": ceiling}},
        )
    except Exception:
        logger.warning("Failed to re-clamp API keys after a plan change", exc_info=True)
        return 0
    if result.modified_count:
        logger.info(
            "clamped api keys after plan change",
            extra={
                "user_id": user_id,
                "tier": tier.value,
                "keys": result.modified_count,
            },
        )
    return int(result.modified_count)
