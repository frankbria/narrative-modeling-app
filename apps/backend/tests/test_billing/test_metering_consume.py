"""Atomic check-and-consume (#368).

`remaining()` cannot back a hard limit: it composes two reads, so N concurrent
callers all see room and all proceed. These tests are about the primitive that
replaces it — one conditional `$inc` where the check and the consume are the same
operation.

The concurrency test is the point of the file. A `consume()` built on
read-then-write passes every single-threaded test here and fails only that one.
"""

import asyncio

import pytest

from app.billing import metering
from app.billing.plans import UNLIMITED
from app.models.usage import UsageRecord

pytestmark = pytest.mark.asyncio


async def _units(user_id: str, metric: str) -> int:
    doc = await UsageRecord.find_one(
        UsageRecord.user_id == user_id,
        UsageRecord.period_key == metering.period_key_for(),
        UsageRecord.metric == metric,
    )
    return doc.units if doc else 0


class TestConsume:
    async def test_first_use_creates_the_record_and_allows(self, setup_database):
        assert await metering.consume("u-first", "predictions", limit=5) is True
        assert await _units("u-first", "predictions") == 1

    async def test_allows_up_to_the_limit_then_denies(self, setup_database):
        for i in range(3):
            assert await metering.consume("u-wall", "uploads", limit=3) is True, i

        assert await metering.consume("u-wall", "uploads", limit=3) is False
        # The denied call must not have consumed anything. A naive
        # "increment then compare" would leave 4 here and hand the tenant a
        # permanent deficit they cannot spend down.
        assert await _units("u-wall", "uploads") == 3

    async def test_a_zero_limit_denies_the_very_first_request(self, setup_database):
        # The insert path is the dangerous one: with no record to filter against,
        # an unguarded upsert creates units=1 under a limit of 0.
        assert await metering.consume("u-zero", "predictions", limit=0) is False
        assert await _units("u-zero", "predictions") == 0

    async def test_an_amount_larger_than_the_limit_is_denied_not_inserted(
        self, setup_database
    ):
        assert (
            await metering.consume("u-big", "predictions", limit=10, amount=25) is False
        )
        assert await _units("u-big", "predictions") == 0

    async def test_an_amount_that_exactly_fills_the_limit_is_allowed(
        self, setup_database
    ):
        assert (
            await metering.consume("u-exact", "predictions", limit=10, amount=10) is True
        )
        assert await _units("u-exact", "predictions") == 10
        assert await metering.consume("u-exact", "predictions", limit=10) is False

    async def test_unlimited_allows_and_still_counts(self, setup_database):
        # Unlimited tenants are not exempt from *counting* — usage reporting and
        # any future overage pricing both need the number.
        assert await metering.consume("u-unl", "predictions", limit=UNLIMITED) is True
        assert await _units("u-unl", "predictions") == 1

    async def test_tenants_do_not_share_a_quota(self, setup_database):
        assert await metering.consume("tenant-a", "uploads", limit=1) is True
        assert await metering.consume("tenant-b", "uploads", limit=1) is True
        assert await metering.consume("tenant-a", "uploads", limit=1) is False

    async def test_metrics_do_not_share_a_quota(self, setup_database):
        assert await metering.consume("u-split", "uploads", limit=1) is True
        assert await metering.consume("u-split", "predictions", limit=1) is True

    async def test_an_unknown_metric_raises(self, setup_database):
        # Same reasoning as `usage_for`: a drifted name must not read as a full
        # quota and wave everything through.
        with pytest.raises(KeyError):
            await metering.consume("u-typo", "predictionz", limit=5)

    async def test_concurrent_callers_cannot_exceed_the_limit(self, setup_database):
        """The whole reason this primitive exists.

        Twenty simultaneous requests against a limit of 5. A read-then-write
        implementation lets most of them through, because they all read 0 before
        any of them writes.
        """
        results = await asyncio.gather(
            *(metering.consume("u-race", "predictions", limit=5) for _ in range(20))
        )

        assert sum(results) == 5
        assert await _units("u-race", "predictions") == 5


class TestRefund:
    async def test_refund_returns_units_to_the_pool(self, setup_database):
        await metering.consume("u-refund", "uploads", limit=1)
        assert await metering.consume("u-refund", "uploads", limit=1) is False

        await metering.refund("u-refund", "uploads")

        assert await _units("u-refund", "uploads") == 0
        assert await metering.consume("u-refund", "uploads", limit=1) is True

    async def test_refund_never_goes_negative(self, setup_database):
        # A refund larger than what is reserved must not mint quota — a negative
        # balance turns every failed request into free credit against the next
        # period's first requests.
        #
        # The record has to EXIST for this to test anything: with no document,
        # an unclamped `$inc` matches nothing and the assertion passes against a
        # broken implementation. That is exactly how the first version of this
        # test let a missing clamp through.
        await metering.consume("u-neg", "uploads", limit=10)
        assert await _units("u-neg", "uploads") == 1

        await metering.refund("u-neg", "uploads", amount=5)

        assert await _units("u-neg", "uploads") == 1

    async def test_refund_with_nothing_reserved_creates_no_record(
        self, setup_database
    ):
        await metering.refund("u-none", "uploads", amount=3)
        assert await _units("u-none", "uploads") == 0

    async def test_refund_swallows_storage_failures(self, setup_database, monkeypatch):
        # A refund failing must not turn a 4xx into a 500. The tenant already has
        # their error; losing a unit is the lesser harm.
        class Boom:
            async def update_one(self, *a, **k):
                raise RuntimeError("mongo is down")

        monkeypatch.setattr(UsageRecord, "get_motor_collection", lambda: Boom())
        await metering.refund("u-boom", "uploads")  # must not raise
