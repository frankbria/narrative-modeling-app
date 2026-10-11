# #665 — training's S3 download and parse run on the event loop before the semaphore (P1.62)

Self-authored plan (the issue has two acceptance criteria, no plan).

## Decisions made here
- **Both halves of AC1.** The parse moves to `asyncio.to_thread`, and the whole load
  (download + parse) moves inside the training semaphore. The download was already off
  the loop (`download_file_bytes` uses `to_thread`); the pandas parse was not.
- **Two new small functions, `_parse_dataset` and `_load_training_frame`,** hold the code
  that leaves `train_model_task`. The task itself stays over the CRAP ceiling under the
  standing #842 exemption; it gets shorter here (cc 41 to 37).
- **The parse is moved as it stood** (same `decode` + `StringIO` for CSV, same type
  dispatch). Routing training through `load_dataframe_from_s3`, the reader every other
  stage uses, is #842's: it changes which seam the existing training tests stub.
- **The `TimeoutError` → wall-clock mapping now wraps `engine.run` alone.** With the load
  beside it inside the semaphore, the old outer `try` would have reported an S3 socket
  timeout as the plan's wall-clock limit.
- **The "Dataset downloaded" log line goes through `on_event`** (a partial write). It used
  to be a full `save()` at task entry; after a wait for a slot, a full save could
  overwrite a cancellation.
- AC2's timing test is marked `performance` (outside the PR gate): it measures time and
  pandas holds the GIL for parts of a parse. The gate's version asserts the parse runs on
  a worker thread.

## Acceptance criteria (from the issue)
- [x] AC1: the S3 download + parse run in `to_thread` and inside the training semaphore.
- [x] AC2: a test/benchmark confirms a large parse does not block other request handling.

## Steps
1. Tests first: loop stall during a large parse; no download while every slot is held;
   a download timeout is not the wall clock; each stored type reaches the engine.
2. `_parse_dataset`, `_load_training_frame`; call the latter inside the semaphore.
3. CLAUDE.md: the training concurrency paragraph.
