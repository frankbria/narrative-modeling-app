# #878 — local development and the test suite stay off the shared bucket (P2.60)

Self-authored plan.

## Decisions made here
- **Tests (AC4).** `tests/conftest.py` assigns `AWS_ENDPOINT_URL` and sets the three
  credential variables to nothing, before any app import. Assigned rather than
  `setdefault`, because the values to keep out come from two places: the developer's
  `.env` (loaded without override, so only a variable that is already set is safe from
  it) and the developer's shell.
  - Blank, not placeholder, credentials: with none, `S3Service` is in mock mode and
    `get_s3_client()` is `None`, which is exactly what the PR gate has. A placeholder
    would have made `get_s3_client()` return a client in CI where it returns `None` today.
  - The endpoint is pinned as well, so a test that sets credentials of its own still
    cannot reach AWS.
- **Warning (AC2).** `development_uses_a_real_bucket()` in `app/config.py`; `S3Service`
  logs once when it is built. Not in the lifespan: that function is over the complexity
  ceiling and the service is built once per process anyway. `S3Service.__init__` was at
  the ceiling itself, so the credential test moved out into `_lacks_real_credentials`.
- **Docs (AC1, AC3).** `.env.example` and the README default to LocalStack with the two
  commands that start it and create the bucket; a real bucket is described as an opt-in.
- The owner's own `.env` is outside the repo; switching it is the owner's step.

## Steps
- [x] Tests: the pin, a `.env` that cannot undo it, every client kind points away from
      AWS, the predicate's truth table, the warning logged once.
- [x] conftest, the predicate, the warning, the `s3_client` fixture.
- [x] `.env.example`, README, TEST_INFRASTRUCTURE.md, CLAUDE.md.
- [ ] Full gate and the LocalStack integration suite with the pin, review, PR, demo, CI, merge.
