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


async def reconcile_user_api_keys(user_id: str, tier: PlanTier) -> int:
    """Reconcile `user_id`'s keys' effective `rate_limit` to their `tier`. Returns
    the count changed.

    Called after a subscription change. It moves each key **both directions** to
    ``min(requested_rate_limit, ceiling)``:
    - **down** when the ceiling drops (the #455 control: a tenant who held ENTERPRISE
      long enough to mint a 60k/hr key must not keep that throughput on FREE, since
      the limiter never reads a subscription on the serving path); and
    - **back up** when the ceiling recovers, so a transient payment blip that clamped
      a paying tenant to FREE doesn't ratchet their keys down permanently (#588).

    The requested value is the pivot that keeps "restore" safe: a key **we** clamped
    has ``requested_rate_limit`` above its clamped value, so it rises again; a key the
    tenant **set low on purpose** has ``requested_rate_limit`` == that low value, so
    ``min`` leaves it there. The result never exceeds the tenant's request or their
    tier ceiling.

    Legacy rows written before #588 have no ``requested_rate_limit``; ``$ifNull``
    falls back to their current ``rate_limit`` — conservative, so they are only ever
    lowered, never surprise-raised (``fix_api_key_rate_limits.py`` / a new key is the
    path for those). Never raises — a webhook must still record the subscription
    change even if this write fails.
    """
    ceiling = api_key_rate_limit_ceiling(tier)
    try:
        # Aggregation-pipeline update so the target depends on each row's own
        # requested value. `$ifNull` covers pre-#588 rows and any corrupted/missing
        # field (the middleware still floors the stored value at 1).
        result = await APIKey.get_motor_collection().update_many(
            {"user_id": user_id},
            [
                {
                    "$set": {
                        "rate_limit": {
                            "$min": [
                                {"$ifNull": ["$requested_rate_limit", "$rate_limit"]},
                                ceiling,
                            ]
                        }
                    }
                }
            ],
        )
    except Exception:
        logger.warning("Failed to reconcile API keys after a plan change", exc_info=True)
        return 0
    if result.modified_count:
        logger.info(
            "reconciled api keys after plan change",
            extra={
                "user_id": user_id,
                "tier": tier.value,
                "keys": result.modified_count,
            },
        )
    return int(result.modified_count)
