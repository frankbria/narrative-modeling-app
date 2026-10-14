"""#853: one holder at a time for work on a dataset, across workers.

The lease is a document whose `_id` is its name, so these run against real MongoDB:
the insert that collides is the mechanism.
"""

import asyncio
from datetime import timedelta

import pytest

from app.models.dataset_lease import DatasetLease
from app.models.transformation import TransformationConfig
from app.services import dataset_lease as lease
from app.services.dataset_lease import LeaseBusy, dataset_lease
from app.services.transformation_service import TransformationService
from app.utils.datetime import utcnow

pytestmark = pytest.mark.asyncio


async def test_the_second_caller_runs_only_after_the_first_has_finished(setup_database):
    order: list[str] = []

    async def work(who: str) -> None:
        async with dataset_lease("apply:u:d"):
            order.append(f"{who} starts")
            await asyncio.sleep(0.2)
            order.append(f"{who} ends")

    await asyncio.gather(work("a"), work("b"))

    assert order in (
        ["a starts", "a ends", "b starts", "b ends"],
        ["b starts", "b ends", "a starts", "a ends"],
    )
    assert await DatasetLease.find_all().count() == 0, "released when the work is done"


async def test_leases_with_different_names_do_not_wait_for_each_other(setup_database):
    async with dataset_lease("apply:u:one"):
        async with dataset_lease("apply:u:two", wait_seconds=0):
            assert await DatasetLease.find_all().count() == 2


async def test_a_lease_still_held_when_the_wait_runs_out_is_reported(setup_database):
    async with dataset_lease("apply:u:d"):
        with pytest.raises(LeaseBusy):
            async with dataset_lease("apply:u:d", wait_seconds=0.3):
                pytest.fail("two holders at once")


async def test_the_lease_of_a_holder_that_died_is_taken_over(setup_database):
    await DatasetLease(id="apply:u:d", holder="a worker that was killed", expires_at=utcnow() - timedelta(seconds=1)).insert()

    async with dataset_lease("apply:u:d", wait_seconds=0):
        held = await DatasetLease.find_one({"_id": "apply:u:d"})
        assert held.holder != "a worker that was killed"


async def test_work_longer_than_the_lease_is_still_one_holder(setup_database, monkeypatch):
    """A slow apply is not a dead one: its lease is renewed while it runs (codex review)."""
    monkeypatch.setattr(lease, "LEASE_SECONDS", 0.3)
    monkeypatch.setattr(lease, "RENEW_SECONDS", 0.1)

    async with dataset_lease("apply:u:d"):
        await asyncio.sleep(0.6)  # twice the lease
        with pytest.raises(LeaseBusy):
            async with dataset_lease("apply:u:d", wait_seconds=0.2):
                pytest.fail("the lease of a holder that is still running was taken")


async def test_a_renewal_that_fails_is_tried_again_and_does_not_stop_the_work(setup_database, monkeypatch):
    monkeypatch.setattr(lease, "RENEW_SECONDS", 0.05)
    renewals = 0

    def unreachable(*_args, **_kwargs):
        nonlocal renewals
        renewals += 1
        raise RuntimeError("mongo is away")

    async with dataset_lease("apply:u:d"):
        monkeypatch.setattr(lease.DatasetLease, "find", unreachable)
        await asyncio.sleep(0.2)
        monkeypatch.undo()

    assert renewals >= 2
    assert await DatasetLease.find_all().count() == 0, "released as usual"


async def test_a_run_that_outlived_its_lease_does_not_release_its_successors(setup_database):
    async with dataset_lease("apply:u:d"):
        # This holder's lease expired and someone else took it.
        await DatasetLease.find({"_id": "apply:u:d"}).delete()
        await DatasetLease(id="apply:u:d", holder="the successor", expires_at=utcnow() + timedelta(seconds=60)).insert()

    assert (await DatasetLease.find_one({"_id": "apply:u:d"})).holder == "the successor"


async def test_a_release_that_fails_does_not_fail_the_work(setup_database, monkeypatch):
    def unreachable(*_args, **_kwargs):
        raise RuntimeError("mongo is away")

    async with dataset_lease("apply:u:d"):
        monkeypatch.setattr(lease.DatasetLease, "find", unreachable)
    monkeypatch.undo()

    assert await DatasetLease.find_all().count() == 1, "left to expire"


async def test_an_apply_that_cannot_get_the_lease_says_so_and_writes_nothing(setup_database, monkeypatch):
    monkeypatch.setattr(lease, "WAIT_SECONDS", 0.2)

    async with dataset_lease("apply:u853:d853"):
        answer = await TransformationService().apply_pipeline("u853", "d853", [("trim_whitespace", {})])

    assert answer["success"] is False
    assert "still being applied" in answer["error"]
    assert await TransformationConfig.find_all().count() == 0
