# Chunked upload group: #463 (P0.20) → #464 (P0.21) → #462 (P0.19) → #454 (P0.11)

All four issues instruct landing together — same handler, ~150 lines. #463 unblocks the rest.

## Scope decision
- `init_chunked_upload` moves to `Form(...)`. The client already sends a form body
  (`useChunkedUpload.ts:56-67`) and a form body is right for a POST; a 3-line backend
  change beats changing a shipped client. Frontend needs no edit — verified by the
  existing `apiUrlConstruction` test.
- Add `DELETE /chunked/{session_id}` (abort). #454 AC4 names abort explicitly, and
  `cancelUpload` currently leaks the temp file until session expiry.

## Backend `app/services/security/upload_handler.py`
1. `_generate_session_id` → `secrets.token_urlsafe(32)` (AC3 of #454).
2. Reject a session_id that is not `[A-Za-z0-9_-]+` in `_get_session` — it is a path
   param spliced into `temp_dir / f"{sid}.json"`.
3. `init_upload(user_id, ...)` stores `user_id` on the session.
4. `upload_chunk`/`resume_upload`/`complete_upload` take `user_id`; a session owned by
   someone else is indistinguishable from missing (404).
5. New `abort_upload(session_id, user_id)` — deletes temp file + metadata.

## Backend `app/api/routes/secure_upload.py`
6. `init_chunked_upload`: `Form(...)` params; pass `current_user_id`.
7. chunk / resume / complete: pass `current_user_id` through.
8. `complete_chunked_upload`:
   - server-derived key `datasets/{user_id}/{uuid}.{ext}` (#464 AC1/AC2)
   - `upload_file_to_s3(content, key, content_type=<real mime>)` (#464 AC3, #462 AC1)
   - unpack `(success, url)`, 500 on failure, assign only the URL (#462 AC2)
   - supply `original_filename` (#462 AC3) and `file_type`
   - 400 instead of NameError for a non-csv/xlsx filename
9. New abort route.

## Tests
- `tests/test_api/test_secure_upload.py`: rewrite the chunked class onto
  `async_authorized_client` + real Mongo `UserData` (conftest's `mock_user_data` is
  what certified the broken path — #462 AC4). Mutation-check.
- Cross-tenant: A cannot chunk/resume/complete/abort B's session → 404.
- Two tenants, same filename → distinct keys, both readable (#464 AC5).
- `tests/test_security/test_upload_handler.py`: update for the `user_id` argument.

## Migration (#464 AC4)
Inventory unprefixed keys in the bucket. The flow has never worked end-to-end
(#463 blocks init, #462 500s completion) so expect zero objects; record the finding.
