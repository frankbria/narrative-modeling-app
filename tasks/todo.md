# Issue #451 — [P0.8] Mass assignment on /api/v1/user_data

Branch: `fix/451-user-data-mass-assignment`

## Problem
`POST /api/v1/user_data/` and `PUT /api/v1/user_data/{id}` take the **Beanie Document
itself** as the request body (`user_data: UserData`, `updated: UserData`). There is no
request schema, so every field is client-settable — including `s3_url`, which the
visualization and preview endpoints later fetch. A tenant can point `s3_url` at another
tenant's object and read it back through a legitimately-scoped endpoint.

## Two things the issue could not have known, which change its criteria

**AC1 says "removed from the create/update request schemas". There are no request
schemas** — the Document is the body. The fix is to introduce `UserDataCreate` /
`UserDataUpdate` exposing only client-settable fields, which is a larger change than
deleting a field but the only one that actually closes it: today `file_path`,
`contains_pii`, `pii_masked`, `is_processed` and the rest are equally settable.

**AC3's tenant-prefix half is not implementable for this id-space.** Legacy `UserData`
uploads key objects as `generate_s3_filename()` → `"{uuid4}.{ext}"` — flat, with **no
tenant component**. There is nothing to check a caller's prefix against, and enforcing
one would break every legitimate legacy read. (`DatasetMetadata` is the id-space that
uses `datasets/{user}/...`; the two are separate, per CLAUDE.md.) The bucket-allowlist
half is implementable and worth having, so that is what gets built; the prefix half is
reported with the reason, and the durable fix — namespacing new uploads under the owner
— is filed separately because it changes key layout for existing objects.

## Plan
1. **RED** — route tests (`async_authorized_client`, real documents):
   - POST carrying `s3_url` pointing at another tenant's key → the stored value is
     server-derived, not the supplied one (AC4)
   - PUT carrying a foreign `s3_url` → stored value unchanged (AC4)
   - POST/PUT carrying `user_id` for another tenant → ignored (AC2)
   - PUT on another tenant's document → 404 (currently 403, which confirms existence)
   - `get_file_from_s3` rejects a bucket outside the allowlist (AC3)
2. **GREEN**
   - `UserDataCreate` / `UserDataUpdate` in `app/schemas/user_data.py` with only
     client-settable fields; `s3_url`, `user_id`, `id`, timestamps derived server-side
   - bucket allowlist in `app/utils/s3.py::get_file_from_s3`
   - PUT's 403 → 404
3. **AC5 is a data check I cannot run** — it needs the production/staging Atlas cluster,
   which is not reachable from here (and #444's rotation left the local credential
   stale). Write the query, hand it to the operator, record on the issue.
4. Docs: `SECURITY_OWNERSHIP_CHECKS.md`.

## Acceptance criteria
- [ ] AC1 `s3_url` not acceptable from the client on create/update
- [ ] AC2 other server-authoritative fields audited (`user_id` above all)
- [ ] AC3 bucket allowlist (prefix half reported as not applicable, with reasons)
- [ ] AC4 route test proves a supplied `s3_url` does not land
- [ ] AC5 data check handed to the operator with an exact query
