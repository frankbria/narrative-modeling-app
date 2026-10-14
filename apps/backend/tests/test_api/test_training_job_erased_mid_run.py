"""#936: a training job whose row is erased while it runs stays erased.

`train_model_task` keeps its `TrainingJob` in memory for the whole run. Its terminal
handlers re-read the row, fell back to the in-memory copy when it was gone, and saved
it: a Beanie `save()` of a missing document inserts it. So erasing the dataset or the
account during a run was undone by the task's last write, which on success also stored
a model for the data the tenant had asked to have removed.

The real task runs against the real test database. The fit is a stand-in held open on
an event, which is where the erasure lands.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.training_job import JobStatus, TrainingJob
from tests.test_api.test_training_dataset_load import _dataset
from tests.test_api.test_training_queue_and_reaper import CSV, _job, _stored

pytestmark = pytest.mark.asyncio


class _Run:
    """The task, with a stand-in engine and model store."""

    def __init__(self, model_id: str, *, fit_fails: bool = False):
        self.model_id, self.fit_fails = model_id, fit_fails
        self.fitting, self.resume = asyncio.Event(), asyncio.Event()
        self.save_model = AsyncMock(return_value=MagicMock(model_id=model_id))
        self.delete_model = AsyncMock(return_value=True)

    async def _fit(self, *_args, **_kwargs):
        self.fitting.set()
        await self.resume.wait()
        if self.fit_fails:
            raise RuntimeError("the fit failed")
        return MagicMock()

    async def to_the_end(self) -> None:
        from app.api.routes.model_training import TrainModelRequest, train_model_task

        with (
            patch("app.services.s3_service.S3Service.download_file_bytes", AsyncMock(return_value=CSV)),
            patch("app.api.routes.model_training.AutoMLEngine") as engine,
            patch("app.api.routes.model_training.ModelStorageService") as storage,
        ):
            engine.return_value.run = self._fit
            storage.return_value.save_model = self.save_model
            storage.return_value.delete_model = self.delete_model
            await train_model_task(
                _dataset(), TrainModelRequest(dataset_id="dataset_665", target_column="target"),
                "test_user", self.model_id,
            )


async def _erase(model_id: str) -> None:
    """What `POST /datasets/{id}/erase` and `POST /users/me/erase` do to the job."""
    await TrainingJob.find_one(TrainingJob.model_id == model_id).delete()


async def _erased_during_the_fit(run: _Run) -> None:
    await _job(run.model_id)
    task = asyncio.create_task(run.to_the_end())
    await asyncio.wait_for(run.fitting.wait(), 10)
    await _erase(run.model_id)
    run.resume.set()
    await task


async def test_a_job_erased_during_the_fit_saves_no_model_and_is_not_written_back(setup_database):
    run = _Run("model_936_fit")

    await _erased_during_the_fit(run)

    run.save_model.assert_not_awaited()
    assert await _stored("model_936_fit") is None


async def test_a_job_erased_during_a_fit_that_then_fails_is_not_written_back(setup_database, caplog):
    run = _Run("model_936_fails", fit_fails=True)

    await _erased_during_the_fit(run)

    assert await _stored("model_936_fails") is None
    assert "Failed to persist" not in caplog.text, "an erased job is not a failed write"
    assert "nothing is recorded" in caplog.text


async def _erased_while_the_model_is_stored(run: _Run) -> None:
    """The gap after the check: the erasure lands during the S3 write of the model."""

    async def store_then_erase(*_args, **_kwargs):
        await _erase(run.model_id)
        return MagicMock(model_id=run.model_id)

    run.save_model.side_effect = store_then_erase
    await _job(run.model_id)
    run.resume.set()
    await run.to_the_end()


async def test_a_job_erased_while_its_model_is_stored_takes_the_model_with_it(setup_database):
    run = _Run("model_936_stored")

    await _erased_while_the_model_is_stored(run)

    run.save_model.assert_awaited_once()
    run.delete_model.assert_awaited_once_with("model_936_stored", "test_user")
    assert await _stored("model_936_stored") is None


async def test_a_model_that_cannot_be_removed_does_not_bring_the_job_back(setup_database):
    """Removing the model is best effort (S3 can fail). The row still stays erased, and
    the background task still ends without raising."""
    run = _Run("model_936_stuck")
    run.delete_model.side_effect = RuntimeError("S3 is unreachable")

    await _erased_while_the_model_is_stored(run)

    assert await _stored("model_936_stuck") is None


async def test_a_job_erased_between_the_last_read_and_the_last_write_is_not_written_back(setup_database):
    """The re-read and the write are two round trips, and an erasure can land between
    them. The write itself must refuse a row that is gone."""
    from app.api.routes import model_training

    run = _Run("model_936_race", fit_fails=True)
    read = model_training._refreshed_job

    async def read_then_erase(job):
        fresh = await read(job)
        await _erase(job.model_id)
        return fresh

    await _job(run.model_id)
    run.resume.set()
    with patch.object(model_training, "_refreshed_job", read_then_erase):
        await run.to_the_end()

    assert await _stored("model_936_race") is None


async def test_a_job_the_reaper_ended_during_the_fit_keeps_the_reapers_verdict(setup_database):
    """The same check covers a run the reaper failed and refunded while it fitted (#901
    covered only the wait for a slot)."""
    run = _Run("model_936_reaped")
    await _job(run.model_id)
    task = asyncio.create_task(run.to_the_end())
    await asyncio.wait_for(run.fitting.wait(), 10)
    await TrainingJob.find_one(TrainingJob.model_id == run.model_id).update(
        {"$set": {"status": JobStatus.FAILED.value, "error": "reaped"}}
    )
    run.resume.set()
    await task

    run.save_model.assert_not_awaited()
    after = await _stored("model_936_reaped")
    assert (after.status, after.error) == (JobStatus.FAILED, "reaped")


# #945: the two windows #936 left.


async def test_a_job_erased_before_its_task_starts_is_not_run(setup_database):
    """The route creates the row before it schedules the task, so a lookup that finds
    nothing at entry means it was erased in between. The task trained anyway."""
    run = _Run("model_945_gone")
    run.resume.set()

    await run.to_the_end()  # no job row

    assert not run.fitting.is_set(), "the model was not fitted"
    run.save_model.assert_not_awaited()
    assert await _stored("model_945_gone") is None


async def test_a_model_stored_for_an_erased_job_marks_no_version_and_records_no_event(setup_database):
    """The version mark and the first-model event ran after the model was stored and
    before the re-read that notices the row is gone; they now follow it."""
    from app.api.routes import model_training

    run = _Run("model_945_marks")
    with (
        patch.object(model_training, "_mark_version_trained_on", AsyncMock()) as mark,
        patch.object(model_training.product_events, "record", AsyncMock()) as event,
    ):
        await _erased_while_the_model_is_stored(run)

    mark.assert_not_awaited()
    event.assert_not_awaited()
    run.delete_model.assert_awaited_once_with("model_945_marks", "test_user")


async def test_a_completed_job_still_marks_its_version_and_records_the_event(setup_database):
    from app.api.routes import model_training

    run = _Run("model_945_done")
    await _job(run.model_id)
    run.resume.set()
    with (
        patch.object(model_training, "_mark_version_trained_on", AsyncMock()) as mark,
        patch.object(model_training.product_events, "record", AsyncMock()) as event,
        patch.object(model_training, "_record_completion", AsyncMock()),
    ):
        await run.to_the_end()

    mark.assert_awaited_once()
    event.assert_awaited_once()
