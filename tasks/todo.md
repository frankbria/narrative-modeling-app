# Issue #584: chunked-upload session expiry is advisory

## Problem
1. Only `resume_upload` compares `expires_at` with now. `upload_chunk`, `claim_upload`
   and `abort_upload` do not, so a session past its window can still be appended to
   and completed.
2. `cleanup_expired_sessions` walks the in-memory store only. A session's metadata is
   also on disk so it survives a restart; after one, the pair is on disk and not in the
   store, and the sweep never reaps it.

## Plan
- [ ] RED: `tests/test_services/test_chunked_session_expiry.py`.
- [ ] Expiry is enforced where a session is resolved: `get_session` answers 410 for the
      caller's own expired session (a foreign or unknown id is still None, checked first,
      so 410 confirms nothing about another tenant). `abort_upload` passes
      `expired_ok=True`: discarding an expired session is the point of abort.
- [ ] The sweep also reads `{temp_dir}/*.json` for sessions this process does not hold,
      and deletes the expired ones' files. It does not load live ones into the store:
      another worker may own them, and a cached copy goes stale.
- [ ] AC4: no scheduler. The sweep already runs on every `/upload/secure` and chunked
      `init`, so disk-only sessions are now reaped at the next upload.
