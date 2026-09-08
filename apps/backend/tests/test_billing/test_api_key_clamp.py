"""Re-clamping a tenant's API keys when their plan changes (#455).

The creation clamp only binds at creation. Without this, a tenant who held
ENTERPRISE long enough to mint a 60,000/hr key would keep that throughput on FREE
forever — the limiter never reads a subscription on the serving path.
"""

import pytest

from app.billing.api_keys import clamp_user_api_keys
from app.billing.plans import api_key_rate_limit_ceiling
from app.models.api_key import APIKey
from app.models.subscription import PlanTier

pytestmark = pytest.mark.asyncio


async def _key(user_id: str, key_id: str, rate_limit: int) -> APIKey:
    key = APIKey(
        key_id=key_id,
        key_hash=APIKey.hash_key(f"sk_live_{key_id}"),
        name=key_id,
        user_id=user_id,
        rate_limit=rate_limit,
    )
    await key.insert()
    return key


class TestClampUserApiKeys:
    async def test_lowers_keys_above_the_new_ceiling(self, setup_database):
        enterprise = api_key_rate_limit_ceiling(PlanTier.ENTERPRISE)
        free = api_key_rate_limit_ceiling(PlanTier.FREE)
        await _key("clamp-user-1", "clamp-1", enterprise)

        assert await clamp_user_api_keys("clamp-user-1", PlanTier.FREE) == 1

        reread = await APIKey.find_one({"key_id": "clamp-1"})
        assert reread is not None
        assert reread.rate_limit == free

    async def test_leaves_keys_already_within_the_ceiling(self, setup_database):
        await _key("clamp-user-2", "clamp-2", 5)

        assert await clamp_user_api_keys("clamp-user-2", PlanTier.FREE) == 0

        reread = await APIKey.find_one({"key_id": "clamp-2"})
        assert reread is not None
        assert reread.rate_limit == 5

    async def test_does_not_touch_another_tenants_keys(self, setup_database):
        enterprise = api_key_rate_limit_ceiling(PlanTier.ENTERPRISE)
        await _key("clamp-user-3", "clamp-3", enterprise)
        await _key("clamp-other", "clamp-other-1", enterprise)

        await clamp_user_api_keys("clamp-user-3", PlanTier.FREE)

        other = await APIKey.find_one({"key_id": "clamp-other-1"})
        assert other is not None
        assert other.rate_limit == enterprise


class TestWebhookReclampsOnDowngrade:
    async def test_subscription_downgrade_lowers_existing_keys(self, setup_database):
        """The wiring, not just the helper: a plan change must reach the keys."""
        from app.api.routes.billing_webhook import _apply
        from app.models.subscription import SubscriptionStatus

        enterprise = api_key_rate_limit_ceiling(PlanTier.ENTERPRISE)
        await _key("clamp-user-4", "clamp-4", enterprise)

        await _apply(
            "clamp-user-4",
            status_=SubscriptionStatus.CANCELED,
            tier=PlanTier.ENTERPRISE,
        )

        reread = await APIKey.find_one({"key_id": "clamp-4"})
        assert reread is not None
        # CANCELED is not entitled, so effective_tier is FREE regardless of plan_tier.
        assert reread.rate_limit == api_key_rate_limit_ceiling(PlanTier.FREE)

    async def test_out_of_order_event_does_not_clamp(self, setup_database):
        """`_apply` returns early on a stale event — the clamp must stay behind it.

        Nothing is persisted on that path, so clamping there would apply a tier the
        subscription never moved to.
        """
        from datetime import UTC, datetime, timedelta

        from app.api.routes.billing_webhook import _apply
        from app.models.subscription import SubscriptionStatus

        enterprise = api_key_rate_limit_ceiling(PlanTier.ENTERPRISE)
        await _key("clamp-user-5", "clamp-5", enterprise)

        now = datetime.now(UTC)
        await _apply(
            "clamp-user-5",
            status_=SubscriptionStatus.ACTIVE,
            tier=PlanTier.ENTERPRISE,
            event_at=now,
        )
        # A *stale* downgrade arriving after the newer event must be ignored. It
        # carries its own tier: without one the mutant (clamping before the guard)
        # would read the unchanged ENTERPRISE off `sub` and look correct.
        await _apply(
            "clamp-user-5",
            status_=SubscriptionStatus.CANCELED,
            tier=PlanTier.FREE,
            event_at=now - timedelta(hours=1),
        )

        reread = await APIKey.find_one({"key_id": "clamp-5"})
        assert reread is not None
        assert reread.rate_limit == enterprise
