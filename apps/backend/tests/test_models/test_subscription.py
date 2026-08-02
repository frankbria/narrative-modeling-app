"""Subscription model and plan limits (#366).

The parts worth pinning are the ones where a wrong answer silently grants or
revokes paid access:

* a status Stripe sends that we do not model must not default to "entitled"
* a canceled subscription must stop granting the tier it records
* past-due must keep granting it, because Stripe retries for days
* no Subscription document at all must mean FREE, not a crash or a backfill
"""

import pytest

from app.billing.plans import PLAN_LIMITS, UNLIMITED, limits_for
from app.models.subscription import PlanTier, Subscription, SubscriptionStatus


class TestStripeStatusMapping:
    @pytest.mark.parametrize(
        ("stripe_status", "expected"),
        [
            ("active", SubscriptionStatus.ACTIVE),
            ("trialing", SubscriptionStatus.ACTIVE),
            ("past_due", SubscriptionStatus.PAST_DUE),
            ("unpaid", SubscriptionStatus.PAST_DUE),
            ("canceled", SubscriptionStatus.CANCELED),
            ("paused", SubscriptionStatus.CANCELED),
            ("incomplete", SubscriptionStatus.INCOMPLETE),
            ("incomplete_expired", SubscriptionStatus.INCOMPLETE),
        ],
    )
    def test_known_statuses_map_explicitly(self, stripe_status, expected):
        assert SubscriptionStatus.from_stripe(stripe_status) == expected

    def test_an_unknown_status_fails_closed(self):
        """Stripe can add statuses. A new one must not silently grant access."""
        assert (
            SubscriptionStatus.from_stripe("some_future_stripe_status")
            == SubscriptionStatus.INCOMPLETE
        )
        assert not _sub(status=SubscriptionStatus.INCOMPLETE).is_entitled


def _sub(**kwargs) -> Subscription:
    """Build one without touching Mongo.

    `Subscription(...)` raises CollectionWasNotInitialized outside an initialised
    Beanie app, and this module lives in the service-free CI selection — requiring
    a database here would take it out of that run. `model_construct` skips both
    validation and the collection check, which is fine because what is under test
    is the entitlement logic, not field coercion.
    """
    kwargs.setdefault("user_id", "u-1")
    kwargs.setdefault("plan_tier", PlanTier.FREE)
    kwargs.setdefault("status", SubscriptionStatus.INCOMPLETE)
    return Subscription.model_construct(**kwargs)


class TestEntitlement:
    def test_active_is_entitled(self):
        assert _sub(status=SubscriptionStatus.ACTIVE).is_entitled

    def test_past_due_is_still_entitled(self):
        """Stripe retries a failed payment for days; cutting access off at the
        first failure is worse than serving a card that is about to be updated."""
        assert _sub(status=SubscriptionStatus.PAST_DUE).is_entitled

    @pytest.mark.parametrize(
        "status", [SubscriptionStatus.CANCELED, SubscriptionStatus.INCOMPLETE]
    )
    def test_canceled_and_incomplete_are_not(self, status):
        assert not _sub(status=status).is_entitled

    def test_effective_tier_drops_to_free_when_not_entitled(self):
        """`plan_tier` records what was bought; it must not keep granting PRO
        limits after the subscription lapses."""
        sub = _sub(plan_tier=PlanTier.PRO, status=SubscriptionStatus.CANCELED)

        assert sub.plan_tier == PlanTier.PRO
        assert sub.effective_tier == PlanTier.FREE

    def test_effective_tier_holds_while_entitled(self):
        sub = _sub(plan_tier=PlanTier.PRO, status=SubscriptionStatus.PAST_DUE)
        assert sub.effective_tier == PlanTier.PRO

    def test_defaults_are_free_and_unentitled(self):
        """A document created with nothing set must not grant anything."""
        sub = _sub()
        assert sub.plan_tier == PlanTier.FREE
        assert not sub.is_entitled
        assert sub.effective_tier == PlanTier.FREE


class TestPlanLimits:
    def test_every_tier_has_limits(self):
        for tier in PlanTier:
            assert tier in PLAN_LIMITS

    def test_unknown_tier_falls_back_to_free(self):
        assert limits_for("not-a-tier") == PLAN_LIMITS[PlanTier.FREE]  # type: ignore[arg-type]

    def test_free_is_usable_rather_than_a_teaser(self):
        """A free tier that cannot train a single model makes the invite-only beta
        (ADR-001) unusable the moment enforcement is switched on."""
        free = PLAN_LIMITS[PlanTier.FREE]
        assert free.training_runs > 0
        assert free.predictions > 0
        assert free.uploads > 0

    def test_tiers_are_ordered_free_under_pro(self):
        free, pro = PLAN_LIMITS[PlanTier.FREE], PLAN_LIMITS[PlanTier.PRO]
        for metric in ("training_runs", "predictions", "uploads"):
            assert pro.limit_for(metric) > free.limit_for(metric)

    def test_unlimited_always_allows(self):
        ent = PLAN_LIMITS[PlanTier.ENTERPRISE]
        assert ent.training_runs == UNLIMITED
        assert ent.allows("training_runs", 10_000_000)

    def test_allows_is_exclusive_of_the_limit(self):
        """At the limit the tenant has spent their quota; the next call is denied."""
        free = PLAN_LIMITS[PlanTier.FREE]
        n = free.training_runs
        assert free.allows("training_runs", n - 1)
        assert not free.allows("training_runs", n)

    def test_unknown_metric_is_a_clear_error(self):
        with pytest.raises(KeyError):
            PLAN_LIMITS[PlanTier.FREE].limit_for("bandwidth")


class TestEnvOverrides:
    def test_a_malformed_override_falls_back_instead_of_crashing(self, monkeypatch):
        """A typo in a limit must not stop the app booting."""
        monkeypatch.setenv("PLAN_FREE_TRAINING_RUNS", "not-a-number")
        import importlib

        from app.billing import plans

        reloaded = importlib.reload(plans)
        try:
            assert reloaded.PLAN_LIMITS[PlanTier.FREE].training_runs == 10
        finally:
            monkeypatch.delenv("PLAN_FREE_TRAINING_RUNS", raising=False)
            importlib.reload(plans)

    def test_an_override_is_honoured(self, monkeypatch):
        monkeypatch.setenv("PLAN_FREE_TRAINING_RUNS", "3")
        import importlib

        from app.billing import plans

        reloaded = importlib.reload(plans)
        try:
            assert reloaded.PLAN_LIMITS[PlanTier.FREE].training_runs == 3
        finally:
            monkeypatch.delenv("PLAN_FREE_TRAINING_RUNS", raising=False)
            importlib.reload(plans)
