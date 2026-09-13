"""Training job admission + parallelism bounds (#498).

On a shared VPS, unbounded concurrent trainings each using every core saturate
the box and starve co-tenants (and the other apps sharing it). Two independent
limits, mirroring the batch mechanism (#515):

  * a PER-PROCESS ceiling on trainings actually executing at once (a semaphore),
    so excess jobs queue rather than all running. Per running loop, because the
    test suite creates a fresh loop per test and a semaphore is bound to one.
  * a PER-TENANT cap on PENDING/RUNNING jobs, enforced at admission, so one
    tenant cannot fill the queue either.

Plus a hard bound on estimator ``n_jobs`` so a single job cannot claim the whole
machine. ``_env_positive_int`` (not ``int(getenv)``) so a 0/negative override
cannot silently disable a control — the same guard plans.py uses.
"""

from __future__ import annotations

import asyncio
import os
import weakref

from app.billing.plans import _env_positive_int
from app.models.batch_job import JobStatus
from app.models.training_job import TrainingJob

_CPU = os.cpu_count() or 1

#: Total trainings executing at once across all tenants, sized for the host.
MAX_CONCURRENT_TRAINING_JOBS = _env_positive_int("MAX_CONCURRENT_TRAINING_JOBS", 2)
#: Trainings one tenant may have PENDING/RUNNING at once.
MAX_CONCURRENT_TRAINING_JOBS_PER_USER = _env_positive_int(
    "MAX_CONCURRENT_TRAINING_JOBS_PER_USER", 2
)
#: Upper bound on estimator ``n_jobs`` — never more cores than the host has.
TRAINING_MAX_N_JOBS = min(_env_positive_int("TRAINING_MAX_N_JOBS", 2), _CPU)

# WeakKeyDictionary, not id(loop): a closed test loop is collected and its entry
# with it, so the cache never grows and a reused id() cannot alias a dead loop.
_semaphores: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore] = (
    weakref.WeakKeyDictionary()
)


def training_semaphore() -> asyncio.Semaphore:
    """The per-process training-execution semaphore for the CURRENT event loop."""
    loop = asyncio.get_running_loop()
    sem = _semaphores.get(loop)
    if sem is None:
        sem = asyncio.Semaphore(MAX_CONCURRENT_TRAINING_JOBS)
        _semaphores[loop] = sem
    return sem


def bounded_n_jobs(requested: int | None = None) -> int:
    """Clamp an estimator's ``n_jobs`` to ``TRAINING_MAX_N_JOBS`` (#498).

    ``None`` or ``-1`` (sklearn's "all cores") resolve to the configured max; a
    positive request is capped to it; ``0`` (invalid for sklearn) becomes 1.
    """
    if requested is None or requested < 0:
        return TRAINING_MAX_N_JOBS
    if requested == 0:
        return 1
    return min(requested, TRAINING_MAX_N_JOBS)


class TrainingConcurrencyLimitError(Exception):
    """A tenant is already at their concurrent-training cap (#498). The route
    maps this to 429; the refund middleware returns any reserved quota units."""

    def __init__(self, active: int, limit: int) -> None:
        self.active = active
        self.limit = limit
        super().__init__(
            f"You already have {active} training job(s) running or queued "
            f"(limit {limit}); wait for one to finish before starting another."
        )


async def enforce_training_per_user_cap(user_id: str) -> None:
    """Refuse when the caller already holds MAX_CONCURRENT_TRAINING_JOBS_PER_USER
    PENDING/RUNNING training jobs. Checked BEFORE the new job is inserted, so it
    does not count itself. Best-effort under a same-tenant burst — the
    per-process semaphore is the hard execution bound.
    """
    active = await TrainingJob.find(
        {
            "user_id": user_id,
            "status": {"$in": [JobStatus.PENDING.value, JobStatus.RUNNING.value]},
        }
    ).count()
    if active >= MAX_CONCURRENT_TRAINING_JOBS_PER_USER:
        raise TrainingConcurrencyLimitError(active, MAX_CONCURRENT_TRAINING_JOBS_PER_USER)
