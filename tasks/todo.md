# Issue #515 — [P1.11] [perf] Batch prediction jobs run as unbounded in-process asyncio tasks

Plan source: self-authored. Approved autonomously — the issue marks (a) bound concurrency + (c) per-tenant cap as the launch-relevant half; (b) chunked streaming is already the code's O(chunk_size) design (verified) with tests. No fork.

## Findings
- `_spawn_processing` does `asyncio.create_task(...)` with no bound; one tenant can start arbitrarily many.
- Streaming IS in place: `_read_data_chunks` uses `pd.read_csv(chunksize=)`, results stream to a temp file, `_upload_results_file` streams from disk — peak memory O(chunk_size). Tested (`test_process_batch_job_streams_results_across_chunks`, `_streams_valid_json_across_chunks`). AC2/AC4 (memory) are pre-existing and covered.
- `bulk_transformation_service` already has the per-user pattern (`MAX_CONCURRENT_JOBS_PER_USER`, active-count query) to mirror.

## Design
1. **Global bound (AC1):** a per-process `asyncio.Semaphore(_MAX_CONCURRENT_BATCH_JOBS)` (default 2, env-tunable), acquired around the run; excess jobs queue instead of all executing. Per running loop (tests use many loops). Direct `_process_batch_job(auto_start=False)` calls bypass it, staying deterministic.
2. **Per-tenant cap (AC3):** `create_batch_prediction_job` counts the user's PENDING/RUNNING batch jobs before the S3 upload and raises `BatchConcurrencyLimitError`; the route maps it to 429, and the refund middleware returns the reserved units.
3. A queued job cancelled before it starts (semaphore held) is skipped after acquisition — small guard; full cancel is #485.

## Steps
- [ ] RED tests (per-user 429, global semaphore bounds concurrency, cancelled-while-queued skipped)
- [ ] semaphore + admission + route 429
- [ ] gate → PR → demo → CI → merge
