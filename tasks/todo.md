# Issue #581 — [P1.35] [data-integrity] /secure and /confirm-pii-upload write bare {uuid} S3 keys with no tenant prefix — 155 such objects exist

Plan source: self-authored (no plan comment). No architectural fork; approved autonomously.

## Design

- **One key builder.** `dataset_s3_key(user_id, original_filename, *, masked=False)` in `app/utils/s3.py` returns `datasets/{user_id}/[masked_]{uuid4}.{ext}`. It replaces `generate_s3_filename` (deleted — a helper that cannot express the prefix must not exist for the next route to reach for) at **all four** call sites: `/upload/secure`, `/upload/confirm-pii-upload`, `/upload/` (`upload.py` — a third bare-key writer the issue did not list), and the chunked `complete` route (#464's inline f-string, consolidated).
- **Reconciliation** `scripts/reconcile_unprefixed_s3_keys.py`: list root-level objects matching `^(masked_)?{uuid4}\.\w+$`, match each to `UserData`/`DatasetMetadata` rows by `s3_url` (via the app's own `parse_s3_url`), copy under `datasets/{owner}/{basename}`, verify the copy (ContentLength + ETag), rewrite the rows' `s3_url` (and `file_path` when it held the old key), then delete the original. **Orphans (no owning row) are reported and never touched.** Dry-run by default, `--apply` to write, counts only in output. Exit 1 while unreconciled objects remain.
- **AC3 needs the operator.** The local backend has no AWS credentials; the 155-object production run is filed as a deployment follow-up with the exact command (the #589 pattern).

## Steps

1. [ ] `dataset_s3_key` + tests (`tests/test_utils/test_s3.py`): shape, masked variant, extension lowering/absence, uniqueness.
2. [ ] Replace the four call sites; delete `generate_s3_filename`; update the `require_allowed_bucket` docstring that cites it.
3. [ ] Route tests (AC4): `/upload/secure`, `/upload/confirm-pii-upload` (masked and unmasked), `/upload/` each write a key under `datasets/{user_id}/`, following `test_chunked_upload_flow.py`'s capture pattern.
4. [ ] Reconcile script + unit tests for `plan()` + an `integration`-marked LocalStack test: bare object + row → moved, row rewritten, original deleted; orphan → reported, untouched; dry-run → nothing written.
5. [ ] Erasure re-verified (AC5): `integration` test uploads through the real `/upload/secure` against LocalStack, erases, asserts the object is gone.
6. [ ] Docs: CLAUDE.md chunked-upload bullet (drop the "#581 still bare" note, record the helper), `require_allowed_bucket` docstring, `scripts/README.md`.

## Acceptance criteria

- [ ] AC1 both routes (and the other two) write `datasets/{user_id}/{uuid}.{ext}`
- [ ] AC2 `generate_s3_filename` replaced by a helper that takes the owner
- [ ] AC3 155 objects reconciled — script + tests here; production run is the operator's (follow-up issue)
- [ ] AC4 a test per route asserts the prefixed key
- [ ] AC5 erasure verified against a `/secure` upload

## Known limitation

The production reconciliation itself cannot run from this environment (no AWS credentials). Filed for the operator with the dry-run and `--apply` commands.
