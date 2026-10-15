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

Refunds go against the period the unit was RESERVED in (``created_at``, or a batch
retry's own period), per the ``QuotaRefundMiddleware`` contract in CLAUDE.md:
refunding against the current period would credit a month that was never charged.
The claim records the refund it owes in the same write, so a worker that dies before
paying it leaves it for the next pass (``app/billing/owed_refunds.py``, #1032).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from motor.motor_asyncio import AsyncIOMotorCollection

from app.billing import owed_refunds
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
    await owed_refunds.settle_pending(coll)
    return await _reap(coll, _stale_filter(cutoff), _training_failure)


def _training_failure(doc: dict) -> tuple[dict, dict]:
    """FAILED, owing the one `training_runs` unit reserved at creation."""
    refund = owed_refunds.owed(
        doc["user_id"], "training_runs", 1, period_key_for(as_utc(doc["created_at"]))
    )
    return {
        "status": JobStatus.FAILED.value,
        "error": _REASON,
        "completed_at": utcnow(),
        "updated_at": utcnow(),
    }, refund


async def _reap_batch(cutoff: datetime) -> int:
    coll = BatchJob.get_motor_collection()
    await owed_refunds.settle_pending(coll)
    return await _reap(coll, _stale_filter(cutoff, {"job_type": JobType.BATCH_PREDICTION.value}), _batch_failure)


def _batch_failure(doc: dict) -> tuple[dict, dict]:
    """FAILED, owing the whole reservation (`predictions` = total_records), against
    the period the latest reservation was taken from."""
    reserved = int((doc.get("progress") or {}).get("total_records") or 0)
    refund = owed_refunds.owed(
        doc["user_id"], "predictions", reserved, reservation_period(doc)
    )
    return {
        "status": JobStatus.FAILED.value,
        "error_message": _REASON,
        "completed_at": utcnow(),
        # This path refunds the whole reservation, so mark it (#653): a reaped job
        # that was only queued is still picked up when its slot frees, fails its
        # claim, and would otherwise be refunded a second time by the batch service.
        "remainder_refunded": True,
    }, refund


def reservation_period(doc: dict) -> str:
    """The period a batch job's latest reservation was taken from (#1032): a retry
    records its own, and a row written before that falls back to creation's."""
    return doc.get("reserved_period") or period_key_for(as_utc(doc["created_at"]))


async def _reap(
    coll: AsyncIOMotorCollection, stale: dict, failure: Callable[[dict], tuple[dict, dict]]
) -> int:
    """Claim each stale job with one conditional write that also records the refund
    it owes, then pay that refund. Another worker's claim between the read and the
    write makes the write match nothing, and this one moves on."""
    reaped = 0
    while (doc := await coll.find_one(stale)) is not None:
        fields, refund = failure(doc)
        claim = {"$set": fields, "$push": {"refunds_owed": refund}}
        if await coll.find_one_and_update({**stale, "_id": doc["_id"]}, claim):
            await owed_refunds.settle(coll, {"_id": doc["_id"]}, refund)
            reaped += 1
    return reaped
