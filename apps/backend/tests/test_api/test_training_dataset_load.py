"""#665: training parsed its dataset on the event loop, before taking a training slot.

`train_model_task` awaited the S3 download and then ran `pd.read_csv` /
`read_excel` / `read_parquet` inline. A large parse stalled every other request for
its duration, and because it ran before the semaphore, any number of queued jobs
could each hold a parsed frame in memory at once (the cap in #498 only bounded the
engine run). Only the S3 download and the engine are stubbed here; the parse is real.
"""
import asyncio
import io
import time
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from app.models.training_job import JobStatus, TrainingJob

pytestmark = pytest.mark.asyncio


class _StopAfterLoad(Exception):
    """Ends the run once the engine has been handed the frame."""


def _dataset(file_type: str = "csv") -> MagicMock:
    return MagicMock(
        id="dataset_665", user_id="test_user", file_type=file_type,
        s3_url="s3://test-bucket/datasets/test_user/data.csv",
    )


async def _job(model_id: str) -> TrainingJob:
    job = TrainingJob(
        model_id=model_id, user_id="test_user", dataset_id="dataset_665", target_column="target"
    )
    await job.insert()
    return job


def _big_csv() -> bytes:
    """Large enough that parsing it takes a visible fraction of a second."""
    frame = pd.DataFrame(np.random.default_rng(665).random((400_000, 8)))
    frame.columns = [f"f{i}" for i in range(7)] + ["target"]
    return frame.to_csv(index=False).encode()


def _xlsx(frame: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    frame.to_excel(buffer, index=False)
    return buffer.getvalue()


async def _longest_stall(stop: asyncio.Event) -> float:
    """The longest the event loop went without running a ready coroutine."""
    longest, last = 0.0, time.perf_counter()
    while not stop.is_set():
        await asyncio.sleep(0.005)
        now = time.perf_counter()
        longest, last = max(longest, now - last), now
    return longest


async def _run(dataset, model_id: str, download: AsyncMock, seen: list) -> None:
    from app.api.routes.model_training import TrainModelRequest, train_model_task

    async def engine_run(df, *_a, **_k):
        seen.append(df.shape)
        raise _StopAfterLoad

    with (
        patch("app.services.s3_service.S3Service.download_file_bytes", download),
        patch("app.api.routes.model_training.AutoMLEngine") as engine_cls,
    ):
        engine_cls.return_value.run = engine_run
        await train_model_task(
            dataset, TrainModelRequest(dataset_id="dataset_665", target_column="target"),
            "test_user", model_id,
        )


@pytest.mark.performance
async def test_parsing_a_large_dataset_does_not_stall_the_event_loop(setup_database):
    """A benchmark, outside the PR gate: it measures time, and pandas still holds the
    GIL for parts of a parse, so the loop hitches for a fraction of it. The gate's
    version of this fact is `test_the_parse_runs_on_a_worker_thread`."""
    content = _big_csv()
    started = time.perf_counter()
    pd.read_csv(io.BytesIO(content))
    parse_seconds = time.perf_counter() - started
    if parse_seconds < 0.15:
        pytest.skip("this machine parses the file too fast for a stall to be measured")

    job = await _job("model_665_stall")
    stop, seen = asyncio.Event(), []
    try:
        watcher = asyncio.create_task(_longest_stall(stop))
        await _run(_dataset(), "model_665_stall", AsyncMock(return_value=content), seen)
        stop.set()
        stall = await watcher
    finally:
        await job.delete()

    assert seen == [(400_000, 8)], "the engine was handed the whole parsed frame"
    # On the loop the stall is the whole parse and more (0.37s for a 0.24s parse when
    # this was written); off it, between a fifth and a half of the parse.
    assert stall < parse_seconds * 0.75, (
        f"the loop stalled for {stall:.2f}s while a {parse_seconds:.2f}s parse ran"
    )


async def test_the_parse_runs_on_a_worker_thread(setup_database):
    """The same fact without a stopwatch: pandas is not called from the loop's thread."""
    import threading

    from app.api.routes import model_training

    parsed_on: list[int] = []
    real_read_csv = pd.read_csv

    def read_csv(*args, **kwargs):
        parsed_on.append(threading.get_ident())
        return real_read_csv(*args, **kwargs)

    job = await _job("model_665_thread")
    try:
        with patch.object(model_training.pd, "read_csv", read_csv):
            await _run(_dataset(), "model_665_thread", AsyncMock(return_value=b"a,target\n1,0\n2,1\n"), [])
    finally:
        await job.delete()

    assert parsed_on and parsed_on[0] != threading.get_ident()


async def test_the_dataset_is_not_loaded_until_a_training_slot_is_free(setup_database):
    from app.services.training_admission import (
        MAX_CONCURRENT_TRAINING_JOBS,
        training_semaphore,
    )

    job = await _job("model_665_queued")
    download, seen = AsyncMock(return_value=b"a,target\n1,0\n2,1\n"), []
    slots = training_semaphore()
    for _ in range(MAX_CONCURRENT_TRAINING_JOBS):
        await slots.acquire()
    try:
        task = asyncio.create_task(_run(_dataset(), "model_665_queued", download, seen))
        await asyncio.sleep(0.2)
        assert not task.done()
        download.assert_not_awaited()  # queued: nothing downloaded, nothing held in memory

        for _ in range(MAX_CONCURRENT_TRAINING_JOBS):
            slots.release()
        await task
    finally:
        await job.delete()

    download.assert_awaited_once()
    assert seen == [(2, 2)]


async def test_a_download_timeout_is_not_reported_as_the_wall_clock(setup_database):
    """The load now runs beside the engine's wall clock; its own socket timeout is a
    TimeoutError too and must not borrow the plan-limit message."""
    job = await _job("model_665_timeout")
    try:
        await _run(
            _dataset(), "model_665_timeout",
            AsyncMock(side_effect=TimeoutError("read timed out")), [],
        )
        refreshed = await TrainingJob.find_one(TrainingJob.model_id == "model_665_timeout")
    finally:
        await job.delete()

    assert refreshed.status == JobStatus.FAILED
    assert "wall-clock" not in refreshed.error


@pytest.mark.parametrize("file_type, encode", [
    ("csv", lambda f: f.to_csv(index=False).encode()),
    ("parquet", lambda f: f.to_parquet(index=False)),
    ("xlsx", lambda f: _xlsx(f)),
])
async def test_each_stored_type_reaches_the_engine_as_the_same_frame(setup_database, file_type, encode):
    frame = pd.DataFrame({"a": [1, 2, 3], "target": [0, 1, 0]})
    job = await _job(f"model_665_{file_type}")
    seen: list = []
    try:
        await _run(_dataset(file_type), f"model_665_{file_type}", AsyncMock(return_value=encode(frame)), seen)
    finally:
        await job.delete()

    assert seen == [(3, 2)]


async def test_an_unsupported_type_fails_the_job_and_names_nothing_internal(setup_database):
    job = await _job("model_665_txt")
    seen: list = []
    try:
        await _run(_dataset("txt"), "model_665_txt", AsyncMock(return_value=b"a\ttarget\n1\t0\n"), seen)
        refreshed = await TrainingJob.find_one(TrainingJob.model_id == "model_665_txt")
    finally:
        await job.delete()

    assert seen == [] and refreshed.status == JobStatus.FAILED
