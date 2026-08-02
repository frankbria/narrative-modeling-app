"""Subscription persistence against real Mongo (#366).

`tests/test_models/test_subscription.py` covers the entitlement logic without a
database, so it can stay in the service-free CI selection. What it cannot cover is
the thing the webhook (#367) will depend on: the unique index on `user_id`, which
is what makes an upsert idempotent under Stripe's at-least-once retries.
"""

import pytest
from beanie import PydanticObjectId, init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from app.models.subscription import PlanTier, Subscription, SubscriptionStatus

TEST_USER = "test_user_123"


@pytest.mark.asyncio
class TestSubscriptionPersistence:
    async def test_round_trips_through_mongo(self, setup_database):
        sub = Subscription(
            user_id=TEST_USER,
            plan_tier=PlanTier.PRO,
            status=SubscriptionStatus.ACTIVE,
            stripe_customer_id="cus_123",
            stripe_subscription_id="sub_123",
        )
        await sub.insert()

        found = await Subscription.find_one(Subscription.user_id == TEST_USER)

        assert found is not None
        assert found.plan_tier == PlanTier.PRO
        assert found.effective_tier == PlanTier.PRO
        assert found.stripe_customer_id == "cus_123"

    async def test_one_subscription_per_tenant(self, setup_database):
        """The unique index is what lets the webhook upsert be idempotent.

        Beanie surfaces a unique-index violation as RevisionIdWasChanged rather than
        DuplicateKeyError on `save()` (see CLAUDE.md); `insert()` raises the pymongo
        error, so the assertion is deliberately broad about the type and specific
        about the outcome — exactly one document survives.
        """
        await Subscription(user_id=TEST_USER, plan_tier=PlanTier.PRO).insert()

        with pytest.raises(Exception):  # noqa: B017 - see docstring
            await Subscription(user_id=TEST_USER, plan_tier=PlanTier.ENTERPRISE).insert()

        assert await Subscription.find(Subscription.user_id == TEST_USER).count() == 1

    async def test_different_tenants_are_independent(self, setup_database):
        await Subscription(user_id="tenant-a", plan_tier=PlanTier.PRO).insert()
        await Subscription(user_id="tenant-b", plan_tier=PlanTier.ENTERPRISE).insert()

        a = await Subscription.find_one(Subscription.user_id == "tenant-a")
        b = await Subscription.find_one(Subscription.user_id == "tenant-b")

        assert a is not None and b is not None
        assert a.plan_tier == PlanTier.PRO
        assert b.plan_tier == PlanTier.ENTERPRISE

    async def test_absent_subscription_is_not_an_error(self, setup_database):
        """A tenant who never subscribed has no document. Enforcement must read that
        as FREE rather than depending on a backfill having run."""
        found = await Subscription.find_one(
            Subscription.user_id == f"never-subscribed-{PydanticObjectId()}"
        )

        assert found is None

    async def test_lookup_by_stripe_customer_id(self, setup_database):
        """The webhook arrives with Stripe ids, not our user_id."""
        await Subscription(
            user_id=TEST_USER,
            stripe_customer_id="cus_lookup",
            plan_tier=PlanTier.PRO,
            status=SubscriptionStatus.ACTIVE,
        ).insert()

        found = await Subscription.find_one(
            Subscription.stripe_customer_id == "cus_lookup"
        )

        assert found is not None
        assert found.user_id == TEST_USER


@pytest.mark.asyncio
class TestIndexDeclaration:
    """The unique index must initialise on a database that already has it (#366 review).

    An earlier draft declared it twice — a field-level `Indexed(unique=True)` AND an
    explicit `IndexModel(..., name="uniq_user_id")`. Two definitions for one key
    pattern under different names makes Mongo reject the second with `Index already
    exists with a different name`, which is a hard startup crash rather than a
    warning. It passed on a fresh collection, which is exactly why it needed a test
    that is not fresh.
    """

    async def test_initialises_against_a_pre_existing_user_id_index(self):
        client = AsyncIOMotorClient("mongodb://localhost:27017")
        db = client["subscription_index_regression_366"]
        try:
            await db.drop_collection("subscriptions")
            # What a deployment created by an earlier version would already have.
            await db["subscriptions"].create_index([("user_id", 1)], unique=True)

            await init_beanie(database=db, document_models=[Subscription])

            names = set(await db["subscriptions"].index_information())
            assert "user_id_1" in names
            # A second unique index on the same key under another name is the bug.
            user_id_indexes = [
                n
                for n, spec in (await db["subscriptions"].index_information()).items()
                if spec.get("key") == [("user_id", 1)]
            ]
            assert len(user_id_indexes) == 1, user_id_indexes
        finally:
            await client.drop_database("subscription_index_regression_366")
            client.close()
