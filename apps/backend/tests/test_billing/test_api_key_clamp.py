"""Re-clamping a tenant's API keys when their plan changes (#455).

The creation clamp only binds at creation. Without this, a tenant who held
ENTERPRISE long enough to mint a 60,000/hr key would keep that throughput on FREE
forever — the limiter never reads a subscription on the serving path.
"""

import pytest

from app.billing.api_keys import reconcile_user_api_keys
from app.billing.plans import api_key_rate_limit_ceiling
from app.models.api_key import APIKey
from app.models.subscription import PlanTier

pytestmark = pytest.mark.asyncio


async def _key(
    user_id: str, key_id: str, rate_limit: int, requested: int | None = None
) -> APIKey:
    key = APIKey(
        key_id=key_id,
        key_hash=APIKey.hash_key(f"sk_live_{key_id}"),
        name=key_id,
        user_id=user_id,
        rate_limit=rate_limit,
        # Default: the tenant asked for exactly what the key holds (a deliberate
        # value). A dip that clamps rate_limit below `requested` is what lets the
        # later recovery restore it (#588).
        requested_rate_limit=rate_limit if requested is None else requested,
    )
    await key.insert()
    return key


class TestClampUserApiKeys:
    async def test_lowers_keys_above_the_new_ceiling(self, setup_database):
        enterprise = api_key_rate_limit_ceiling(PlanTier.ENTERPRISE)
        free = api_key_rate_limit_ceiling(PlanTier.FREE)
        await _key("clamp-user-1", "clamp-1", enterprise)

        assert await reconcile_user_api_keys("clamp-user-1", PlanTier.FREE) == 1

        reread = await APIKey.find_one({"key_id": "clamp-1"})
        assert reread is not None
        assert reread.rate_limit == free

    async def test_leaves_keys_already_within_the_ceiling(self, setup_database):
        await _key("clamp-user-2", "clamp-2", 5)

        assert await reconcile_user_api_keys("clamp-user-2", PlanTier.FREE) == 0

        reread = await APIKey.find_one({"key_id": "clamp-2"})
        assert reread is not None
        assert reread.rate_limit == 5

    async def test_does_not_touch_another_tenants_keys(self, setup_database):
        enterprise = api_key_rate_limit_ceiling(PlanTier.ENTERPRISE)
        await _key("clamp-user-3", "clamp-3", enterprise)
        await _key("clamp-other", "clamp-other-1", enterprise)

        await reconcile_user_api_keys("clamp-user-3", PlanTier.FREE)

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


class TestRestoreAfterTransientDip:
    """#588: a transient non-entitled status must not permanently ratchet a paying
    tenant's keys down — the reconcile restores them when entitlement returns."""

    async def test_dip_then_recovery_restores_keys_via_apply(self, setup_database):
        """Full round trip through the webhook's _apply: entitled -> non-entitled
        (clamped) -> entitled again (restored to no worse than before)."""
        from datetime import UTC, datetime, timedelta

        from app.api.routes.billing_webhook import _apply
        from app.models.subscription import SubscriptionStatus

        pro = api_key_rate_limit_ceiling(PlanTier.PRO)
        free = api_key_rate_limit_ceiling(PlanTier.FREE)
        assert pro > free  # otherwise the round trip proves nothing
        user = "dip-user-1"
        await _key(user, "dip-1", pro)  # PRO tenant, key at full PRO throughput

        t0 = datetime.now(UTC) - timedelta(hours=3)

        # 1) Entitled (PRO) — the key holds at PRO.
        await _apply(user, status_=SubscriptionStatus.ACTIVE, tier=PlanTier.PRO, event_at=t0)
        assert (await APIKey.find_one({"key_id": "dip-1"})).rate_limit == pro

        # 2) A payment blip flips them to INCOMPLETE (not entitled -> effective FREE),
        #    so the reconcile clamps the key down.
        await _apply(
            user, status_=SubscriptionStatus.INCOMPLETE, tier=PlanTier.PRO,
            event_at=t0 + timedelta(hours=1),
        )
        assert (await APIKey.find_one({"key_id": "dip-1"})).rate_limit == free

        # 3) The payment settles -> ACTIVE again -> the key is RESTORED to PRO, not
        #    left ratcheted down.
        await _apply(
            user, status_=SubscriptionStatus.ACTIVE, tier=PlanTier.PRO,
            event_at=t0 + timedelta(hours=2),
        )
        assert (await APIKey.find_one({"key_id": "dip-1"})).rate_limit == pro

    async def test_restore_never_exceeds_the_requested_value(self, setup_database):
        """A key the tenant set low ON PURPOSE stays low even when the ceiling rises —
        the requested value, not the tier ceiling, is the cap."""
        await _key("dip-user-2", "dip-2", 500)  # requested == 500 (deliberate)

        await reconcile_user_api_keys("dip-user-2", PlanTier.FREE)   # dip
        assert (await APIKey.find_one({"key_id": "dip-2"})).rate_limit == 500
        await reconcile_user_api_keys("dip-user-2", PlanTier.PRO)    # recover
        # Not raised to the PRO ceiling — the tenant only ever asked for 500.
        assert (await APIKey.find_one({"key_id": "dip-2"})).rate_limit == 500

    async def test_legacy_key_without_requested_is_only_lowered(self, setup_database):
        """A pre-#588 row has no requested_rate_limit; $ifNull falls back to
        rate_limit, so it is clamped down but never surprise-raised."""
        enterprise = api_key_rate_limit_ceiling(PlanTier.ENTERPRISE)
        pro = api_key_rate_limit_ceiling(PlanTier.PRO)
        assert enterprise > pro
        await APIKey.get_motor_collection().insert_one(
            {
                "key_id": "legacy-1",
                "key_hash": APIKey.hash_key("sk_live_legacy"),
                "name": "legacy",
                "user_id": "legacy-user",
                "model_ids": [],
                "rate_limit": enterprise,
                "total_requests": 0,
                "is_active": True,
                # deliberately NO requested_rate_limit (pre-#588 shape)
            }
        )

        await reconcile_user_api_keys("legacy-user", PlanTier.PRO)   # downgrade -> lower
        doc = await APIKey.get_motor_collection().find_one({"key_id": "legacy-1"})
        assert doc["rate_limit"] == pro

        await reconcile_user_api_keys("legacy-user", PlanTier.ENTERPRISE)  # upgrade
        doc = await APIKey.get_motor_collection().find_one({"key_id": "legacy-1"})
        assert doc["rate_limit"] == pro  # NOT surprise-raised — no requested recorded


def test_create_request_rejects_an_unstorable_rate_limit():
    """#588: requested_rate_limit is persisted raw, and BSON is 64-bit — an
    unbounded request must be a 422 at validation, not a 500 on insert."""
    import pytest as _pytest
    from pydantic import ValidationError

    from app.api.routes.production import CreateAPIKeyRequest

    # A sane large value is accepted.
    assert CreateAPIKeyRequest(name="k", rate_limit=1_000_000_000).rate_limit == 1_000_000_000
    # Absurd values (BSON-unstorable, or just nonsense) are rejected.
    for bad in (1_000_000_001, 10 ** 100):
        with _pytest.raises(ValidationError):
            CreateAPIKeyRequest(name="k", rate_limit=bad)
