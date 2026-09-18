# #768 — Abuse and cost backstops before signup opens

Branch: feat/768-abuse-cost-backstops. Plan self-authored (none on the issue).

## Steps
1. AC1 SIGNUP_MODE (both halves)
   - backend `app/config.py`: `resolve_signup_mode()` → "open"|"invite"; blank in production-like → invite (fail closed); blank in dev/test → legacy (allowlist set → invite, else open); invalid → invite + error log. `signup_admits(email)`; invite with empty allowlist admits nobody.
   - `nextauth_auth.py` gate uses it; lifespan logs the mode (WARNING when open).
   - frontend `lib/invite-allowlist.ts`: `resolveSignupMode(env, nodeEnv)`; `isSignInAllowed` uses it; auth.ts logs when open.
   - compose: `SIGNUP_MODE: ${SIGNUP_MODE:-}` on both services (optional until provisioned — #457 rule; blank = invite in staging, i.e. today's behaviour). Operator follow-up flips it to `:?`.
2. AC2 global AI ceiling
   - `app/billing/ai_ceiling.py`: `AI_CALLS_DAILY_CEILING` (_env_positive_int, default 500 = $60/day at ADR-003's $0.12 gpt-4 worst case), `admit()` = conditional $inc on UsageRecord(user_id="__global__", period_key=YYYY-MM-DD, metric="ai_calls"); fails closed; on denial ERROR log + Prometheus counter.
   - choke point: `with_circuit_breaker` for services named `openai*` checks the ceiling once per logical call (outside tenacity retries) and raises `AICeilingReached(CircuitBreakerOpen)` → every caller's existing fallback.
   - fix release gaps: feature `/suggest` ai_used set only after a call ran; `/ai/summarize` releases on fallback.
3. AC3 nginx `limit_req_zone` on `/api/auth/` + test (RATE_LIMIT_TRUST_PROXY already in compose, #483).
4. AC4 health probe: accounts created in last 24h (NextAuth `users` `_id` timestamp) printed + `signup_rate` status unhealthy above `SIGNUP_ALERT_THRESHOLD_24H`.
5. AC5 FREE storage ceiling: `PlanLimits.storage_bytes` (FREE 500 MB, PRO/ENT unlimited), `UserData.file_size` written at every dataset writer, `enforce_storage_ceiling(user, incoming)` → 402 quota_exceeded(metric=storage_bytes) at each dataset-creating route.
6. AC6 `/metrics` requires backend ADMIN_EMAILS (fail closed, 404 otherwise) + test.
7. AC7 ADR-003 aggregate line + storage limit.
8. Docs: CLAUDE.md conventions, .env examples.

## Acceptance criteria
- [x] AC1 explicit signup mode, fail closed in prod, tests both halves
- [x] AC2 global AI ceiling → fallback + release + alert
- [x] AC3 auth edge rate limit (repo; deploy via #594)
- [x] AC4 account-creation count + alert threshold
- [x] AC5 FREE storage ceiling
- [x] AC6 /metrics admin-only, test pins it
- [x] AC7 ADR-003 aggregate exposure line
