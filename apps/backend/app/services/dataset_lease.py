"""One holder at a time for a piece of work on a dataset, across workers (#853).

Two first transformations on one dataset at the same moment both missed the lookup for
its history and both created one, and each transformed the same starting file. An
in-process lock would not help: the container runs two workers. The lease is a document
whose `_id` is its name, so the insert itself decides who holds it.
"""

import asyncio
import contextlib
import logging
import time
import uuid
from collections.abc import AsyncIterator
from datetime import timedelta

from pymongo.errors import DuplicateKeyError

from app.models.dataset_lease import DatasetLease
from app.utils.datetime import utcnow

logger = logging.getLogger(__name__)

#: How long a lease lasts if its holder never releases it (a worker that died mid-run).
LEASE_SECONDS = 300
#: How long a second caller waits for the first to finish before giving up.
WAIT_SECONDS = 30.0
_POLL_SECONDS = 0.1


class LeaseBusy(Exception):
    """Someone else held the lease for the whole wait."""


@contextlib.asynccontextmanager
async def dataset_lease(name: str, *, wait_seconds: float | None = None) -> AsyncIterator[None]:
    """Hold the lease called `name` for the body, having waited for it if it was taken.

    Raises:
        LeaseBusy: it was still held when the wait (`WAIT_SECONDS` unless given) ran out.
    """
    holder = uuid.uuid4().hex
    await _acquire(name, holder, WAIT_SECONDS if wait_seconds is None else wait_seconds)
    try:
        yield
    finally:
        await _release(name, holder)


async def _acquire(name: str, holder: str, wait_seconds: float) -> None:
    deadline = time.monotonic() + wait_seconds
    while not await _take(name, holder):
        if time.monotonic() >= deadline:
            raise LeaseBusy(name)
        await asyncio.sleep(_POLL_SECONDS)


async def _take(name: str, holder: str) -> bool:
    now = utcnow()
    # A lease past its expiry belongs to a holder that died. The TTL index removes it
    # too, but only about once a minute.
    await DatasetLease.find({"_id": name, "expires_at": {"$lt": now}}).delete()
    try:
        await DatasetLease(
            id=name, holder=holder, expires_at=now + timedelta(seconds=LEASE_SECONDS)
        ).insert()
    except DuplicateKeyError:
        return False
    return True


async def _release(name: str, holder: str) -> None:
    """Delete the lease if it is still this holder's: a run that outlived its lease must
    not free the one its successor now holds. Never raises; an unreleased lease expires."""
    try:
        await DatasetLease.find({"_id": name, "holder": holder}).delete()
    except Exception:
        logger.warning("Could not release the lease %s; it expires on its own", name, exc_info=True)
