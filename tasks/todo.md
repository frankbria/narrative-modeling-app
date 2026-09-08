# Issue #455 — [P0.12] rate_limit=0 disables rate limiting on the paid serving surface

## Decision (AC1)
**Clamp**, not reject. `rate_limit` stays in the API (a tenant lowering their own key's
budget is legitimate blast-radius control), but it is validated `ge=1` and clamped
server-side to the tenant's plan ceiling from `plans.py`.

## Steps
1. `app/billing/plans.py` — add `api_key_rate_limit` to `PlanLimits` (finite for every
   tier, including ENTERPRISE; env-overridable). Not a metered metric, so it stays out
   of `METERED_METRICS` / `limit_for`.
2. `app/api/routes/production.py` — `rate_limit: int = Field(default=..., ge=1)` (0 and
   negatives 422 before the handler runs) and clamp to `limits_for(tier).api_key_rate_limit`
   at creation.
3. `app/middleware/rate_limit.py` — floor the stored per-key limit at 1 when resolving
   identity, so a legacy row with `rate_limit<=0` cannot be unlimited. No tier lookup
   on the hot path (the ceiling is enforced at creation + by the remediation script).
4. `scripts/fix_api_key_rate_limits.py` — report + correct existing rows outside
   `[1, ceiling]`; record the count on the issue (AC3).
5. Tests (AC4/AC5): rate limiting is disabled in the test env, so exercise the limiter
   directly via the `_build_app(..., enabled=True)` harness in
   `tests/test_middleware/test_rate_limit.py`, plus route tests for the 422 and the clamp.
