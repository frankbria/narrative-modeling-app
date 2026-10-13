"""The named steps the application lifespan was split into for #694.

The lifespan was one function at cyclomatic complexity 11. Two of its pieces had no
test of their own: the periodic stale-job sweep and closing the rate-limit store.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app import main
from app.services import job_reaper


@pytest.mark.asyncio
async def test_the_periodic_sweep_keeps_going_after_a_failed_iteration(monkeypatch):
    sweeps = AsyncMock(side_effect=[RuntimeError("mongo went away"), None, asyncio.CancelledError()])
    monkeypatch.setattr(job_reaper, "reap_stale_jobs", sweeps)
    monkeypatch.setattr(job_reaper, "JOB_REAPER_INTERVAL_SECONDS", 0)

    with pytest.raises(asyncio.CancelledError):
        await main._reaper_loop()

    assert sweeps.await_count == 3  # the failure did not end the loop


@pytest.mark.asyncio
async def test_a_sweep_that_fails_at_startup_does_not_stop_the_app(monkeypatch):
    monkeypatch.setattr(job_reaper, "reap_stale_jobs", AsyncMock(side_effect=RuntimeError("mongo went away")))

    await main._reap_stale_jobs_once()  # no raise


@pytest.mark.asyncio
async def test_the_rate_limit_store_is_closed_when_it_can_be():
    closable = SimpleNamespace(close=AsyncMock())

    await main._close_rate_limit_store(SimpleNamespace(state=SimpleNamespace(rate_limit_store=closable)))
    await main._close_rate_limit_store(SimpleNamespace(state=SimpleNamespace(rate_limit_store=object())))
    await main._close_rate_limit_store(SimpleNamespace(state=SimpleNamespace()))

    closable.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_stopping_the_sweep_cancels_it_and_tolerates_there_being_none():
    async def forever():
        await asyncio.sleep(3600)

    task = asyncio.create_task(forever())

    await main._stop_reaper(SimpleNamespace(state=SimpleNamespace(reaper_task=task)))
    await main._stop_reaper(SimpleNamespace(state=SimpleNamespace()))

    assert task.cancelled()
