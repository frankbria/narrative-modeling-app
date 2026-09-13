"""Training admission: per-tenant cap, global semaphore, n_jobs bound (#498)."""

import asyncio

import pytest

from app.services import training_admission as ta
from app.services.training_admission import (
    TRAINING_MAX_N_JOBS,
    TrainingConcurrencyLimitError,
    bounded_n_jobs,
    enforce_training_per_user_cap,
    training_semaphore,
)


def test_bounded_n_jobs_clamps_to_the_configured_max():
    # -1 (sklearn "all cores") and None resolve to the host cap, never all cores.
    assert bounded_n_jobs(-1) == TRAINING_MAX_N_JOBS
    assert bounded_n_jobs(None) == TRAINING_MAX_N_JOBS
    # A large request is capped; 0 (invalid for sklearn) becomes 1; a small
    # request within the cap is honoured.
    assert bounded_n_jobs(9999) == TRAINING_MAX_N_JOBS
    assert bounded_n_jobs(0) == 1
    assert bounded_n_jobs(1) == 1
    assert TRAINING_MAX_N_JOBS >= 1


@pytest.mark.asyncio
async def test_training_semaphore_bounds_global_concurrency():
    sem = training_semaphore()
    # Same instance for the same loop (the per-loop cache).
    assert training_semaphore() is sem
    # Hold every permit; a further acquire must block (times out).
    held = [await asyncio.wait_for(sem.acquire(), 0.5) for _ in range(ta.MAX_CONCURRENT_TRAINING_JOBS)]
    assert len(held) == ta.MAX_CONCURRENT_TRAINING_JOBS
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(sem.acquire(), 0.1)
    for _ in held:
        sem.release()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_per_user_cap_refuses_the_next_job(setup_database):
    """The N+1th concurrent job for a tenant is refused before it can start."""
    from app.models.batch_job import JobStatus
    from app.models.training_job import TrainingJob

    user = "training_cap_user"
    # Under the cap: no refusal.
    await enforce_training_per_user_cap(user)

    # Seed the tenant up to their cap with PENDING/RUNNING jobs.
    for i in range(ta.MAX_CONCURRENT_TRAINING_JOBS_PER_USER):
        status = JobStatus.PENDING if i % 2 == 0 else JobStatus.RUNNING
        await TrainingJob(
            model_id=f"cap-{i}", user_id=user, dataset_id="d", target_column="y", status=status
        ).insert()

    # The next one is refused (AC5) — a different tenant is unaffected.
    with pytest.raises(TrainingConcurrencyLimitError):
        await enforce_training_per_user_cap(user)
    await enforce_training_per_user_cap("someone_else")

    # A terminal job does not count against the cap.
    await TrainingJob.find(TrainingJob.user_id == user).delete()
    await TrainingJob(
        model_id="done", user_id=user, dataset_id="d", target_column="y",
        status=JobStatus.COMPLETED,
    ).insert()
    await enforce_training_per_user_cap(user)
