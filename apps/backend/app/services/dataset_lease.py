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

#: How long a lease lasts once its holder stops renewing it (a worker that died mid-run).
LEASE_SECONDS = 300.0
#: How often a living holder pushes its expiry out. Well inside the lease, so a renewal
#: delayed by a busy event loop still lands in time.
RENEW_SECONDS = 60.0
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
    renewing = asyncio.create_task(_keep(name, holder))
    try:
        yield
    finally:
        renewing.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await renewing
        await _release(name, holder)


async def _keep(name: str, holder: str) -> None:
    """Renew the lease for as long as its holder is running.

    Work that takes longer than the lease is still one holder: without this a second
    caller took a live holder for a dead one once the lease ran out, and both wrote.
    """
    while True:
        await asyncio.sleep(RENEW_SECONDS)
        try:
            await DatasetLease.find({"_id": name, "holder": holder}).update(
                {"$set": {"expires_at": utcnow() + timedelta(seconds=LEASE_SECONDS)}}
            )
        except Exception:
            logger.warning("Could not renew the lease %s", name, exc_info=True)


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
