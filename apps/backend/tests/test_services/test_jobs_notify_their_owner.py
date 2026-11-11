"""#494 AC2, AC4: every way a job ends well or badly mails its owner, and none of them
can be changed by the mail.

Each test drives the real job code against real Mongo and reads the message off the
provider seam (`email_service.send`). Three places end a job: the training task, the batch
run, and the stale-job reaper.
"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from bson import ObjectId

from app.api.routes import model_training
from app.api.routes.model_training import TrainModelRequest, train_model_task
from app.models.batch_job import BatchJob, JobProgress, JobStatus, JobType
from app.models.notification_preference import NotificationPreference
from app.models.training_job import TrainingJob
from app.services import email_service, job_notifications
from app.services.batch_prediction import BatchPredictionService
from app.services.job_reaper import reap_stale_jobs
from app.services.model_training.automl_engine import TrainingCancelledError
from app.utils.datetime import utcnow

ADDRESS = "analyst@customer.example"
CSV = b"a,target\n1,0\n2,1\n"
REQUEST = TrainModelRequest(dataset_id="dataset_123", target_column="target")


@pytest.fixture
def outbox(monkeypatch) -> list[dict[str, str]]:
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
    monkeypatch.setenv("EMAIL_FROM", "SheetPredict <jobs@mail.example>")
    sent: list[dict[str, str]] = []

    async def deliver(to: str, subject: str, text: str, *, idempotency_key: str) -> bool:
        sent.append({"to": to, "subject": subject, "text": text, "key": idempotency_key})
        return True

    monkeypatch.setattr(email_service, "send", deliver)
    return sent


@pytest.fixture
def broken_provider(monkeypatch) -> None:
    """A configured sender that raises on every message."""
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
    monkeypatch.setenv("EMAIL_FROM", "SheetPredict <jobs@mail.example>")
    monkeypatch.setattr(email_service, "send", AsyncMock(side_effect=RuntimeError("provider down")))


@pytest_asyncio.fixture
async def owner(setup_database):
    users = NotificationPreference.get_motor_collection().database["users"]
    user_id = ObjectId()
    await users.insert_one({"_id": user_id, "email": ADDRESS})
    yield str(user_id)
    await users.delete_one({"_id": user_id})


# --- Training -------------------------------------------------------------------


def _dataset(owner: str) -> MagicMock:
    return MagicMock(
        id="dataset_123", user_id=owner, file_type="csv", filename="churn.csv",
        s3_url=f"s3://test-bucket/datasets/{owner}/churn.csv",
    )


async def _training_job(model_id: str, owner: str) -> None:
    await TrainingJob(
        model_id=model_id, user_id=owner, dataset_id="dataset_123", target_column="target"
    ).insert()


async def _train(model_id: str, owner: str, engine_run, request: TrainModelRequest = REQUEST) -> None:
    with (
        patch("app.services.s3_service.S3Service.download_file_bytes", new_callable=AsyncMock, return_value=CSV),
        patch("app.api.routes.model_training.AutoMLEngine") as engine_cls,
    ):
        engine_cls.return_value.run = engine_run
        await train_model_task(_dataset(owner), request, owner, model_id, wall_clock_seconds=30)


async def _engine_fails(*_args, **_kwargs):
    raise ValueError("This solver needs samples of at least 2 classes but the data has 1")


async def _engine_is_cancelled(*_args, **_kwargs):
    raise TrainingCancelledError("Training cancelled before RandomForest")


async def _train_to_completion(model_id: str, owner: str) -> None:
    """The task with training, storage and the completion write stubbed: what is left is
    the order of its steps, which is what decides whether a mail goes out."""
    trained = SimpleNamespace(model_id=model_id, name="Churn model")
    with (
        patch.object(model_training, "_run_training", AsyncMock(return_value=MagicMock())),
        patch.object(model_training, "_store_trained_model", AsyncMock(return_value=trained)),
        patch.object(model_training, "_record_completion", AsyncMock()),
        patch.object(model_training, "_record_what_follows", AsyncMock()),
    ):
        await train_model_task(_dataset(owner), REQUEST, owner, model_id, wall_clock_seconds=30)


async def test_a_trained_model_mails_its_owner(owner, outbox):
    await _training_job("model_done", owner)

    await _train_to_completion("model_done", owner)

    (message,) = outbox
    assert message["to"] == ADDRESS
    assert message["subject"] == 'Training "Churn model" finished'
    assert message["key"] == "training-model_done-completed"


async def test_a_failed_training_mails_the_stored_reason(owner, outbox):
    await _training_job("model_failed", owner)

    await _train("model_failed", owner, _engine_fails)

    job = await TrainingJob.find_one(TrainingJob.model_id == "model_failed")
    assert job.status == JobStatus.FAILED
    (message,) = outbox
    assert message["subject"] == 'Training "churn.csv" failed'
    assert f"Reason: {job.error}" in message["text"]
    assert "solver needs samples" not in message["text"], "the raw exception stays server-side"
    assert message["key"] == "training-model_failed-failed"
    assert "Job id: model_failed" in message["text"]


async def test_a_failed_training_is_named_as_the_user_named_it(owner, outbox):
    await _training_job("model_named", owner)
    named = TrainModelRequest(dataset_id="dataset_123", target_column="target", name="Q3 churn")

    await _train("model_named", owner, _engine_fails, named)

    assert outbox[0]["subject"] == 'Training "Q3 churn" failed'


async def test_a_cancelled_training_mails_nobody(owner, outbox):
    await _training_job("model_cancelled", owner)

    await _train("model_cancelled", owner, _engine_is_cancelled)

    assert outbox == []


async def test_a_failure_that_was_not_recorded_mails_nobody(owner, outbox):
    # The row still reads RUNNING, so the reaper will fail it and send the one mail.
    await _training_job("model_unrecorded", owner)

    with patch.object(TrainingJob, "mark_failed", side_effect=RuntimeError("database is down")):
        await _train("model_unrecorded", owner, _engine_fails)

    assert outbox == []


async def test_a_provider_that_raises_changes_nothing_about_a_training_job(owner, broken_provider):
    await _training_job("model_mail_down", owner)

    await _train("model_mail_down", owner, _engine_fails)  # no raise
    await _train_to_completion("model_mail_done", owner)  # no raise

    job = await TrainingJob.find_one(TrainingJob.model_id == "model_mail_down")
    assert job.status == JobStatus.FAILED
    assert "only one distinct value" in job.error


# --- Batch prediction -----------------------------------------------------------


async def _batch_job(job_id: str, owner: str, status: JobStatus, **fields) -> BatchJob:
    return await BatchJob(
        job_id=job_id, job_type=JobType.BATCH_PREDICTION, user_id=owner,
        config={"model_id": "model_123"}, input_path=f"batch-jobs/{owner}/model_123/{job_id}/input.csv",
        status=status, progress=JobProgress(total_records=1200), **fields,
    ).insert()


ENDED = datetime(2026, 11, 11, 9, 30, tzinfo=UTC)


async def test_a_completed_batch_job_mails_its_owner(owner, outbox):
    await _batch_job("batch_done", owner, JobStatus.COMPLETED, completed_at=ENDED)

    await job_notifications.batch_job_finished("batch_done")

    (message,) = outbox
    assert message["to"] == ADDRESS
    assert message["subject"] == "Your batch prediction of 1,200 records finished"
    assert message["key"] == "batch-batch_done-completed-2026-11-11 09:30:00"


async def test_a_failed_batch_job_mails_the_stored_reason(owner, outbox):
    await _batch_job(
        "batch_failed", owner, JobStatus.FAILED, error_message="The input file has no rows.", completed_at=ENDED
    )

    await job_notifications.batch_job_finished("batch_failed")

    (message,) = outbox
    assert message["subject"] == "Your batch prediction of 1,200 records failed"
    assert "Reason: The input file has no rows." in message["text"]
    assert "Job id: batch_failed" in message["text"]
    assert message["key"] == "batch-batch_failed-failed-2026-11-11 09:30:00"


async def test_one_ending_has_one_key_and_a_later_ending_of_the_same_job_another(owner, outbox):
    # A job that fails, is retried, and is then reaped keeps its retry count, so the
    # count cannot tell the two failures apart; when each was stored can.
    job = await _batch_job("batch_twice", owner, JobStatus.FAILED, error_message="first", completed_at=ENDED)

    await job_notifications.batch_job_finished("batch_twice")
    await job_notifications.batch_job_finished("batch_twice")
    await job.set({BatchJob.completed_at: ENDED + timedelta(minutes=5), BatchJob.error_message: "second"})
    await job_notifications.batch_job_finished("batch_twice")

    first, again, later = (message["key"] for message in outbox)
    assert first == again
    assert later != first


@pytest.mark.parametrize("status", [JobStatus.CANCELLED, JobStatus.RUNNING, JobStatus.PENDING])
async def test_a_batch_job_that_did_not_finish_or_fail_mails_nobody(owner, outbox, status):
    await _batch_job("batch_other", owner, status)

    await job_notifications.batch_job_finished("batch_other")

    assert outbox == []


async def test_an_erased_batch_job_mails_nobody(owner, outbox):
    await job_notifications.batch_job_finished("batch_gone")

    assert outbox == []


async def _run_failing_batch(job: BatchJob) -> None:
    """The real run, failing at its first step after the claim (the model lookup)."""
    svc = BatchPredictionService()
    svc.s3_service = MagicMock()
    with patch(
        "app.services.batch_prediction.MLModel.find_one",
        AsyncMock(side_effect=ValueError("s3://secret-bucket/x.csv could not be read")),
    ):
        await svc._process_batch_job(job)


async def test_the_batch_run_mails_what_it_stored(owner, outbox):
    job = await _batch_job("batch_run", owner, JobStatus.PENDING)

    await _run_failing_batch(job)

    stored = await BatchJob.find_one(BatchJob.job_id == "batch_run")
    assert stored.status == JobStatus.FAILED
    (message,) = outbox
    assert f"Reason: {stored.error_message}" in message["text"]
    assert "secret-bucket" not in message["text"]


async def test_a_batch_run_that_lost_to_a_cancel_mails_nobody(owner, outbox):
    job = await _batch_job("batch_raced", owner, JobStatus.PENDING)
    svc = BatchPredictionService()
    svc.s3_service = MagicMock()

    async def cancelled_meanwhile(*_args, **_kwargs):
        await BatchJob.find_one(BatchJob.job_id == "batch_raced").update(
            {"$set": {"status": JobStatus.CANCELLED.value}}
        )
        raise ValueError("the run fails after the cancel landed")

    with patch("app.services.batch_prediction.MLModel.find_one", cancelled_meanwhile):
        await svc._process_batch_job(job)

    assert (await BatchJob.find_one(BatchJob.job_id == "batch_raced")).status == JobStatus.CANCELLED
    assert outbox == []


async def test_a_deadline_reached_during_a_slow_webhook_does_not_cost_the_owner_the_mail(
    owner, outbox, monkeypatch
):
    # The run stored its ending in time; only its webhook outlived the wall clock.
    import asyncio

    from app.services import batch_prediction

    monkeypatch.setattr(batch_prediction, "BATCH_JOB_WALL_CLOCK_SECONDS", 0.5)
    job = await _batch_job("batch_slow_hook", owner, JobStatus.PENDING)
    svc = BatchPredictionService()
    svc.s3_service = MagicMock()

    async def slow_webhook(_job):
        await asyncio.sleep(30)

    svc._fire_webhook = slow_webhook
    with patch(
        "app.services.batch_prediction.MLModel.find_one",
        AsyncMock(side_effect=ValueError("the model could not be loaded")),
    ):
        await asyncio.wait_for(svc._process_batch_job(job), timeout=10)

    stored = await BatchJob.find_one(BatchJob.job_id == "batch_slow_hook")
    (message,) = outbox
    assert f"Reason: {stored.error_message}" in message["text"]
    assert "limit" not in message["text"], "the run's own failure, not the wall clock's"


async def test_a_provider_that_raises_changes_nothing_about_a_batch_job(owner, broken_provider):
    job = await _batch_job("batch_mail_down", owner, JobStatus.PENDING)

    await _run_failing_batch(job)  # no raise

    stored = await BatchJob.find_one(BatchJob.job_id == "batch_mail_down")
    assert stored.status == JobStatus.FAILED
    assert stored.error_message


async def test_a_batch_run_stopped_at_the_wall_clock_mails_that_reason_once(owner, outbox, monkeypatch):
    # The only ending where the mail goes out from a cancelled run's `finally`.
    import asyncio

    from app.services import batch_prediction

    monkeypatch.setattr(batch_prediction, "BATCH_JOB_WALL_CLOCK_SECONDS", 0.2)
    job = await _batch_job("batch_hung", owner, JobStatus.PENDING)
    svc = BatchPredictionService()
    svc.s3_service = MagicMock()

    async def never_answers(*_args, **_kwargs):
        await asyncio.sleep(30)

    with patch("app.services.batch_prediction.MLModel.find_one", never_answers):
        await asyncio.wait_for(svc._process_batch_job(job), timeout=10)

    stored = await BatchJob.find_one(BatchJob.job_id == "batch_hung")
    assert stored.status == JobStatus.FAILED
    (message,) = outbox
    assert message["subject"] == "Your batch prediction of 1,200 records failed"
    assert f"Reason: {stored.error_message}" in message["text"]
    assert "0.2-second limit" in message["text"]


# --- The stale-job reaper -------------------------------------------------------


async def test_a_reaped_training_job_mails_its_owner(owner, outbox):
    job = TrainingJob(
        model_id="model_reaped", user_id=owner, dataset_id="d", target_column="y",
        status=JobStatus.RUNNING,
    )
    job.last_heartbeat = utcnow() - timedelta(hours=2)
    await job.insert()

    await reap_stale_jobs(timeout_seconds=60)

    (message,) = outbox
    assert message["to"] == ADDRESS
    assert message["subject"] == "Your training run failed"
    assert "restarted or crashed" in message["text"]
    assert "Job id: model_reaped" in message["text"]
    # The key the task itself would use, so a task that outlived its reaping mails nothing more.
    assert message["key"] == "training-model_reaped-failed"


async def test_a_reaped_batch_job_mails_its_owner(owner, outbox):
    job = await _batch_job("batch_reaped", owner, JobStatus.RUNNING)
    await job.set({BatchJob.last_heartbeat: utcnow() - timedelta(hours=2)})

    await reap_stale_jobs(timeout_seconds=60)

    (message,) = outbox
    assert message["subject"] == "Your batch prediction of 1,200 records failed"
    assert "restarted or crashed" in message["text"]


async def test_a_provider_that_raises_does_not_stop_the_reaper(owner, broken_provider):
    for model_id in ("model_reaped_1", "model_reaped_2"):
        job = TrainingJob(
            model_id=model_id, user_id=owner, dataset_id="d", target_column="y",
            status=JobStatus.RUNNING,
        )
        job.last_heartbeat = utcnow() - timedelta(hours=2)
        await job.insert()

    summary = await reap_stale_jobs(timeout_seconds=60)

    assert summary.training == 2


async def test_a_refund_that_cannot_be_paid_does_not_cost_the_owner_the_mail(owner, outbox, monkeypatch):
    # The claim already wrote FAILED, so no later pass reaps this job again.
    from app.billing import owed_refunds

    job = TrainingJob(
        model_id="model_refund_down", user_id=owner, dataset_id="d", target_column="y",
        status=JobStatus.RUNNING,
    )
    job.last_heartbeat = utcnow() - timedelta(hours=2)
    await job.insert()
    monkeypatch.setattr(owed_refunds, "settle", AsyncMock(side_effect=ConnectionError("mongo is away")))

    with pytest.raises(ConnectionError):
        await reap_stale_jobs(timeout_seconds=60)

    assert (await TrainingJob.get(job.id)).status == JobStatus.FAILED
    assert [message["key"] for message in outbox] == ["training-model_refund_down-failed"]
