"""#901: a training job that waits for a slot is alive, and one the reaper ended stays ended.

`train_model_task` waits for the per-process training semaphore before it starts the
heartbeat pump. Nothing bumped `last_heartbeat` during the wait, so a job queued longer
than the stale-job timeout was failed and refunded by the reaper while it was only
waiting its turn. The task was still alive: when a slot freed it trained anyway, and
wrote its own terminal state over the reaper's. The tenant got a refunded run and a model.
"""
import asyncio
import functools
from unittest.mock import AsyncMock, patch

import pytest

from app.models.training_job import JobStatus, TrainingJob
from app.services.job_reaper import reap_stale_jobs
from app.services.training_admission import (
    MAX_CONCURRENT_TRAINING_JOBS,
    training_semaphore,
)
from app.utils.heartbeat import heartbeat_pump
from tests.test_api.test_training_dataset_load import _dataset, _run

pytestmark = pytest.mark.asyncio

CSV = b"a,target\n1,0\n2,1\n"


async def _job(model_id: str) -> TrainingJob:
    job = TrainingJob(model_id=model_id, user_id="test_user", dataset_id="dataset_665", target_column="target")
    await job.insert()
    return job


async def _stored(model_id: str) -> TrainingJob:
    return await TrainingJob.find_one(TrainingJob.model_id == model_id)


class _EverySlotTaken:
    """Hold every training slot, as long jobs ahead in the queue would."""

    async def __aenter__(self):
        self.slots = training_semaphore()
        for _ in range(MAX_CONCURRENT_TRAINING_JOBS):
            await self.slots.acquire()
        return self

    def free(self) -> None:
        for _ in range(MAX_CONCURRENT_TRAINING_JOBS):
            self.slots.release()
        self.freed = True

    async def __aexit__(self, *_exc):
        if not getattr(self, "freed", False):
            self.free()


async def test_a_job_waiting_for_a_slot_is_not_reaped(setup_database):
    await _job("model_901_waiting")
    download, seen = AsyncMock(return_value=CSV), []
    quick_beat = functools.partial(heartbeat_pump, interval=0.05)

    with patch("app.api.routes.model_training.heartbeat_pump", quick_beat):
        async with _EverySlotTaken() as queue:
            task = asyncio.create_task(_run(_dataset(), "model_901_waiting", download, seen))
            await asyncio.sleep(0.5)  # well past the stale timeout used below

            reaped = await reap_stale_jobs(timeout_seconds=0.25)

            assert reaped.training == 0, "a job that is waiting its turn is not a dead job"
            assert (await _stored("model_901_waiting")).status == JobStatus.RUNNING
            queue.free()
            await task

    assert seen == [(2, 2)], "and it trains once a slot is free"


async def test_a_job_the_reaper_ended_while_it_queued_does_not_train(setup_database):
    """The pump can still miss (a worker stalled past the timeout): the task must then
    find out on taking the slot, not after training."""
    await _job("model_901_reaped")
    download, seen = AsyncMock(return_value=CSV), []

    async with _EverySlotTaken() as queue:
        task = asyncio.create_task(_run(_dataset(), "model_901_reaped", download, seen))
        # Wait for the task to mark the job running (a loaded CI runner can take longer
        # than any fixed sleep), then outlast the timeout. The default beat is 60s, so no
        # heartbeat lands in this time.
        while (await _stored("model_901_reaped")).status != JobStatus.RUNNING:
            await asyncio.sleep(0.02)
        await asyncio.sleep(0.3)
        reaped = await reap_stale_jobs(timeout_seconds=0.1)
        assert reaped.training == 1, "precondition: the reaper ended the queued job"
        ended = await _stored("model_901_reaped")

        queue.free()
        await task

    assert seen == [], "a job already failed and refunded must not go on to train"
    download.assert_not_awaited()
    after = await _stored("model_901_reaped")
    assert (after.status, after.error) == (JobStatus.FAILED, ended.error), "the reaper's verdict stands"


async def test_a_job_erased_while_it_queued_does_not_train_and_is_not_written_back(setup_database):
    """An erasure of the dataset or the account deletes the job's row. The task holds a
    copy in memory; training on, or saving that copy, would undo the erasure."""
    await _job("model_901_erased")
    download, seen = AsyncMock(return_value=CSV), []

    async with _EverySlotTaken() as queue:
        task = asyncio.create_task(_run(_dataset(), "model_901_erased", download, seen))
        await asyncio.sleep(0.2)
        await TrainingJob.find_one(TrainingJob.model_id == "model_901_erased").delete()

        queue.free()
        await task

    assert seen == []
    download.assert_not_awaited()
    assert await _stored("model_901_erased") is None, "the task must not write its copy back"


async def test_the_waiting_line_does_not_overwrite_a_cancellation(setup_database):
    """The line was written with a save of the task's whole in-memory document, which
    put `cancellation_requested` back to what it was when the task loaded it."""
    from app.api.routes.model_training import _log_waiting_for_slot

    loaded = await _job("model_901_cancelled")
    await TrainingJob.find_one(TrainingJob.model_id == "model_901_cancelled").update(
        {"$set": {"cancellation_requested": True}}
    )

    await _log_waiting_for_slot(loaded)

    stored = await _stored("model_901_cancelled")
    assert stored.cancellation_requested is True
    assert stored.logs[-1].message.startswith("Waiting for an available training slot")


class TestOnTakingTheSlot:
    async def test_a_job_still_in_flight_goes_ahead(self, setup_database):
        from app.api.routes.model_training import _require_in_flight

        await _require_in_flight(await _job("model_901_live"))

    async def test_a_job_cancelled_while_queued_is_cancelled(self, setup_database):
        from app.api.routes.model_training import _require_in_flight
        from app.services.model_training.automl_engine import TrainingCancelledError

        loaded = await _job("model_901_cancel")
        await TrainingJob.find_one(TrainingJob.model_id == "model_901_cancel").update(
            {"$set": {"cancellation_requested": True}}
        )

        with pytest.raises(TrainingCancelledError):
            await _require_in_flight(loaded)

    @pytest.mark.parametrize("status", [JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.COMPLETED])
    async def test_a_job_something_else_ended_is_not_run(self, setup_database, status):
        from app.api.routes.model_training import (
            TrainingNoLongerInFlight,
            _require_in_flight,
        )

        loaded = await _job(f"model_901_{status.value}")
        await TrainingJob.find_one(TrainingJob.model_id == loaded.model_id).update(
            {"$set": {"status": status.value}}
        )

        with pytest.raises(TrainingNoLongerInFlight):
            await _require_in_flight(loaded)

    async def test_a_job_whose_row_is_gone_is_not_run(self, setup_database):
        from app.api.routes.model_training import (
            TrainingNoLongerInFlight,
            _require_in_flight,
        )

        loaded = await _job("model_901_gone")
        await loaded.delete()

        with pytest.raises(TrainingNoLongerInFlight, match="deleted"):
            await _require_in_flight(loaded)

    async def test_a_status_read_that_fails_does_not_block_a_valid_run(self, setup_database):
        from app.api.routes.model_training import _require_in_flight

        loaded = await _job("model_901_unreadable")
        with patch.object(TrainingJob, "find_one", side_effect=RuntimeError("the database went away")):
            await _require_in_flight(loaded)
