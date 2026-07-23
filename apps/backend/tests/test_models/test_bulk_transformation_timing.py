"""Datetime-hygiene regression tests for BulkTransformationJob timing (#284).

`BulkTransformationJob.duration_seconds`/`estimated_remaining_seconds` subtract
a persisted `started_at` from an aware `get_current_time()`. After a Mongo
round-trip `started_at` is naive, so without `as_utc` coercion these raise
`TypeError` — surfaced as a 500 on `GET .../bulk-jobs/{job_id}` status polls of
a RUNNING job (found by GLM review on PR #359).
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.models.bulk_transformation import (
    BulkJobStatus,
    BulkTransformationJob,
)

pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("beanie_models_initialized")]


def _job(**over) -> BulkTransformationJob:
    return BulkTransformationJob(
        job_id="bj1",
        user_id="u1",
        dataset_id="d1",
        transformation_type="fill_missing",
        **over,
    )


def _naive_utc(seconds_ago: int) -> datetime:
    # Naive UTC == the shape Mongo returns (tzinfo dropped off a UTC value).
    return datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=seconds_ago)


def test_duration_seconds_with_naive_start_does_not_raise():
    job = _job(status=BulkJobStatus.RUNNING, started_at=_naive_utc(5))
    assert job.duration_seconds >= 5.0


def test_duration_seconds_completed_span_naive():
    started = datetime(2026, 1, 1, 12, 0, 0)
    completed = datetime(2026, 1, 1, 12, 0, 30)
    job = _job(status=BulkJobStatus.COMPLETED, started_at=started, completed_at=completed)
    assert job.duration_seconds == 30.0


def test_estimated_remaining_with_naive_start_does_not_raise():
    job = _job(status=BulkJobStatus.RUNNING, started_at=_naive_utc(10))
    job.progress.total_columns = 10
    job.progress.processed_columns = 5
    remaining = job.estimated_remaining_seconds
    assert remaining is not None
    assert remaining >= 0
