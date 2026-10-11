# #735 — uploads write the S3 object before `insert()`; a failed insert orphans it (P1.61)

Self-authored plan (the issue lists two options, no plan and no acceptance criteria).

## Decisions made here
- **Delete on failure, in one middleware, not in each route.** `upload_file_to_s3` records
  every object it writes during a request. `UnownedUploadCleanupMiddleware` runs when the
  request ends in a 4xx/5xx or an unhandled exception, and deletes each recorded object
  that no document references. Same shape as `QuotaRefundMiddleware`, for the same
  reason: routes get added, and the one that forgets orphans silently.
- **Why not a guard in each route:** five handlers write then insert (`/upload/secure`,
  `/upload/confirm-pii-upload`, chunked `complete`, `/upload/`, `/datasets/upload`), at
  cyclomatic complexity 23, 8, 11, 16 and 11. Editing any of them means splitting it for
  the CRAP gate, which is a rewrite of the whole upload surface for a cleanup fix. The
  middleware touches none of them and also covers the onboarding sample loader and the
  transformation writers, which use the same helper.
- **"Owned" is decided by looking, not by where the exception came from.** An object is
  kept if any `UserData` or `DatasetMetadata` row of that tenant names its key in
  `s3_url`, `file_path`, `source_s3_url` or `superseded_s3_urls`. So an insert that landed
  and then raised, or `/datasets/upload` failing on its second (twin) write, keeps the
  object. If the lookup or the delete itself fails, the object is left and the failure is
  logged: an orphan is reported by `scripts/inventory_orphaned_s3_objects.py`, a deleted
  object that a row still points at is data loss.
- `upload_file_to_s3` is cc 8, so the recording is a decorator on it, not an edit inside it.
- Not covered: a request cancelled by a client disconnect (the refund middleware has the
  same limit), and a 2xx that reports failure in its body after uploading.
- From review: `TransformationConfig.current_file_path` and
  `BulkTransformationJob.output_file_path` also count as ownership, the key is matched raw
  or percent-encoded, and both log lines name the key.

## Acceptance criteria (derived from the issue)
- [x] AC1: a request that fails after the S3 put on `/upload/secure`,
      `/upload/confirm-pii-upload` or chunked `complete` leaves no object in the bucket.
- [x] AC2: the same holds for the other writers through the helper, shown on
      `/datasets/upload` with a file that fails processing (no fault injection).
- [x] AC3: a successful upload keeps its object, and an object a document references is
      never deleted even when the request then fails.
- [x] AC4: a cleanup that cannot run (lookup or delete fails) does not change the
      response, and is logged.

## Steps
1. Tests first: LocalStack tests per route (real bucket listing), plus gate-suite tests of
   the middleware with real documents and a stubbed delete.
2. `app/utils/s3.py`: the per-request record and the decorator.
3. `app/middleware/upload_cleanup.py`: the middleware; mount it in `app/main.py`.
4. CLAUDE.md: the chunked-upload / S3 section.
