"""Usage metering against real Mongo (#369).

The properties worth pinning are the ones where being wrong costs money or blocks a
paying customer:

* concurrent increments must not lose counts — under-counting gives usage away
* the read path must NOT fail open, or a storage blip grants unlimited quota
* recording must never break the request it is metering
* rollover must happen by the period key changing, with no job to forget to run
"""

import asyncio
from datetime import UTC, datetime

import pytest
from pymongo.errors import DuplicateKeyError

from app.billing import metering
from app.billing.plans import METERED_METRICS, PLAN_LIMITS
from app.models.subscription import PlanTier, Subscription, SubscriptionStatus
from app.models.usage import UsageRecord

TEST_USER = "test_user_123"


class TestPeriodKey:
    def test_is_the_calendar_month(self):
        assert metering.period_key_for(datetime(2026, 8, 2, tzinfo=UTC)) == "2026-08"

    def test_pads_single_digit_months(self):
        """String keys sort lexicographically; '2026-9' would sort after '2026-10'."""
        assert metering.period_key_for(datetime(2026, 9, 30, tzinfo=UTC)) == "2026-09"

    def test_changes_at_the_month_boundary(self):
        """Rollover is the key changing — there is no reset job to fail to run."""
        assert metering.period_key_for(
            datetime(2026, 8, 31, 23, 59, tzinfo=UTC)
        ) != metering.period_key_for(datetime(2026, 9, 1, 0, 1, tzinfo=UTC))


@pytest.mark.asyncio
class TestRecording:
    async def test_records_and_reads_back(self, setup_database):
        await metering.record(TEST_USER, "predictions")
        await metering.record(TEST_USER, "predictions", amount=4)

        assert await metering.usage_for(TEST_USER, "predictions") == 5

    async def test_metrics_are_counted_separately(self, setup_database):
        await metering.record(TEST_USER, "predictions", amount=3)
        await metering.record(TEST_USER, "training_runs", amount=1)

        assert await metering.usage_for(TEST_USER, "predictions") == 3
        assert await metering.usage_for(TEST_USER, "training_runs") == 1

    async def test_tenants_are_counted_separately(self, setup_database):
        await metering.record("tenant-a", "uploads", amount=2)
        await metering.record("tenant-b", "uploads", amount=7)

        assert await metering.usage_for("tenant-a", "uploads") == 2
        assert await metering.usage_for("tenant-b", "uploads") == 7

    async def test_concurrent_increments_do_not_lose_counts(self, setup_database):
        """The reason this is a `$inc` upsert and not read-modify-write.

        Fifty concurrent predictions must count as fifty. A read-then-write would
        interleave and lose some — and under-counting is the direction that gives
        usage away for free.
        """
        await asyncio.gather(
            *(metering.record(TEST_USER, "predictions") for _ in range(50))
        )

        assert await metering.usage_for(TEST_USER, "predictions") == 50

    async def test_a_duplicate_key_race_is_retried_not_swallowed(
        self, setup_database, monkeypatch
    ):
        """The first writes for a new key race on the unique index (#369 review).

        Both find nothing, both try to insert, one loses with DuplicateKeyError. A
        blanket `except Exception` would log it and move on — silently under-counting,
        which is the one failure mode this module exists to avoid. The retry runs
        without upsert, since the document is guaranteed to exist by then.
        """
        # Model the race faithfully: the writer that WON has already created the
        # document, which is why the retry can drop `upsert` and still land.
        await UsageRecord(
            user_id=TEST_USER,
            period_key=metering.period_key_for(),
            metric="predictions",
            units=1,
        ).insert()

        real = UsageRecord.get_motor_collection().update_one
        calls = {"n": 0}

        async def _fail_first_then_delegate(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise DuplicateKeyError("simulated first-write race")
            return await real(*args, **kwargs)

        monkeypatch.setattr(
            UsageRecord.get_motor_collection(), "update_one", _fail_first_then_delegate
        )

        await metering.record(TEST_USER, "predictions", amount=3)

        assert calls["n"] == 2, "expected exactly one retry"
        # 1 from the winner + 3 from the write that lost and retried. Swallowing
        # the DuplicateKeyError would leave this at 1.
        assert await metering.usage_for(TEST_USER, "predictions") == 4

    async def test_unknown_metric_is_rejected(self, setup_database):
        with pytest.raises(KeyError):
            await metering.record(TEST_USER, "bandwidth")

    async def test_zero_and_negative_amounts_are_ignored(self, setup_database):
        """A negative amount would be a refund path nobody has designed; silently
        decrementing a billing counter is worse than doing nothing."""
        await metering.record(TEST_USER, "predictions", amount=0)
        await metering.record(TEST_USER, "predictions", amount=-5)

        assert await metering.usage_for(TEST_USER, "predictions") == 0

    async def test_recording_never_raises_on_storage_failure(
        self, setup_database, monkeypatch
    ):
        """The user has already had the work done; refusing them the result because
        a counter did not increment helps nobody."""

        def _boom(*_args, **_kwargs):
            raise RuntimeError("mongo is down")

        monkeypatch.setattr(UsageRecord, "get_motor_collection", _boom)

        await metering.record(TEST_USER, "predictions")  # must not raise


@pytest.mark.asyncio
class TestReading:
    async def test_absent_record_reads_as_zero(self, setup_database):
        assert await metering.usage_for("never-used-anything", "predictions") == 0

    async def test_the_read_path_does_not_fail_open(self, setup_database, monkeypatch):
        """`usage_for` deliberately does NOT swallow errors the way `record` does.

        Returning 0 on a storage failure would grant unlimited quota — which is the
        precise reason the #151 rate-limit buckets, which fail open by design, were
        unsuitable for billing.
        """

        async def _boom(*_args, **_kwargs):
            raise RuntimeError("mongo is down")

        monkeypatch.setattr(UsageRecord, "find_one", _boom)

        with pytest.raises(RuntimeError):
            await metering.usage_for(TEST_USER, "predictions")

    async def test_summary_reports_every_metric(self, setup_database):
        await metering.record(TEST_USER, "predictions", amount=2)

        summary = await metering.usage_summary(TEST_USER)

        assert set(summary) == set(METERED_METRICS)
        assert summary["predictions"] == 2
        # Unused metrics read as 0 rather than being absent, so a usage panel does
        # not have to special-case a feature the tenant has not touched.
        assert summary["uploads"] == 0

    async def test_usage_is_scoped_to_the_period(self, setup_database):
        """A record from another period must not count against this one."""
        await UsageRecord(
            user_id=TEST_USER,
            period_key="1999-01",
            metric="predictions",
            units=9_999,
        ).insert()

        assert await metering.usage_for(TEST_USER, "predictions") == 0


@pytest.mark.asyncio
class TestTierAndRemaining:
    async def test_no_subscription_means_free(self, setup_database):
        assert await metering.effective_tier_for("never-subscribed") == PlanTier.FREE

    async def test_canceled_subscription_falls_back_to_free(self, setup_database):
        await Subscription(
            user_id=TEST_USER,
            plan_tier=PlanTier.PRO,
            status=SubscriptionStatus.CANCELED,
        ).insert()

        assert await metering.effective_tier_for(TEST_USER) == PlanTier.FREE

    async def test_remaining_counts_down_from_the_tier_limit(self, setup_database):
        limit = PLAN_LIMITS[PlanTier.FREE].training_runs
        await metering.record(TEST_USER, "training_runs", amount=2)

        assert await metering.remaining(TEST_USER, "training_runs") == limit - 2

    async def test_remaining_never_goes_negative(self, setup_database):
        limit = PLAN_LIMITS[PlanTier.FREE].training_runs
        await metering.record(TEST_USER, "training_runs", amount=limit + 10)

        assert await metering.remaining(TEST_USER, "training_runs") == 0

    async def test_remaining_is_none_when_unlimited(self, setup_database):
        await Subscription(
            user_id=TEST_USER,
            plan_tier=PlanTier.ENTERPRISE,
            status=SubscriptionStatus.ACTIVE,
        ).insert()

        assert await metering.remaining(TEST_USER, "training_runs") is None
