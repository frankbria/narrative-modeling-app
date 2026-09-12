# Issue #461 — [P0.18] [billing] Every OpenAI-backed endpoint is unmetered

Plan source: self-authored. Fork considered: call-based vs token-based metric → call-based (`ai_calls`).
Token counts are only known after the response, so they cannot be reserved atomically; a per-call
unit reuses `quota()` verbatim. No stop needed.

## Design
- `ai_calls` joins `METERED_METRICS` + `PlanLimits`; ceilings FREE 50 / PRO 2 000 / ENTERPRISE 20 000 per period,
  **finite for every tier** and read through `_env_positive_int`, so an env override cannot lift the ceiling (AC5 backstop).
- `quota("ai_calls")` on all four `ai_analysis.py` routes. `/insights` and `/chat/{file_id}` are 501 stubs (#274) —
  metered anyway so implementing them cannot reopen the hole; the refund middleware hands the unit back on 501.
- Registry test for `/api/v1/ai` POSTs (walker in `test_dataset_routes_are_metered.py` gains a `prefixes` arg).
- Route tests (real Mongo): user at the FREE `ai_calls` limit → 402 on analyze + summarize, service never called, no unit consumed.
- `/api/chat` bounded independently: message ≤ 4 000 chars, context ≤ 8 000, history ≤ 20 turns of `{role: user|assistant, content ≤ 4 000}`,
  total ≤ 24 000 chars → 400 before OpenAI; context goes in a fenced *untrusted data* message, not the system prompt. 20/min rate cap stays.
- Billing page: `ai_calls: 'AI calls'` label (types are `Record<string, number>` already).

## Steps
1. [ ] Backend RED: plans tests (finite, monotonic, override refused), registry, 402 route tests
2. [ ] Backend GREEN: plans.py, ai_analysis.py; `setup_database` on the AI route tests that now touch Subscription
3. [ ] Frontend RED/GREEN: route.test.ts caps + context handling; route.ts; billing label
4. [ ] Docs: CLAUDE.md plan-enforcement bullet (ai_calls, finite ceiling, /api/chat is bounded not metered)

## Acceptance criteria
- [ ] AC1 metric with per-tier ceilings
- [ ] AC2 four routes carry quota
- [ ] AC3 /api/chat history/size caps + rate cap
- [ ] AC4 context validated and constrained
- [ ] AC5 finite per-tenant ceiling that config cannot lift
- [ ] AC6 402 tests with no OpenAI call
