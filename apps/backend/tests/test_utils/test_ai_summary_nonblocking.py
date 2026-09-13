"""ai_summary's OpenAI call must not block the event loop (#501, AC5).

The synchronous OpenAI client is called from an async BackgroundTask after every
upload. Before #501 it ran inline and froze the worker for the whole round-trip;
now it goes through asyncio.to_thread. This asserts a *blocking* OpenAI call does
not delay an unrelated concurrent coroutine, and that a failure degrades to None
(the upload still succeeds with no summary — AC3).
"""

import asyncio
import time
from unittest.mock import MagicMock

import pytest

import app.utils.ai_summary as ai_summary
from app.utils.ai_summary import call_openai_api

pytestmark = [pytest.mark.usefixtures("beanie_models_initialized")]

_BLOCK_SECONDS = 0.5


@pytest.mark.asyncio
async def test_slow_openai_call_does_not_block_the_event_loop(monkeypatch):
    # slow_create runs the (synchronous) OpenAI round-trip; record the wall-clock
    # window it occupies. If the call is offloaded, a concurrent coroutine keeps
    # ticking DURING that window; if it runs inline on the loop, the loop is
    # frozen and zero ticks land inside it. monotonic timestamps are safe to write
    # from the worker thread (unlike asyncio.Event.set()).
    window = {}

    def slow_create(*args, **kwargs):
        window["start"] = time.monotonic()
        time.sleep(_BLOCK_SECONDS)
        window["end"] = time.monotonic()
        resp = MagicMock()
        resp.choices[0].message.content = '{"overview": "ok"}'
        return resp

    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = slow_create
    monkeypatch.setattr(ai_summary, "client", mock_client)

    tick_times: list[float] = []

    async def heartbeat():
        # Tick well past the blocking window so ticks would land inside it.
        for _ in range(int(_BLOCK_SECONDS / 0.02) + 20):
            await asyncio.sleep(0.02)
            tick_times.append(time.monotonic())

    summary, _ = await asyncio.gather(
        call_openai_api({"filename": "t.csv", "columns": []}),
        heartbeat(),
    )

    ticks_during_call = [t for t in tick_times if window["start"] <= t <= window["end"]]
    # Inline (blocking) → the loop is frozen for _BLOCK_SECONDS → zero ticks land
    # in the window. Offloaded → many (~_BLOCK_SECONDS / 0.02 ≈ 25).
    assert len(ticks_during_call) >= 5, (
        f"event loop was blocked during the OpenAI call "
        f"(ticks in-window={len(ticks_during_call)})"
    )
    assert summary is not None and summary.overview == "ok"


@pytest.mark.asyncio
async def test_openai_failure_degrades_to_none(monkeypatch):
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = TimeoutError("upstream hung")
    monkeypatch.setattr(ai_summary, "client", mock_client)

    result = await call_openai_api({"filename": "t.csv", "columns": []})
    assert result is None  # AC3: no summary, but no crash — the upload still succeeds
