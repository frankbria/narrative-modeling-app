# Issue #151 — Enforce API rate limiting (modeled but never enforced)

**Branch:** `feat/151-rate-limiting`
**Plan source:** self-authored (issue had no implementation-plan comment)

## Problem
`APIKey.rate_limit` is modeled and even partially checked in one route
(`production.py` predict), but there is **no global enforcement**. Every `/api/v1`
endpoint can be hammered without restriction (DoS + cost risk before beta).

## Design decisions
- **Global ASGI middleware** (not per-route decorators) so it covers *all* `/api/v1`
  routes per AC. Registered so CORS stays **outermost** (429s get CORS headers) and
  the limiter runs just before route handlers (blocks the expensive work).
- **Identity resolution** (in order): `X-API-Key` header → per-key limit from
  `APIKey.rate_limit` (window 1h, matching the field's documented semantics);
  else session Bearer token → default per-user limit; else client IP → default limit.
  Reuses existing `get_current_user_id_optional` (no auth-logic drift).
- **Storage:** pluggable `RateLimitStore`. `RedisRateLimitStore` (atomic INCR+EXPIRE
  fixed-window, async) is primary; `InMemoryRateLimitStore` for unit tests + a
  single-instance fallback. **Fail-open** when Redis is unreachable (log a warning) —
  never take the app down for a limiter outage (documented beta tradeoff).
- **429 response:** JSON body + `Retry-After` (seconds to window reset). Also adds
  `X-RateLimit-Limit/Remaining/Reset` on every `/api/v1` response.
- **Env-configurable** via new `Settings` fields.

## Steps (TDD: RED → GREEN → REFACTOR)
1. **Config** — add to `app/config.py`: `REDIS_URL`, `RATE_LIMIT_ENABLED` (def true),
   `RATE_LIMIT_DEFAULT_REQUESTS` (def 100), `RATE_LIMIT_DEFAULT_WINDOW_SECONDS`
   (def 60), `RATE_LIMIT_APIKEY_WINDOW_SECONDS` (def 3600).
2. **Store layer** — `app/services/rate_limit.py`: `RateLimitResult`, store protocol,
   `InMemoryRateLimitStore`, `RedisRateLimitStore` (lazy async client, fail-open).
   Add `APIKey.hash_key(raw)` staticmethod for shared hashing.
3. **Middleware** — `app/middleware/rate_limit.py`: `RateLimitMiddleware` (identity →
   limit/window → store hit → 200 + headers or 429 + Retry-After). Skip non-`/api/v1`
   paths and OPTIONS preflight.
4. **Wire up** — `app/main.py`: build the store in lifespan (from `REDIS_URL`), expose
   on `app.state`, register `RateLimitMiddleware` so CORS remains outermost.
5. **Refactor production.py** — remove the now-redundant in-route `check_rate_limit`
   + sync `redis` client (global middleware supersedes it; kills the sync-redis-in-async
   antipattern). Migrate its test into the middleware suite.
6. **Tests**
   - `tests/test_middleware/test_rate_limit.py` (unit, InMemory store): under limit→200,
     over→429 + `Retry-After`, headers present, window reset, OPTIONS / non-`/api/v1`
     skipped, disabled flag, fail-open when store errors.
   - integration (real Redis :6380): Redis-backed counter enforces + expires.
   - integration (DB): per-`APIKey` override honored (low `rate_limit` → 429 sooner).
   - update `tests/test_api/test_production.py` (drop direct `check_rate_limit` test).
7. **Docs** — update CLAUDE.md backend section + `.env` example; note beta limitations.

## Acceptance criteria
- [ ] Rate-limit middleware applied to all `/api/v1` routes
- [ ] Per-API-key limits read from `APIKey` model fields
- [ ] Sensible default per-user limits for session-authenticated requests
- [ ] 429 responses with `Retry-After` header
- [ ] Limits configurable via env
- [ ] Tests: over-limit→429; under-limit→200; key-specific overrides honored

## Known beta limitations
- Fixed-window (not sliding-window/token-bucket) — simple, matches existing per-hour field.
- Fail-open on Redis outage (availability > strict enforcement for beta).
- In-memory fallback is per-worker (not shared) — fine for single-instance staging.
