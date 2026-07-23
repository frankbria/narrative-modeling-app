"""Datetime-hygiene regression tests for BatchJob timing (issue #284).

MongoDB/Beanie drops tzinfo on read-back, so a persisted ``started_at`` returns
*naive*. The timing properties compute ``aware_now - started_at``; without
coercion that raises ``TypeError``. These construct jobs with naive timestamps
(the read-back shape) and assert the arithmetic works.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.models.batch_job import BatchJob, JobStatus, JobType

pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("beanie_models_initialized")]


def _job(**over) -> BatchJob:
    return BatchJob(
        job_id="j1", job_type=JobType.BATCH_PREDICTION, user_id="u1", config={}, **over
    )


def test_duration_seconds_with_naive_timestamps_does_not_raise():
    # Naive == the shape MongoDB returns.
    started = datetime(2026, 1, 1, 12, 0, 0)
    completed = datetime(2026, 1, 1, 12, 0, 30)
    job = _job(started_at=started, completed_at=completed)
    assert job.duration_seconds == 30.0


def test_duration_seconds_running_uses_now_against_naive_start():
    # Naive UTC — the exact shape Mongo returns (tzinfo dropped off a UTC value),
    # timezone-independent so it can't skew on a non-UTC CI box.
    started = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=5)
    job = _job(status=JobStatus.RUNNING, started_at=started)  # no completed_at
    # aware now - naive start; must not raise and must be positive.
    assert job.duration_seconds >= 5.0


def test_estimated_completion_with_naive_start_does_not_raise():
    started = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=10)
    job = _job(status=JobStatus.RUNNING, started_at=started)
    job.progress.total_records = 100
    job.progress.processed_records = 50
    eta = job.estimated_completion
    assert eta is not None
    assert eta.tzinfo is not None  # returned value is aware
