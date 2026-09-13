"""Stale-job reaper: reap orphaned jobs, refund their quota, spare live ones (#484)."""

import asyncio
from datetime import timedelta

import pytest

from app.billing import metering
from app.models.batch_job import BatchJob, JobProgress, JobStatus, JobType
from app.models.training_job import TrainingJob
from app.services.job_reaper import reap_stale_jobs
from app.utils.datetime import as_utc, utcnow
from app.utils.heartbeat import heartbeat_pump

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

USER = "reaper_user"


async def test_reaps_a_stale_training_job_and_refunds_its_unit(setup_database):
    # Simulate the reservation the quota dependency made at creation.
    await metering.record(USER, "training_runs", 1)
    before = await metering.usage_for(USER, "training_runs")
    assert before >= 1

    job = TrainingJob(
        model_id="reap-train-1", user_id=USER, dataset_id="d", target_column="y",
        status=JobStatus.RUNNING,
    )
    job.last_heartbeat = utcnow() - timedelta(hours=2)  # heartbeat long dead
    await job.insert()

    summary = await reap_stale_jobs(timeout_seconds=60)

    assert summary.training >= 1
    reaped = await TrainingJob.get(job.id)
    assert reaped.status == JobStatus.FAILED
    assert "recovery" in (reaped.error or "").lower()
    # AC2: the reserved unit is returned.
    assert await metering.usage_for(USER, "training_runs") == before - 1


async def test_does_not_reap_a_job_with_a_fresh_heartbeat(setup_database):
    """A live job (recent heartbeat) is never reaped — critical under 2 workers."""
    job = TrainingJob(
        model_id="reap-train-live", user_id=USER, dataset_id="d", target_column="y",
        status=JobStatus.RUNNING,
    )
    job.last_heartbeat = utcnow()  # beating right now
    await job.insert()

    await reap_stale_jobs(timeout_seconds=60)

    still = await TrainingJob.get(job.id)
    assert still.status == JobStatus.RUNNING


async def test_reaps_a_stale_batch_job_and_refunds_its_records(setup_database):
    await metering.record(USER, "predictions", 5)
    before = await metering.usage_for(USER, "predictions")

    job = BatchJob(
        job_id="reap-batch-1", job_type=JobType.BATCH_PREDICTION, user_id=USER,
        config={"model_id": "m1"}, input_path="batch-jobs/u/m1/ts/in.csv",
        status=JobStatus.RUNNING, progress=JobProgress(total_records=5),
    )
    job.last_heartbeat = utcnow() - timedelta(hours=2)
    await job.insert()

    summary = await reap_stale_jobs(timeout_seconds=60)

    assert summary.batch >= 1
    reaped = await BatchJob.get(job.id)
    assert reaped.status == JobStatus.FAILED
    # AC2: the reserved predictions (= total_records) are returned.
    assert await metering.usage_for(USER, "predictions") == before - 5


async def test_sweeps_a_pre484_job_missing_the_heartbeat_field(setup_database):
    """AC4: an existing stuck job written before #484 has no last_heartbeat at all.
    A missing field never matches a $lt, so the reaper falls back to created_at."""
    coll = TrainingJob.get_motor_collection()
    await coll.insert_one(
        {
            "model_id": "reap-pre484",
            "user_id": USER,
            "dataset_id": "d",
            "target_column": "y",
            "status": JobStatus.RUNNING.value,
            "created_at": utcnow() - timedelta(hours=3),
            # deliberately NO last_heartbeat, as a pre-#484 document
        }
    )
    summary = await reap_stale_jobs(timeout_seconds=60)
    assert summary.training >= 1
    doc = await coll.find_one({"model_id": "reap-pre484"})
    assert doc["status"] == JobStatus.FAILED.value


async def test_a_persisted_progress_write_keeps_a_job_alive(setup_database):
    """Regression (codex P1): a live training persists last_heartbeat via its
    PARTIAL progress write; if that partial $set omits the field, the DB heartbeat
    stays stale and the reaper kills a live run. This exercises that contract."""
    job = TrainingJob(
        model_id="reap-hb", user_id=USER, dataset_id="d", target_column="y",
        status=JobStatus.RUNNING,
    )
    job.last_heartbeat = utcnow() - timedelta(hours=2)  # would be reaped as-is
    await job.insert()

    # A progress update like on_progress: bump the heartbeat and persist it with
    # the same partial-$set shape the route uses.
    job.update_progress(completed_algorithms=1, total_algorithms=3)
    await job.set(
        {
            TrainingJob.progress: job.progress,
            TrainingJob.updated_at: job.updated_at,
            TrainingJob.last_heartbeat: job.last_heartbeat,
        }
    )

    await reap_stale_jobs(timeout_seconds=60)
    assert (await TrainingJob.get(job.id)).status == JobStatus.RUNNING


async def test_reaping_is_idempotent(setup_database):
    """A second pass finds nothing (the job left the in-flight set) — no double refund."""
    await metering.record(USER, "training_runs", 1)
    before = await metering.usage_for(USER, "training_runs")
    job = TrainingJob(
        model_id="reap-train-idem", user_id=USER, dataset_id="d", target_column="y",
        status=JobStatus.RUNNING,
    )
    job.last_heartbeat = utcnow() - timedelta(hours=2)
    await job.insert()

    await reap_stale_jobs(timeout_seconds=60)
    second = await reap_stale_jobs(timeout_seconds=60)

    assert second.training == 0
    # Refunded exactly once, not twice.
    assert await metering.usage_for(USER, "training_runs") == before - 1


async def test_heartbeat_pump_keeps_the_db_heartbeat_fresh(setup_database):
    """Critical (codex #1): a long candidate can outlast the timeout between
    progress events, so a background pump must keep last_heartbeat advancing."""
    job = TrainingJob(
        model_id="pump-1", user_id=USER, dataset_id="d", target_column="y",
        status=JobStatus.RUNNING,
    )
    job.last_heartbeat = utcnow() - timedelta(hours=1)  # would be reaped as-is
    await job.insert()

    async with heartbeat_pump(job, interval=0.05):
        await asyncio.sleep(0.2)  # several ticks

    refreshed = await TrainingJob.get(job.id)
    age = (utcnow() - as_utc(refreshed.last_heartbeat)).total_seconds()
    assert age < 30, "the pump should have refreshed the persisted heartbeat"


async def test_retried_batch_job_refreshes_its_heartbeat(setup_database, monkeypatch):
    """Critical (codex #2): a retry must refresh last_heartbeat, or the stale value
    carried from the original failed run makes the retry immediately reapable."""
    from app.services.batch_prediction import BatchPredictionService

    svc = BatchPredictionService()
    monkeypatch.setattr(svc, "_spawn_processing", lambda job: None)

    job = BatchJob(
        job_id="retry-hb", job_type=JobType.BATCH_PREDICTION, user_id=USER,
        config={"model_id": "m1"}, input_path="batch-jobs/u/m1/ts/in.csv",
        status=JobStatus.FAILED, retry_count=0, max_retries=3,
        progress=JobProgress(total_records=1),
    )
    job.last_heartbeat = utcnow() - timedelta(hours=2)  # stale from the failed run
    await job.insert()

    assert await svc.retry_job("retry-hb", USER) is True

    # Reheartbeated -> the reaper does not kill the retry before it starts.
    await reap_stale_jobs(timeout_seconds=60)
    assert (await BatchJob.get(job.id)).status == JobStatus.PENDING
