"""Stale-job reaper (#484).

Training and batch jobs run in-process and are marked RUNNING while they work.
A restart, deploy or crash therefore leaves the document RUNNING forever —
nothing reconciles it, the user sees a job that never finishes, and the quota it
reserved is never released. This reaps jobs whose liveness heartbeat has gone
stale, marks them FAILED with a clear reason, and returns their reserved quota.

Two things make this safe under the 2 gunicorn workers (see the Dockerfile):

  * **Staleness is heartbeat-based, never "reap all on startup".** Each in-flight
    job bumps ``last_heartbeat`` on every progress write; only jobs whose
    heartbeat is older than the timeout are reaped, so a starting/looping worker
    never touches another worker's *live* job (its heartbeat is recent).
  * **Each reap is an atomic claim.** ``find_one_and_update`` transitions exactly
    one matching doc out of the in-flight set and returns its pre-image, so two
    workers reaping concurrently claim disjoint jobs and each reserved unit is
    refunded exactly once.

Refunds go against the period the unit was RESERVED in (``created_at``), per the
``QuotaRefundMiddleware`` contract in CLAUDE.md — refunding against the current
period would credit a month that was never charged.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.billing import metering
from app.billing.metering import period_key_for
from app.billing.plans import _env_positive_int
from app.models.batch_job import BatchJob, JobStatus, JobType
from app.models.training_job import TrainingJob
from app.utils.datetime import as_utc, utcnow

logger = logging.getLogger(__name__)

_IN_FLIGHT = [JobStatus.PENDING.value, JobStatus.RUNNING.value]
_REASON = (
    "Recovered by stale-job recovery: the worker running this job restarted or "
    "crashed before it finished (#484)."
)

#: A job whose heartbeat is older than this is considered dead. Generous by
#: default: it must exceed the longest gap between a live job's heartbeats (a slow
#: single training candidate, a slow batch chunk) so a live job is never reaped.
STALE_JOB_TIMEOUT_SECONDS = _env_positive_int("STALE_JOB_TIMEOUT_SECONDS", 1800)
#: How often the background reaper runs in each worker.
JOB_REAPER_INTERVAL_SECONDS = _env_positive_int("JOB_REAPER_INTERVAL_SECONDS", 300)


@dataclass
class ReapSummary:
    training: int = 0
    batch: int = 0

    @property
    def total(self) -> int:
        return self.training + self.batch


async def reap_stale_jobs(timeout_seconds: float = STALE_JOB_TIMEOUT_SECONDS) -> ReapSummary:
    """Reap in-flight jobs whose heartbeat is older than ``timeout_seconds``."""
    cutoff = utcnow() - timedelta(seconds=timeout_seconds)
    summary = ReapSummary(
        training=await _reap_training(cutoff),
        batch=await _reap_batch(cutoff),
    )
    if summary.total:
        logger.warning(
            "stale-job reaper: recovered %d job(s) (%d training, %d batch)",
            summary.total,
            summary.training,
            summary.batch,
        )
    return summary


def _stale_filter(cutoff: datetime, extra: dict | None = None) -> dict:
    """Match in-flight jobs that are stale by heartbeat, OR — for documents
    written before #484 that have no ``last_heartbeat`` at all — stale by
    ``created_at``, so the one-time sweep of existing stuck jobs (AC4) reaches
    them. A missing field never matches a ``$lt``, so the fallback is explicit.
    """
    query: dict = {
        "status": {"$in": _IN_FLIGHT},
        "$or": [
            {"last_heartbeat": {"$lt": cutoff}},
            {"last_heartbeat": {"$exists": False}, "created_at": {"$lt": cutoff}},
        ],
    }
    if extra:
        query.update(extra)
    return query


async def _reap_training(cutoff: datetime) -> int:
    coll = TrainingJob.get_motor_collection()
    reaped = 0
    while True:
        doc = await coll.find_one_and_update(
            _stale_filter(cutoff),
            {
                "$set": {
                    "status": JobStatus.FAILED.value,
                    "error": _REASON,
                    "completed_at": utcnow(),
                    "updated_at": utcnow(),
                }
            },
        )
        if doc is None:
            return reaped
        # Claimed atomically -> refund the one training_runs unit reserved at
        # creation, against the period it was taken from.
        await metering.refund(
            doc["user_id"], "training_runs", 1, period_key_for(as_utc(doc["created_at"]))
        )
        reaped += 1


async def _reap_batch(cutoff: datetime) -> int:
    coll = BatchJob.get_motor_collection()
    reaped = 0
    while True:
        doc = await coll.find_one_and_update(
            _stale_filter(cutoff, {"job_type": JobType.BATCH_PREDICTION.value}),
            {
                "$set": {
                    "status": JobStatus.FAILED.value,
                    "error_message": _REASON,
                    "completed_at": utcnow(),
                }
            },
        )
        if doc is None:
            return reaped
        # A batch reserves `predictions` = total_records at creation.
        reserved = int((doc.get("progress") or {}).get("total_records") or 0)
        if reserved > 0:
            await metering.refund(
                doc["user_id"], "predictions", reserved, period_key_for(as_utc(doc["created_at"]))
            )
        reaped += 1
