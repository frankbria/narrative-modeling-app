"""A refund owed by a settled job is paid exactly once, even across a crash (#1032).

Settling a job and returning its units are writes to two collections. The job's row
now carries the refund it owes in the same write that settles it; the refund is
applied once per refund id, and the reaper pays any owed refund a crash left behind.
A job also remembers the period its latest reservation came from, so a retry in a
later month is refunded against that month.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from app.billing import metering
from app.models.batch_job import BatchJob, JobProgress, JobStatus, JobType
from app.models.training_job import TrainingJob
from app.models.usage import UsageRecord
from app.services.batch_prediction import BatchPredictionService
from app.services.job_reaper import reap_stale_jobs
from app.utils.datetime import utcnow

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

USER = "refund_crash_user"


async def _units(metric: str, period: str) -> int:
    row = await UsageRecord.find_one(
        UsageRecord.user_id == USER, UsageRecord.metric == metric, UsageRecord.period_key == period
    )
    return row.units if row else 0


async def _reserve(metric: str, amount: int, period: str) -> None:
    await UsageRecord.get_motor_collection().update_one(
        {"user_id": USER, "metric": metric, "period_key": period},
        {"$inc": {"units": amount}},
        upsert=True,
    )


def _stale_batch(job_id: str, **fields) -> BatchJob:
    job = BatchJob(
        job_id=job_id, job_type=JobType.BATCH_PREDICTION, user_id=USER, config={"model_id": "m"},
        input_path=f"batch-jobs/{USER}/m/{job_id}/input.csv", status=JobStatus.RUNNING,
        progress=JobProgress(total_records=5), **fields,
    )
    job.last_heartbeat = utcnow() - timedelta(hours=2)
    return job


async def test_a_refund_id_is_applied_once(setup_database):
    # More reserved than refunded, so only the id can stop the second refund.
    await _reserve("predictions", 10, "2026-10")

    for _ in range(2):
        assert await metering.refund(USER, "predictions", 5, "2026-10", refund_id="r1") is True

    assert await _units("predictions", "2026-10") == 5


async def test_a_storage_failure_says_the_refund_was_not_paid(setup_database):
    with patch.object(UsageRecord, "get_motor_collection", side_effect=RuntimeError("down")):
        assert await metering.refund(USER, "predictions", 1, "2026-10", refund_id="r2") is False


async def test_a_batch_refund_lost_to_a_crash_is_paid_by_the_next_reaper_pass(setup_database):
    period = metering.period_key_for()
    await _reserve("predictions", 5, period)
    job = await _stale_batch("crash-batch-1").insert()

    with patch("app.billing.owed_refunds.metering.refund", side_effect=RuntimeError("worker died")):
        with pytest.raises(RuntimeError):
            await reap_stale_jobs(timeout_seconds=60)
    stored = await BatchJob.get(job.id)
    assert stored.status == JobStatus.FAILED
    assert len(stored.refunds_owed) == 1
    assert await _units("predictions", period) == 5

    await reap_stale_jobs(timeout_seconds=60)
    await reap_stale_jobs(timeout_seconds=60)

    assert await _units("predictions", period) == 0
    assert (await BatchJob.get(job.id)).refunds_owed == []


async def test_a_training_refund_lost_to_a_crash_is_paid_by_the_next_reaper_pass(setup_database):
    period = metering.period_key_for()
    await _reserve("training_runs", 1, period)
    job = TrainingJob(
        model_id="crash-train-1", user_id=USER, dataset_id="d", target_column="y", status=JobStatus.RUNNING
    )
    job.last_heartbeat = utcnow() - timedelta(hours=2)
    await job.insert()

    with patch("app.billing.owed_refunds.metering.refund", side_effect=RuntimeError("worker died")):
        with pytest.raises(RuntimeError):
            await reap_stale_jobs(timeout_seconds=60)
    assert await _units("training_runs", period) == 1

    await reap_stale_jobs(timeout_seconds=60)

    assert await _units("training_runs", period) == 0
    assert (await TrainingJob.get(job.id)).refunds_owed == []


async def test_a_retry_in_a_later_month_is_refunded_against_that_month(setup_database):
    await _reserve("predictions", 5, "2026-09")
    await _reserve("predictions", 5, "2026-10")
    job = _stale_batch("crash-batch-2", reserved_period="2026-10")
    job.created_at = datetime(2026, 9, 30, 23, 0, tzinfo=UTC)
    await job.insert()

    await reap_stale_jobs(timeout_seconds=60)

    assert await _units("predictions", "2026-10") == 0
    assert await _units("predictions", "2026-09") == 5


async def test_a_retry_records_the_period_it_reserved_against(setup_database):
    job = _stale_batch("retry-period-1", reserved_period="2026-09")
    job.status = JobStatus.FAILED
    await job.insert()

    with patch.object(BatchPredictionService, "_spawn_processing"):
        assert await BatchPredictionService().retry_job("retry-period-1", USER) is True

    assert (await BatchJob.get(job.id)).reserved_period == metering.period_key_for()


async def test_a_cancelled_runs_remainder_lost_to_a_crash_is_paid_by_the_reaper(setup_database):
    period = metering.period_key_for()
    await _reserve("predictions", 5, period)
    job = _stale_batch("crash-batch-3")
    job.status = JobStatus.CANCELLED
    job.last_heartbeat = utcnow()
    await job.insert()

    with patch("app.billing.owed_refunds.metering.refund", side_effect=RuntimeError("worker died")):
        with pytest.raises(RuntimeError):
            await BatchPredictionService()._refund_remainder(job, 2)
    assert await _units("predictions", period) == 5

    await reap_stale_jobs(timeout_seconds=60)

    assert await _units("predictions", period) == 2


async def test_a_retry_settled_again_before_the_first_refund_is_paid_pays_both(setup_database):
    """A settle crashes, the tenant retries, and the retry is reaped before any pass has
    paid the first refund: the second settle must not replace the first."""
    period = metering.period_key_for()
    await _reserve("predictions", 10, period)
    job = await _stale_batch("crash-batch-4").insert()

    with patch("app.billing.owed_refunds.metering.refund", side_effect=RuntimeError("worker died")):
        with pytest.raises(RuntimeError):
            await reap_stale_jobs(timeout_seconds=60)
    with patch.object(BatchPredictionService, "_spawn_processing"):
        assert await BatchPredictionService().retry_job("crash-batch-4", USER) is True
    await BatchJob.get_motor_collection().update_one(
        {"job_id": "crash-batch-4"}, {"$set": {"last_heartbeat": utcnow() - timedelta(hours=2)}}
    )

    await reap_stale_jobs(timeout_seconds=60)

    assert await _units("predictions", period) == 0
    assert (await BatchJob.get(job.id)).refunds_owed == []
