# #368 — Plan enforcement on metered endpoints

## The decision the issue forces

`metering.remaining()` is two independent reads, so it cannot back a hard limit —
concurrent requests all see room. Rather than accept a bounded overshoot, close
the window: add `metering.consume()`, a single conditional `$inc` that checks and
consumes in one operation.

The trick that makes it one operation: filter on `units <= limit - amount` with
`upsert=True`. No record yet → the upsert inserts one. A record already at the
limit → the filter misses, the upsert tries to insert a duplicate, and the unique
index on `(user_id, period_key, metric)` raises `DuplicateKeyError`, which *is*
the denial. No read precedes the write.

Guard: `amount > limit` is denied up front, or the insert path would create a
record above a limit it never checked (and `limit == 0` would allow 1 through).

## Enforcement counts; endpoints do not

The dependency is the only thing counting these metrics, so nothing
double-counts. Reserved units are refunded when the request fails, in one
middleware rather than in every route — otherwise a malformed upload burns quota
and a free tenant loses their 20 uploads to typos.

## Steps

1. `metering.consume()` / `refund()` — atomic reserve; tests incl. a real race
2. `app/billing/enforcement.py` — `quota(metric)` dependency, 402 carrying the
   limit and the reset; a variant for the X-API-Key surface
3. Refund middleware on any >=400 response
4. Wire the six metered routes:
   - `POST /api/v1/ml/train` → training_runs
   - `POST /api/v1/ml/{id}/predict` → predictions
   - `POST /api/v1/jobs` (batch) → predictions
   - `POST /api/v1/production/v1/models/{id}/predict` → predictions
   - `POST /api/v1/datasets/upload` → uploads
   - `POST /api/v1/upload/secure` → uploads
5. ~~Frontend: surface the 402 as an upgrade prompt~~ — **skipped, deliberately.**
   Not in the issue's scope, and the proactive surface already shipped: the #365
   Plan & usage page shows per-metric bars that turn amber at 80%, which warns
   before the wall instead of explaining it afterwards. Wiring 402 handling into
   every service call site is a large diff for the worse half of the UX. Add when
   there is a real complaint about the raw error.
6. Docs: CLAUDE.md conventions

## Invariants
- Enforcement never fails open — a storage error denies, unlike `record()`.
- Composes with #261 invite gate and #151 rate limiting; replaces neither.
- Unlimited (-1) tiers skip the reserve entirely but still count.

## Result

- `consume()`/`refund()` — 15 tests, three mutants killed (read-then-write loses
  the race 20/5; no `amount > limit` guard allows a 0-limit tenant through; no
  refund clamp mints negative usage).
- Route wiring — 8 tests through the full app; unregistering the middleware and
  detaching the dependency each redden a test.
- Full backend suite: 2377 passed, 1 pre-existing failure
  (`test_redis_cache_integration`, fails on a clean tree too).
- Fixed on the way: `tests/test_api/test_secure_upload.py` ran three tests with no
  Beanie at all via `mock_async_client`; they now take `setup_database`.
