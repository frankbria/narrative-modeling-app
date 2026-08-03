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
from pymongo.errors import DuplicateKeyError

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

    async def test_concurrent_first_use_does_not_deny_anyone_spuriously(
        self, setup_database
    ):
        """The other half of the race, which the test above cannot see.

        On the FIRST consume of a period there is no record, so every concurrent
        caller takes the upsert's insert path and all but one collide on the unique
        index. Treating that collision as "full" denies callers who had quota — and
        the assertion above still reads 5, because the survivors go on to fill the
        limit through the update path. Only a limit wider than the fan-out exposes
        it: ten callers, limit twenty, nobody should be turned away.

        This does NOT reliably reproduce the collision — the server retries it
        internally most of the time, which is exactly why it is unsafe to rely on.
        `test_a_duplicate_key_collision_is_retried_not_denied` forces it.
        """
        results = await asyncio.gather(
            *(metering.consume("u-cold", "uploads", limit=20) for _ in range(10))
        )

        assert sum(results) == 10
        assert await _units("u-cold", "uploads") == 10


    async def test_a_duplicate_key_collision_is_retried_not_denied(
        self, setup_database, monkeypatch
    ):
        """A collision means "someone else inserted first", not "you are full".

        Mongo can return `DuplicateKeyError` from an upsert whose filter missed
        because another writer inserted the record a moment earlier — the same race
        `record()` already retries. Reading every collision as exhausted quota turns
        it into a spurious 402 for a tenant with plenty left.

        Forced rather than raced: the server usually retries this internally, so a
        concurrency test observes it only occasionally. Injecting it makes the
        assertion deterministic.
        """
        real = UsageRecord.get_motor_collection()
        calls = {"n": 0}

        class CollideOnce:
            """Stands in for losing the insert race to a concurrent writer.

            It *writes the record* before raising, which is the part that makes the
            simulation faithful: a real collision means the winner's document now
            exists. A stub that only raises leaves nothing behind, and then the
            no-upsert retry finds no record and correctly denies — testing the
            wrong thing.
            """

            async def update_one(self, *args, **kwargs):
                calls["n"] += 1
                if calls["n"] == 1:
                    await real.insert_one(
                        {
                            "user_id": "u-collide",
                            "period_key": metering.period_key_for(),
                            "metric": "uploads",
                            "units": 1,
                        }
                    )
                    raise DuplicateKeyError("E11000 duplicate key")
                return await real.update_one(*args, **kwargs)

        monkeypatch.setattr(
            UsageRecord, "get_motor_collection", staticmethod(lambda: CollideOnce())
        )

        assert await metering.consume("u-collide", "uploads", limit=20) is True
        assert calls["n"] == 2  # collided once, retried once — not a loop

        monkeypatch.undo()
        # The winner's 1 plus ours. Nothing was lost to the collision, which is the
        # difference between this and denying on it.
        assert await _units("u-collide", "uploads") == 2

    async def test_being_at_the_cap_is_not_logged_as_an_error(
        self, setup_database, caplog
    ):
        """A tenant sitting on their limit is routine, not an incident.

        Guards the reason the retry runs without `upsert`: retrying WITH one sends
        every capped request back down the insert path to collide a second time, so
        the ordinary "you are full" answer arrives as an exception and a warning.
        Same return value, so only this assertion catches it — and a plan-limits
        log that cries wolf on every capped free user is one nobody reads.
        """
        await metering.consume("u-quiet", "uploads", limit=1)

        with caplog.at_level("WARNING", logger="app.billing.metering"):
            assert await metering.consume("u-quiet", "uploads", limit=1) is False

        assert caplog.records == []

    async def test_a_second_collision_denies(self, setup_database, monkeypatch):
        """The retry is one deep, and it fails closed.

        The retry runs without `upsert`, so it has no insert to collide on and this
        should be unreachable. Asserted anyway: enforcement's contract is that an
        unexpected state denies rather than hands out quota, and an unhandled
        DuplicateKeyError here would escape as a 500 instead.
        """

        class AlwaysCollide:
            async def update_one(self, *args, **kwargs):
                raise DuplicateKeyError("E11000 duplicate key")

        monkeypatch.setattr(
            UsageRecord, "get_motor_collection", staticmethod(lambda: AlwaysCollide())
        )

        assert await metering.consume("u-collide2", "uploads", limit=20) is False


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
