# Issue #466 — [P0.23] [bug] The first transformation on any dataset always fails — bare S3 key passed to a URL-only downloader

Plan source: self-authored; approved autonomously (no architectural fork).

## Design
- `DatasetMetadata.file_path` holds a raw key on a fresh upload and a full URL after a transformation; every
  `file_path or s3_url` site hands whichever it is to the strict, URL-only downloader → the first transform fails.
- One accessor, `app/utils/s3.py::downloadable_url(path_or_url, fallback=None)`: returns the value if it parses as a
  URL, else `s3://{allowed bucket}/{key}` — the validated core then applies its own key/bucket checks (#531).
- Sweep (AC2): every `file_path or s3_url` → `downloadable_url(...)`: transformation_service (2), transformations.py (3),
  data_issues.py (5), bulk_transformation_service (2). `feature_store_service` passes `file_path` to a *key-only*
  downloader — the inverse bug — resolved through the same accessor + `parse_s3_url`.
- AC3: LocalStack integration test — upload through `/datasets/upload`, apply a transformation through the real
  service, assert success and the transformed object in the bucket. `integration`-marked; runs in CI's integration job.

## Steps
1. [ ] RED: unit tests for `downloadable_url`; integration test (fails today with "Invalid S3 URL format")
2. [ ] GREEN: accessor + call sites
3. [ ] Docs: CLAUDE.md gotcha reworded around the accessor

## Acceptance criteria
- [ ] AC1 transformation call site resolves a full URL
- [ ] AC2 swept; shared accessor extracted
- [ ] AC3 end-to-end LocalStack test
- [ ] AC4 further instances noted on the issue
