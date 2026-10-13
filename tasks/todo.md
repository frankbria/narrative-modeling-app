# Issue #752: three e2e specs whose backend calls never reach the backend

## What each one turned out to be
- `upload.spec.ts`, the metadata check: a relative `/api/v1` URL (answered by the Next dev
  server), the wrong id-space, and a branch that logged "skipped" on any failure. The test
  is `@smoke`.
- `ai-recommendations.spec.ts`: 15 tests posting to `/ai/analyze-dataset`. No such route.
- `transformation-preview.spec.ts`: drives a `/datasets` page that does not exist.

## Plan
- [x] The metadata check reads `GET {API_BASE}/user_data/{id}` with the session's token and
      asserts 200 and the record. Run on the real stack; mutation-checked (a wrong path fails it).
- [x] The two specs that cannot run are deleted, with why.
- [x] The rest of the unrun suite: #991.
