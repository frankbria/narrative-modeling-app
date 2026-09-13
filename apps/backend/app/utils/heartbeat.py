"""Keep a long-running job's ``last_heartbeat`` fresh while it works (#484).

The stale-job reaper decides a job is dead when its heartbeat stops advancing.
Progress-driven heartbeats are not enough on their own: a single training
candidate's tuning+fit (a tier's tuning budget alone can reach 1800s) or a large
batch chunk can run longer than the reaper's timeout with no progress event in
between, and the reaper would then reap a *live* job and refund a run that is
actually still going. A background pump bumps the heartbeat on a fixed interval —
far shorter than the timeout — regardless of what the CPU-bound work is doing, so
liveness is decoupled from progress cadence.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from typing import Any

from app.billing.plans import _env_positive_int
from app.utils.datetime import utcnow

logger = logging.getLogger(__name__)

#: How often the pump refreshes the heartbeat. Must be << STALE_JOB_TIMEOUT_SECONDS.
HEARTBEAT_INTERVAL_SECONDS = _env_positive_int("JOB_HEARTBEAT_INTERVAL_SECONDS", 60)


@contextlib.asynccontextmanager
async def heartbeat_pump(
    job: Any | None, *, interval: float = HEARTBEAT_INTERVAL_SECONDS
) -> AsyncIterator[None]:
    """Bump ``job.last_heartbeat`` every ``interval`` seconds for the duration.

    ``job`` may be ``None`` (nothing to keep alive) — the pump is then a no-op, so
    callers with an optionally-loaded job need no branch. A failed heartbeat write
    is logged and retried on the next tick, never raised: it must not take down
    the work it is guarding.
    """
    if job is None:
        yield
        return

    async def _beat() -> None:
        while True:
            await asyncio.sleep(interval)
            try:
                # Resolve the Beanie class-field for the partial $set inside the
                # guard: a non-Beanie stand-in (e.g. a test MagicMock) simply
                # no-ops here instead of failing the work being guarded.
                job.last_heartbeat = utcnow()
                await job.set({type(job).last_heartbeat: job.last_heartbeat})
            except Exception:  # noqa: BLE001 - a heartbeat write must never crash the job
                logger.debug("heartbeat write failed for %s", getattr(job, "id", "?"), exc_info=True)

    task = asyncio.create_task(_beat())
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task
